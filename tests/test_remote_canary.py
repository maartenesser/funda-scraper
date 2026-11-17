"""Policy/state regression tests; never connect to Funda or a browser."""

from datetime import datetime, timedelta, timezone
import pytest
from scripts.remote_canary import (
    State,
    valid_gate,
    allowed_target,
    TARGET_URL,
    GateError,
    REQUIRED_CHECKS,
)

NOW = datetime(2026, 11, 17, 18, tzinfo=timezone.utc)


def test_only_exact_first_search_document_is_allowed():
    assert allowed_target(TARGET_URL, "document", True, 0)
    assert not allowed_target(TARGET_URL, "document", True, 1)
    assert not allowed_target(TARGET_URL + "&search_result=2", "document", True, 0)
    assert not allowed_target("https://funda.nl/", "document", True, 0)
    assert not allowed_target("https://www.funda.nl/tracker.js", "script", False, 0)
    assert not allowed_target("http://127.0.0.1/", "document", True, 0)


def test_daily_remote_browser_attempt_cap_survives_restart(tmp_path):
    path = tmp_path / "s.sqlite"
    for i in range(3):
        with State(path) as state:
            assert state.reserve_browser(NOW)
    with State(path) as state:
        assert not state.reserve_browser(NOW)


def test_canary_reservation_is_spent_before_navigation(tmp_path):
    path = tmp_path / "s.sqlite"
    with State(path) as s:
        assert s.reserve_target(NOW)
    with State(path) as s:
        assert not s.reserve_target(NOW + timedelta(days=1))


def test_saved_stop_blocks_future_canary(tmp_path):
    path = tmp_path / "s.sqlite"
    with State(path) as s:
        s.save_target({"status": "BLOCKED", "reason": "HTTP403"})
    with State(path) as s:
        assert not s.reserve_target(NOW)
        assert s.last_target()["status"] == "BLOCKED"


def test_gate_requires_every_measured_check_and_fresh_matching_code():
    g = {
        "status": "PASS",
        "provider": "cloudflare-browser-run",
        "trial": "trial",
        "checked_at": NOW.isoformat(),
        "code_sha256": "abc",
        "checks": {name: True for name in REQUIRED_CHECKS},
    }
    assert valid_gate(g, "trial", "abc", NOW)
    for patch in (
        {"status": "FAIL"},
        {"checks": {}},
        {"checks": {"guardrails": False}},
        {"code_sha256": "stale"},
        {"trial": "other"},
        {"checked_at": (NOW - timedelta(hours=1)).isoformat()},
    ):
        with pytest.raises(GateError):
            valid_gate({**g, **patch}, "trial", "abc", NOW)


def test_response_gate_aborts_redirect_before_follow():
    from scripts.remote_canary import DocumentGate

    class CDP:
        def __init__(self):
            self.calls = []

        def send(self, method, args):
            self.calls.append((method, args))

    cdp = CDP()
    gate = DocumentGate(cdp, TARGET_URL, "main")
    gate.handle(
        {
            "requestId": "one",
            "request": {"url": TARGET_URL},
            "resourceType": "Document",
            "frameId": "main",
        }
    )
    assert gate.sent == 1
    gate.handle(
        {
            "requestId": "one",
            "request": {"url": TARGET_URL},
            "resourceType": "Document",
            "frameId": "main",
            "responseStatusCode": 302,
        }
    )
    assert gate.redirect_blocked
    assert cdp.calls[-1][0] == "Fetch.failRequest"
    gate.handle(
        {
            "requestId": "two",
            "request": {"url": TARGET_URL},
            "resourceType": "Document",
            "frameId": "main",
        }
    )
    assert gate.sent == 1 and cdp.calls[-1][0] == "Fetch.failRequest"


def test_target_counts_survive_context_and_state_cleanup_errors():
    from scripts.remote_canary import target_probe

    class CDP:
        def send(self, method, args=None):
            if method == "Page.getFrameTree":
                return {"frameTree": {"frame": {"id": "main"}}}

        def on(self, name, callback):
            if name == "Fetch.requestPaused":
                self.callback = callback

    class Response:
        status = 403

        def json(self):
            return {"cloudflare_egress": True, "source_hash": "remote"}

    class Page:
        def __init__(self, cdp):
            self.cdp = cdp

        def goto(self, url, **kwargs):
            if url == TARGET_URL:
                self.cdp.callback(
                    {
                        "requestId": "one",
                        "request": {"url": url},
                        "resourceType": "Document",
                        "frameId": "main",
                    }
                )
            return Response()

    class Context:
        def __init__(self):
            self.cdp = CDP()
            self.closed = False

        def new_page(self):
            return Page(self.cdp)

        def new_cdp_session(self, page):
            return self.cdp

        def close(self):
            self.closed = True
            raise RuntimeError("synthetic close failure")

    context = Context()

    class Browser:
        def new_context(self, **kwargs):
            return context

    class BadState:
        def reserve_target(self, now):
            return True

        def save_target(self, result):
            raise RuntimeError("synthetic disk failure")

    result = {}
    target_probe(Browser(), BadState(), NOW, "trial", {"source_hash": "local"}, result)
    assert context.closed
    assert result["requests_sent"] == 1
    assert result["status"] == "BLOCKED"
    assert result["context_closed"] is False
    assert result["state_saved"] is False


@pytest.mark.parametrize("gate_passes", [False, True, "gate-error"])
def test_combined_mode_never_calls_target_before_live_gate(tmp_path, monkeypatch, gate_passes):
    import io
    import sys
    from types import ModuleType, SimpleNamespace
    from scripts import remote_canary as module

    calls = []

    class FakeDate(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(module, "datetime", FakeDate)
    monkeypatch.setattr(sys, "stdin", io.StringIO("synthetic-test-only"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "remote_canary",
            "--verify-and-canary",
            "--state",
            str(tmp_path / "state.sqlite"),
            "--output",
            str(tmp_path / "out.json"),
        ],
    )

    class Session:
        def __init__(self, *args):
            pass

        def acquire(self):
            return "wss://api.cloudflare.com/test-session"

        def close(self):
            calls.append("closed")

    monkeypatch.setattr(module, "CloudSession", Session)
    monkeypatch.setattr(module, "owned_get", lambda *args, **kwargs: {"source_hash": "local"})

    class Playwright:
        def __enter__(self):
            return SimpleNamespace(
                chromium=SimpleNamespace(connect_over_cdp=lambda *args, **kwargs: object())
            )

        def __exit__(self, *args):
            pass

    parent = ModuleType("playwright")
    child = ModuleType("playwright.sync_api")
    child.sync_playwright = Playwright
    monkeypatch.setitem(sys.modules, "playwright", parent)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", child)

    def route(*args):
        report = args[-1]
        report["checks"] = {name: True for name in REQUIRED_CHECKS}
        if gate_passes is False:
            report["checks"]["guardrails_worker"] = False

    monkeypatch.setattr(module, "route_probe", route)
    if gate_passes == "gate-error":

        def bad_gate(*args):
            raise GateError("REMOTE_GATE_NOT_PASSED")

        monkeypatch.setattr(module, "valid_gate", bad_gate)

    def target(*args):
        calls.append("target")
        args[-1].update(status="BLOCKED", requests_sent=1)

    monkeypatch.setattr(module, "target_probe", target)
    with pytest.raises(SystemExit):
        module.main()
    import json

    report = json.loads((tmp_path / "out.json").read_text())
    assert ("target" in calls) == (gate_passes is True)
    assert report["funda_requests"] == (1 if gate_passes is True else 0)
    assert report["status"] != "PASS"
    assert "closed" in calls


def test_qa_and_canary_start_limits_are_separate_and_durable(tmp_path):
    path = tmp_path / "quota.sqlite"
    with State(path) as state:
        for _ in range(3):
            assert state.reserve_browser(NOW, "qa")
        assert not state.reserve_browser(NOW, "qa")
        assert state.reserve_browser(NOW, "canary")
        assert state.reserve_browser(NOW, "canary")
    with State(path) as state:
        assert not state.reserve_browser(NOW, "canary")
        assert not state.reserve_browser(NOW, "qa")


@pytest.mark.parametrize("code", ["ERR_NAME_NOT_RESOLVED", "ERR_CONNECTION_RESET"])
def test_dns_error_uses_and_closes_its_own_page(code):
    from scripts.remote_canary import check_dns_fault

    class Page:
        closed = False

        def goto(self, *args, **kwargs):
            raise RuntimeError("net::" + code)

        def close(self):
            self.closed = True

    page = Page()

    class Context:
        def new_page(self):
            return page

    result = check_dns_fault(Context())
    assert page.closed and result["passed"] and result["page_closed"]
    assert result["network_code"] == code
