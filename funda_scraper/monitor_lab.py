"""Persistent incremental monitor for the owned synthetic test lab only.

This module deliberately cannot navigate to Funda. Canonical listing URLs are
identifiers; all HTTP requests go to the explicitly named lab origin.
"""

import argparse
import fcntl
import hashlib
import json
import os
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import requests

from funda_scraper.errors import BlockedError, ParseError
from funda_scraper.extract import DataExtractor
from funda_scraper.html import check_page, json_objects, listing_links
from funda_scraper.preprocess import clean_living_area, clean_price
from funda_scraper.searchrequest import SearchRequest


class SafetyError(ValueError):
    """The requested destination is not an owned test endpoint."""


@dataclass(frozen=True)
class LabConfig:
    origin: str
    allow_local: bool = False
    daily_session_limit: int = 3
    daily_page_limit: int = 25
    daily_detail_limit: int = 10

    def validate(self):
        parts = urlsplit(self.origin)
        local = (
            self.allow_local
            and parts.scheme == "http"
            and parts.hostname in ("127.0.0.1", "localhost")
        )
        remote = parts.scheme == "https" and parts.hostname == LAB_HOST
        if not (local or remote) or parts.username or parts.password:
            raise SafetyError("Only the owned lab origin is allowed.")
        if parts.path not in ("", "/") or parts.query or parts.fragment:
            raise SafetyError("Expected an origin without a path, query or fragment.")
        if not local and parts.port not in (None, 443):
            raise SafetyError("Unexpected lab port.")
        for value, cap in zip(
            (self.daily_session_limit, self.daily_page_limit, self.daily_detail_limit), (3, 25, 10)
        ):
            if type(value) is not int or not 1 <= value <= cap:
                raise SafetyError("Budgets must stay within the hard daily caps 3/25/10.")


# Set to the actual owned deployment hostname after deployment, never a wildcard.
LAB_HOST = "funda-monitor-lab.maartenjr-esser.workers.dev"


@dataclass(frozen=True)
class Document:
    status: int
    html: str


class HTTPSource:
    """No redirects, ambient proxies, retries, cookies on disk or external URLs."""

    def __init__(self, config):
        config.validate()
        self.origin = config.origin.rstrip("/")
        self.session = requests.Session()
        self.session.trust_env = False

    def __call__(self, url):
        if not url.startswith(self.origin + "/"):
            raise SafetyError("Request escaped the lab origin.")
        with self.session.get(url, timeout=(5, 15), allow_redirects=False, stream=True) as response:
            if response.status_code in (403, 429):
                return Document(response.status_code, "")
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 2_000_000:
                    raise ValueError("Lab response too large.")
            return Document(response.status_code, data.decode("utf-8"))

    def close(self):
        self.session.close()


class Monitor:
    def __init__(self, path, config, fetch):
        config.validate()
        self.path = Path(path)
        self.config, self.fetch = config, fetch
        self.db = sqlite3.connect(path, timeout=2)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS daily (
                day TEXT PRIMARY KEY, sessions INTEGER DEFAULT 0,
                pages INTEGER DEFAULT 0, details INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS seen (url TEXT PRIMARY KEY, fingerprint TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS pending (url TEXT PRIMARY KEY, fingerprint TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS records (url TEXT PRIMARY KEY, payload TEXT NOT NULL);
        """)
        stored = self.db.execute("SELECT value FROM meta WHERE key='origin'").fetchone()
        if stored and stored[0] != config.origin.rstrip("/"):
            self.db.close()
            raise SafetyError("State belongs to a different origin.")
        self.db.execute(
            "INSERT OR IGNORE INTO meta VALUES ('origin', ?)", (config.origin.rstrip("/"),)
        )
        self.db.commit()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    def _reserve(self, day, kind, limit):
        if self._clock().astimezone(ZoneInfo("Europe/Amsterdam")).date().isoformat() != day:
            self._rollover = True
            return False
        # Independent atomic reservation remains spent even after a failed fetch.
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO daily (day) VALUES (?)", (day,))
            return bool(
                self.db.execute(
                    f"UPDATE daily SET {kind}={kind}+1 WHERE day=? AND {kind} < ?", (day, limit)
                ).rowcount
            )

    def _document(self, path, day):
        if not self._reserve(day, "pages", self.config.daily_page_limit):
            return None
        try:
            document = self.fetch(self.config.origin.rstrip("/") + path)
        except (requests.RequestException, ValueError, OSError):
            raise ParseError("TRANSPORT_FAILED") from None
        if document.status in (403, 429):
            raise BlockedError("HTTP_BLOCK")
        check_page(document.html)
        if document.status != 200:
            raise ParseError("HTTP_NOT_OK")
        return document.html

    def run(self, now=None, scenario="initial"):
        # A separate lock file avoids interference with SQLite's own file locks.
        # No stale lease survives process death. This lab runner targets Linux/macOS.
        with self.path.with_suffix(self.path.suffix + ".run.lock").open("a+b") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return dict(
                    status="BUSY",
                    reason="RUN_IN_PROGRESS",
                    source_mode="synthetic",
                    funda_enabled=False,
                )
            try:
                started = time.monotonic()
                now = now or datetime.now(timezone.utc)
                self._clock = lambda: now + timedelta(seconds=time.monotonic() - started)
                self._rollover = False
                return self._run(now, scenario)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _run(self, now, scenario):
        if scenario not in (
            "initial",
            "new",
            "changed",
            "empty",
            "blocked",
            "rate",
            "captcha",
            "unknown",
            "redirect",
        ):
            raise SafetyError("Unknown synthetic scenario.")
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("An aware timestamp is required.")
        day = now.astimezone(ZoneInfo("Europe/Amsterdam")).date().isoformat()
        result = dict(
            status="COMPLETE",
            source_mode="synthetic",
            funda_enabled=False,
            baseline_items=0,
            new_items=0,
            changed_items=0,
            discovered=0,
            details_fetched=0,
            valid_records=0,
            deferred=0,
            timestamp=now.isoformat(),
            scenario=scenario,
        )
        if self.db.execute("SELECT 1 FROM meta WHERE key='paused'").fetchone():
            return dict(result, status="PAUSED", reason="PERSISTENT_BLOCK")
        if not self._reserve(day, "sessions", self.config.daily_session_limit):
            return dict(result, status="BUDGET_LIMIT", reason="DAILY_SESSIONS")
        try:
            html = self._document("/zoeken/koop?scenario=" + scenario, day)
            if html is None:
                result.update(status="BUDGET_LIMIT", reason="DAILY_PAGES")
            else:
                urls = listing_links(html)
                result["discovered"] = len(urls)
                soup = check_page(html)
                cards = {}
                for obj in json_objects(soup):
                    if obj.get("url") in urls:
                        value = {k: obj[k] for k in ("url", "name", "offers") if k in obj}
                        cards[obj["url"]] = value
                baseline = not self.db.execute("SELECT 1 FROM meta WHERE key='baseline'").fetchone()
                with self.db:
                    for url in urls:
                        fingerprint = hashlib.sha256(
                            json.dumps(cards.get(url, {"url": url}), sort_keys=True).encode()
                        ).hexdigest()
                        old = self.db.execute(
                            "SELECT fingerprint FROM seen WHERE url=?", (url,)
                        ).fetchone()
                        if baseline:
                            self.db.execute(
                                "INSERT OR REPLACE INTO seen VALUES (?,?)", (url, fingerprint)
                            )
                            result["baseline_items"] += 1
                        elif not old or old[0] != fingerprint:
                            self.db.execute(
                                "INSERT OR REPLACE INTO pending VALUES (?,?)", (url, fingerprint)
                            )
                            result["new_items" if not old else "changed_items"] += 1
                    self.db.execute("INSERT OR IGNORE INTO meta VALUES ('baseline','1')")
                if not baseline:
                    for url, fingerprint in self.db.execute(
                        "SELECT url,fingerprint FROM pending ORDER BY url"
                    ).fetchall():
                        pages = self.db.execute(
                            "SELECT pages FROM daily WHERE day=?", (day,)
                        ).fetchone()[0]
                        if pages >= self.config.daily_page_limit:
                            break
                        if not self._reserve(day, "details", self.config.daily_detail_limit):
                            break
                        result["details_fetched"] += 1
                        page = self._document(urlsplit(url).path + "?scenario=" + scenario, day)
                        if page is None:
                            break
                        house = DataExtractor().extract_data_from_detail_page(
                            page, SearchRequest("lab", "buy"), expected_url=url
                        )
                        record = {
                            "url": house.url,
                            "address": house.address,
                            "price": clean_price(house.price),
                            "living_area": clean_living_area(house.living_area),
                            "observed_at": now.isoformat(),
                            "synthetic": True,
                        }
                        if record["price"] <= 0 or record["living_area"] <= 0:
                            raise ParseError("INCOMPLETE_DETAIL")
                        with self.db:
                            self.db.execute(
                                "INSERT OR REPLACE INTO records VALUES (?,?)",
                                (url, json.dumps(record)),
                            )
                            self.db.execute(
                                "INSERT OR REPLACE INTO seen VALUES (?,?)", (url, fingerprint)
                            )
                            self.db.execute("DELETE FROM pending WHERE url=?", (url,))
                        result["valid_records"] += 1
        except BlockedError:
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO meta VALUES ('paused','block')")
            result.update(status="BLOCKED", reason="BLOCK_SIGNAL")
        except (ParseError, TypeError, KeyError, ValueError) as error:
            reason = (
                str(error)
                if str(error) in ("TRANSPORT_FAILED", "HTTP_NOT_OK", "INCOMPLETE_DETAIL")
                else "UNRECOGNIZED_PAGE"
            )
            result.update(status="FAILED", reason=reason)
        result["deferred"] = self.db.execute("SELECT count(*) FROM pending").fetchone()[0]
        if result["deferred"] and result["status"] == "COMPLETE":
            result.update(status="PARTIAL", reason="DAILY_BUDGET")
        if self._rollover:
            result.update(status="PARTIAL", reason="DAY_ROLLOVER")
        return result

    def records(self):
        return [
            json.loads(r[0]) for r in self.db.execute("SELECT payload FROM records ORDER BY url")
        ]

    def export(self, target):
        target = Path(target)
        fd, name = tempfile.mkstemp(dir=target.parent, prefix=".monitor-", suffix=".json")
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump(self.records(), stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, target)
        finally:
            if os.path.exists(name):
                os.unlink(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--scenario", default="initial")
    args = parser.parse_args()
    config = LabConfig(args.origin)
    source = HTTPSource(config)
    try:
        with Monitor(args.db, config, source) as monitor:
            print(json.dumps(monitor.run(scenario=args.scenario), indent=2))
    finally:
        source.close()


if __name__ == "__main__":
    main()
