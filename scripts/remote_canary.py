"""Owned remote-route checks and a single guarded HTML-only Funda canary.

Token is accepted on stdin only and stays in runtime memory. No local browser is
launched. No raw HTML, source identity digest, cookies or session URL is exported.
"""

import argparse
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "lab"
ACCOUNT = "ca1c3e97ff0a63340a6f72be720b0ff4"
OBSERVER = "https://funda-egress-observer.maartenjr-esser.workers.dev"
DENIED = "https://funda-egress-denied.maartenjr-esser.workers.dev"
TARGET_URL = "https://www.funda.nl/zoeken/koop?selected_area=%5B%22amsterdam%22%5D&search_result=1"
REQUIRED_CHECKS = {
    "observer_control",
    "allowed_origin",
    "remote_source",
    "guardrails_navigation",
    "guardrails_redirect",
    "guardrails_subresource",
    "guardrails_worker",
    "forbidden_count_unchanged",
    "javascript_disabled",
    "unresolvable_host_fail_closed",
    "context_cleanup",
    "response_interception",
    "same_host_redirect_blocked",
}


class GateError(ValueError):
    pass


def allowed_target(url, resource_type, main_navigation, sent):
    return url == TARGET_URL and resource_type == "document" and main_navigation and sent == 0


def valid_gate(gate, trial, code_hash, now):
    try:
        age = (now - datetime.fromisoformat(gate["checked_at"])).total_seconds()
        checks = gate["checks"]
        if (
            gate["status"] != "PASS"
            or gate["provider"] != "cloudflare-browser-run"
            or gate["trial"] != trial
            or gate["code_sha256"] != code_hash
            or not 0 <= age <= 1800
            or not REQUIRED_CHECKS <= checks.keys()
            or any(checks[name] is not True for name in REQUIRED_CHECKS)
        ):
            raise GateError("REMOTE_GATE_NOT_PASSED")
    except (KeyError, TypeError, ValueError) as error:
        raise GateError("REMOTE_GATE_NOT_PASSED") from error
    return True


class State:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript(
            "CREATE TABLE IF NOT EXISTS daily(day TEXT PRIMARY KEY,n INTEGER NOT NULL); CREATE TABLE IF NOT EXISTS target(key TEXT PRIMARY KEY,value TEXT NOT NULL);"
        )
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(daily)")}
        if "canary_n" not in columns:
            self.db.execute("ALTER TABLE daily ADD COLUMN canary_n INTEGER NOT NULL DEFAULT 0")
            self.db.commit()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    def reserve_browser(self, now, purpose="qa"):
        if purpose not in ("qa", "canary"):
            raise GateError("UNKNOWN_BROWSER_PURPOSE")
        column, cap = ("n", 3) if purpose == "qa" else ("canary_n", 2)
        day = now.astimezone(ZoneInfo("Europe/Amsterdam")).date().isoformat()
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO daily (day,n) VALUES (?,0)", (day,))
            return bool(
                self.db.execute(
                    f"UPDATE daily SET {column}={column}+1 WHERE day=? AND {column}<?", (day, cap)
                ).rowcount
            )

    def reserve_target(self, now):
        with self.db:
            return bool(
                self.db.execute(
                    "INSERT OR IGNORE INTO target VALUES ('attempt',?)", (now.isoformat(),)
                ).rowcount
            )

    def save_target(self, value):
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO target VALUES ('attempt',?)", (json.dumps(value),)
            )

    def last_target(self):
        row = self.db.execute("SELECT value FROM target WHERE key='attempt'").fetchone()
        if not row:
            return None
        try:
            return json.loads(row[0])
        except ValueError:
            return {"status": "STOPPED", "reason": "PREVIOUS_ATTEMPT_RESERVED"}


def code_hash():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class CloudSession:
    def __init__(self, token, allowed):
        if not token or not allowed or any("*" in host or "/" in host for host in allowed):
            raise GateError("EXPLICIT_GUARDRAILS_REQUIRED")
        self.token, self.allowed, self.session_id = token, allowed, None

    def cli(self, args):
        env = {
            **os.environ,
            "CLOUDFLARE_API_TOKEN": self.token,
            "NO_COLOR": "1",
            "PATH": "/Users/maartenesser/.nvm/versions/node/v26.13.1/bin:" + os.environ["PATH"],
        }
        env.pop("DEBUG", None)
        result = subprocess.run(
            [str(LAB / "node_modules/.bin/cf"), *args],
            cwd=LAB,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode:
            # Never copy CLI stdout/stderr: a provider response may contain session URLs.
            raise GateError("CLOUDFLARE_API_FAILED")
        try:
            value = json.loads(result.stdout)
        except ValueError:
            raise GateError("CLOUDFLARE_RESPONSE_UNRECOGNIZED") from None
        return value.get("result", value) if isinstance(value, dict) else value

    def acquire(self):
        data = self.cli(
            [
                "browser-run",
                "devtools",
                "browser",
                "create",
                "--keep-alive",
                "60000",
                "--recording=false",
                "--targets=false",
                "--body",
                json.dumps({"guardrails": {"allowedDomains": self.allowed}}),
            ]
        )
        self.session_id = str(UUID(data["sessionId"]))
        return f"wss://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/browser-rendering/devtools/browser/{self.session_id}"

    def close(self):
        if self.session_id:
            self.cli(["browser-run", "devtools", "browser", "delete", self.session_id, "--force"])
            self.session_id = None


def owned_get(http, origin, path, trial, extra=""):
    if origin not in (OBSERVER, DENIED):
        raise GateError("OWNED_ROUTE_REQUIRED")
    r = http.get(origin + path + "?trial=" + trial + extra, timeout=15, allow_redirects=False)
    r.raise_for_status()
    return r.json()


def guardrail(response):
    return bool(
        response
        and response.status == 403
        and response.headers.get("cf-mitigated") == "guardrails"
        and response.headers.get("cf-brapi-guardrails-reason") == "not-in-allowlist"
    )


def check_dns_fault(context):
    # Isolate the Chromium error document; a pending chrome-error navigation must
    # never interrupt subsequent route verification in the healthy observer tab.
    page = context.new_page()
    result = {"passed": False, "page_closed": False}
    try:
        response = page.goto("https://egress-dns-probe.invalid/", wait_until="load", timeout=8000)
        result["http_status"] = response.status if response else None
        result["passed"] = bool(response and response.status in (502, 523))
    except Exception as error:
        match = re.search(r"net::(ERR_[A-Z_]+)", str(error))
        result["network_code"] = match.group(1) if match else "UNCLASSIFIED"
        result["resolver_diagnostic"] = "NOT_OBSERVABLE_FROM_MANAGED_BROWSER"
        result["passed"] = result["network_code"] in (
            "ERR_NAME_NOT_RESOLVED",
            "ERR_DNS_TIMED_OUT",
            "ERR_CONNECTION_RESET",
        )
    finally:
        try:
            page.close()
            result["page_closed"] = True
        except Exception:
            result["passed"] = False
    return result


def route_probe(browser, http, trial, local_identity, report):
    checks = report["checks"]
    report["phase"] = "REMOTE_CONTEXT"
    context = browser.new_context(service_workers="block", accept_downloads=False)
    page = context.new_page()
    page.set_default_timeout(15000)
    report["phase"] = "OBSERVER_CONTROL"
    before = owned_get(http, OBSERVER, "/counts", trial)["counts"]

    def totals(rows):
        return {r["bucket"]: r["total"] for r in rows}

    # Positive receiving-end control: denied host is reachable without guardrails.
    owned_get(http, DENIED, "/observe", trial, "&bucket=forbidden")
    baseline = totals(owned_get(http, OBSERVER, "/counts", trial)["counts"])
    checks["observer_control"] = (
        baseline.get("forbidden", 0) == totals(before).get("forbidden", 0) + 1
    )
    r = page.goto(OBSERVER + "/identity?trial=" + trial, wait_until="domcontentloaded")
    identity = r.json() if r and r.status == 200 else {}
    checks["remote_source"] = bool(
        identity.get("cloudflare_egress")
        and identity.get("source_hash") != local_identity["source_hash"]
    )
    r = page.goto(
        OBSERVER + "/observe?trial=" + trial + "&bucket=allowed", wait_until="domcontentloaded"
    )
    checks["allowed_origin"] = bool(r and r.status == 200 and r.json().get("cloudflare_egress"))
    report["phase"] = "DENIED_NAVIGATION"
    checks["guardrails_navigation"] = guardrail(
        page.goto(
            DENIED + "/observe?trial=" + trial + "&bucket=forbidden", wait_until="domcontentloaded"
        )
    )
    report["phase"] = "DENIED_REDIRECT"
    checks["guardrails_redirect"] = guardrail(
        page.goto(OBSERVER + "/redirect?trial=" + trial, wait_until="domcontentloaded")
    )
    report["phase"] = "DENIED_SUBRESOURCE"
    page.goto(OBSERVER + "/probe-page?trial=" + trial, wait_until="domcontentloaded")
    with page.expect_response(lambda r: r.url.startswith(DENIED + "/observe")) as response:
        page.evaluate(
            '(url)=>{const img=document.createElement("img");img.src=url;document.body.append(img)}',
            DENIED + "/observe?trial=" + trial + "&bucket=subresource",
        )
    checks["guardrails_subresource"] = guardrail(response.value)
    report["phase"] = "DENIED_WORKER"
    worker_result = page.evaluate(
        """async (urls) => {
        const code = `let violation=false;self.addEventListener('securitypolicyviolation',()=>{violation=true});
          self.onmessage=async(e)=>{let control=false,denied='unknown';
            try{control=(await fetch(e.data[0])).status===200}catch(e){}
            try{const r=await fetch(e.data[1],{mode:'no-cors'});denied=r.type==='opaque'?'opaque':'visible'}catch(e){denied='failed'}
            postMessage({control,denied,violation});}`;
        const worker=new Worker(URL.createObjectURL(new Blob([code],{type:'text/javascript'})));
        return await new Promise(resolve=>{
          const timer=setTimeout(()=>{worker.terminate();resolve({control:false,denied:'timeout',violation:false})},8000);
          worker.onmessage=e=>{clearTimeout(timer);worker.terminate();resolve(e.data)};
          worker.onerror=()=>{clearTimeout(timer);worker.terminate();resolve({control:false,denied:'worker-error',violation:true})};
          worker.postMessage(urls);
        });
    }""",
        [
            OBSERVER + "/observe?trial=" + trial + "&bucket=worker-control",
            DENIED + "/observe?trial=" + trial + "&bucket=worker",
        ],
    )
    worker_counts = totals(owned_get(http, OBSERVER, "/counts", trial)["counts"])
    checks["guardrails_worker"] = bool(
        worker_result.get("control")
        and worker_result.get("denied") in ("opaque", "failed")
        and not worker_result.get("violation")
        and worker_counts.get("worker-control", 0) == baseline.get("worker-control", 0) + 1
        and worker_counts.get("worker", 0) == baseline.get("worker", 0)
    )
    report["worker_check_method"] = "allowed_control_plus_receiving_counter_and_no_csp_violation"
    report["phase"] = "DNS_FAILURE"
    dns = check_dns_fault(context)
    report["dns_probe"] = dns
    checks["unresolvable_host_fail_closed"] = dns["passed"]
    # Recheck route after an injected network failure.
    response = page.goto(OBSERVER + "/identity?trial=" + trial, wait_until="domcontentloaded")
    checks["remote_source"] = checks["remote_source"] and response.json().get(
        "cloudflare_egress", False
    )
    context.close()
    quiet = browser.new_context(
        java_script_enabled=False, service_workers="block", accept_downloads=False
    )
    report["phase"] = "RESPONSE_INTERCEPTION"
    p = quiet.new_page()
    doc_gate = install_document_gate(quiet, p, OBSERVER + "/script-check?trial=" + trial)
    p.goto(OBSERVER + "/script-check?trial=" + trial, wait_until="load")
    checks["response_interception"] = doc_gate.sent == 1 and doc_gate.response_status == 200
    checks["javascript_disabled"] = p.locator("body").get_attribute("data-executed") == "no"
    redirect_page = quiet.new_page()
    redirect_gate = install_document_gate(
        quiet, redirect_page, OBSERVER + "/redirect-self?trial=" + trial
    )
    try:
        redirect_page.goto(
            OBSERVER + "/redirect-self?trial=" + trial, wait_until="load", timeout=10000
        )
    except Exception:
        pass
    checks["same_host_redirect_blocked"] = (
        redirect_gate.redirect_blocked and redirect_gate.sent == 1
    )
    quiet.close()
    checks["context_cleanup"] = True
    after = totals(owned_get(http, OBSERVER, "/counts", trial)["counts"])
    checks["forbidden_count_unchanged"] = all(
        after.get(b, 0) == baseline.get(b, 0)
        for b in ("forbidden", "subresource", "worker", "redirect")
    )
    return checks


class DocumentGate:
    """Remote Chromium Fetch interception at both request and response stages."""

    def __init__(self, cdp, target, main_frame):
        self.cdp, self.target, self.main_frame = cdp, target, main_frame
        self.sent, self.aborted, self.network_bytes = 0, 0, 0
        self.redirect_blocked, self.response_status = False, None
        self.stopped = False

    def handle(self, event):
        request_id = event["requestId"]
        if self.stopped:
            self.aborted += 1
            self.cdp.send("Fetch.failRequest", {"requestId": request_id, "errorReason": "Aborted"})
            return
        if "responseStatusCode" in event or "responseErrorReason" in event:
            status = event.get("responseStatusCode")
            self.response_status = status
            if status is None or 300 <= status < 400:
                self.redirect_blocked = status is not None and 300 <= status < 400
                self.aborted += 1
                self.cdp.send(
                    "Fetch.failRequest", {"requestId": request_id, "errorReason": "Aborted"}
                )
            else:
                self.cdp.send("Fetch.continueResponse", {"requestId": request_id})
        elif (
            event["request"]["url"] == self.target
            and event.get("resourceType") == "Document"
            and event.get("frameId") == self.main_frame
            and self.sent == 0
        ):
            self.sent += 1
            self.cdp.send(
                "Fetch.continueRequest", {"requestId": request_id, "interceptResponse": True}
            )
        else:
            self.aborted += 1
            self.cdp.send(
                "Fetch.failRequest", {"requestId": request_id, "errorReason": "BlockedByClient"}
            )


def install_document_gate(context, page, url):
    cdp = context.new_cdp_session(page)
    frame = cdp.send("Page.getFrameTree")["frameTree"]["frame"]["id"]
    gate = DocumentGate(cdp, url, frame)
    cdp.on("Fetch.requestPaused", gate.handle)

    def received(event):
        gate.network_bytes += int(event.get("encodedDataLength", 0))

    cdp.on("Network.loadingFinished", received)
    cdp.send("Network.enable")
    cdp.send(
        "Fetch.enable",
        {
            "patterns": [
                {"urlPattern": "*", "requestStage": "Request"},
                {"urlPattern": "*", "requestStage": "Response"},
            ]
        },
    )
    return gate


def target_probe(browser, state, now, trial, local_identity, result):
    context, gate, reserved = None, None, False
    result.update(
        status="STOPPED",
        reason="CANARY_NOT_COMPLETED",
        requests_sent=0,
        details_fetched=0,
        javascript_enabled=False,
        retries=0,
    )
    try:
        context = browser.new_context(
            java_script_enabled=False, service_workers="block", accept_downloads=False
        )
        page = context.new_page()
        response = page.goto(
            OBSERVER + "/identity?trial=" + trial, wait_until="domcontentloaded", timeout=15000
        )
        identity = response.json()
        if (
            not identity.get("cloudflare_egress")
            or identity.get("source_hash") == local_identity["source_hash"]
        ):
            raise GateError("REMOTE_ROUTE_CHANGED")
        gate = install_document_gate(context, page, TARGET_URL)
        if not state.reserve_target(now):
            raise GateError("TARGET_ALREADY_ATTEMPTED")
        reserved = True
        try:
            response = page.goto(TARGET_URL, wait_until="load", timeout=20000)
            status = response.status if response else None
            result["http_status"] = status
            if status in (403, 429):
                result.update(status="BLOCKED", reason="HTTP_BLOCK")
            elif status != 200:
                result.update(status="STOPPED", reason="UNEXPECTED_STATUS")
            else:
                from funda_scraper.html import listing_links
                from funda_scraper.errors import BlockedError, ParseError

                html = page.content()
                result["html_bytes_in_memory"] = len(html.encode())
                try:
                    result.update(
                        status="PASS",
                        reason="RECOGNIZED_SEARCH",
                        discovered=len(listing_links(html)),
                    )
                except BlockedError:
                    result.update(status="BLOCKED", reason="CAPTCHA")
                except ParseError:
                    result.update(status="STOPPED", reason="UNRECOGNIZED_HTML")
                del html
        except Exception:
            result.update(
                status="STOPPED",
                reason="REDIRECT_BLOCKED" if gate.redirect_blocked else "NAVIGATION_FAILED",
            )
    except Exception as error:
        result.update(
            status="STOPPED",
            reason=str(error) if isinstance(error, GateError) else "REMOTE_TARGET_SETUP_FAILED",
        )
    finally:
        if gate:
            gate.stopped = True
        result.update(
            requests_sent=gate.sent if gate else 0,
            requests_aborted=gate.aborted if gate else 0,
            network_bytes=gate.network_bytes if gate else 0,
            redirect_blocked=gate.redirect_blocked if gate else False,
        )
        if gate and gate.response_status is not None:
            result["http_status"] = gate.response_status
        result["context_closed"] = context is None
        if context:
            try:
                context.close()
                result["context_closed"] = True
            except Exception:
                if result["status"] != "BLOCKED":
                    result.update(status="STOPPED", reason="CONTEXT_CLEANUP_FAILED")
        result["state_saved"] = not reserved
        if reserved:
            try:
                result["state_saved"] = True
                state.save_target(result)
            except Exception:
                result["state_saved"] = False
                if result["status"] != "BLOCKED":
                    result.update(status="STOPPED", reason="STATE_WRITE_FAILED")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canary", action="store_true")
    parser.add_argument("--verify-and-canary", action="store_true")
    parser.add_argument("--state", type=Path, default=LAB / ".cloudflare/remote-canary.sqlite")
    parser.add_argument("--gate", type=Path, default=LAB / "remote-route.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    combined = args.verify_and_canary
    wants_target = args.canary or combined
    now = datetime.now(timezone.utc)
    trial_config = json.loads((LAB / "egress-trial.json").read_text())
    trial = trial_config["trial"]
    if now >= datetime.fromisoformat(trial_config["expires_at"]):
        raise GateError("TRIAL_EXPIRED")
    if args.canary:
        valid_gate(json.loads(args.gate.read_text()), trial, code_hash(), now)
    token = sys.stdin.read().strip()
    if not token:
        raise GateError("AUTH_STDIN_REQUIRED")
    http = requests.Session()
    http.trust_env = False
    local_identity = owned_get(http, OBSERVER, "/identity", trial)
    result = {
        "provider": "cloudflare-browser-run",
        "trial": trial,
        "checked_at": now.isoformat(),
        "code_sha256": code_hash(),
        "mode": "verify-and-canary" if combined else ("canary" if args.canary else "route"),
        "status": "FAIL",
        "funda_requests": 0,
        "checks": {},
    }
    session = CloudSession(
        token,
        [urlsplit(OBSERVER).hostname, "egress-dns-probe.invalid"]
        + (["www.funda.nl"] if wants_target else []),
    )
    args.state.parent.mkdir(parents=True, exist_ok=True)
    with args.state.with_suffix(".lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with State(args.state) as state:
            if wants_target and state.last_target():
                raise GateError("TARGET_ALREADY_ATTEMPTED")
            if not state.reserve_browser(now, "canary" if wants_target else "qa"):
                raise GateError("BROWSER_DAILY_BUDGET")
            try:
                from playwright.sync_api import sync_playwright

                result["phase"] = "ACQUIRE"
                ws = session.acquire()
                result["phase"] = "CONNECT_CDP"
                with sync_playwright() as pw:
                    browser = pw.chromium.connect_over_cdp(
                        ws, headers={"Authorization": "Bearer " + token}, timeout=20000
                    )
                    if not args.canary:
                        route_probe(browser, http, trial, local_identity, result)
                    if wants_target:
                        if combined:
                            result["status"] = (
                                "PASS"
                                if REQUIRED_CHECKS <= result["checks"].keys()
                                and all(result["checks"].values())
                                else "FAIL"
                            )
                            valid_gate(result, trial, code_hash(), datetime.now(timezone.utc))
                            result["route_status"] = "PASS"
                        result["phase"] = "TARGET_CANARY"
                        result["canary"] = {}
                        target_probe(browser, state, now, trial, local_identity, result["canary"])
                        result["status"] = result["canary"]["status"]
                        result["funda_requests"] = result["canary"]["requests_sent"]
            except Exception as error:
                result["status"] = "STOPPED" if wants_target else "FAIL"
                result["error_type"] = type(error).__name__
                result["reason"] = (
                    str(error) if isinstance(error, GateError) else "REMOTE_EXECUTION_FAILED"
                )
            finally:
                try:
                    session.close()
                    result["checks"]["cleanup"] = True
                except Exception:
                    result["checks"]["cleanup"] = False
                http.close()
            if not wants_target:
                result["status"] = (
                    "PASS"
                    if REQUIRED_CHECKS <= result["checks"].keys() and all(result["checks"].values())
                    else "FAIL"
                )
            elif not result["checks"].get("cleanup"):
                result["status"] = "STOPPED"
            args.output.write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result, indent=2))
            if result["status"] != "PASS":
                raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except GateError as error:
        print(json.dumps({"status": "STOPPED", "reason": str(error)}))
        raise SystemExit(1)
