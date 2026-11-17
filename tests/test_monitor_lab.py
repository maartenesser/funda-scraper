"""Synthetic-only monitor regression tests. No Funda network traffic."""

import json
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit

import pytest
from funda_scraper.monitor_lab import LabConfig, Monitor, Document, SafetyError

ORIGIN = "http://127.0.0.1:8765"
URL1 = "https://www.funda.nl/detail/koop/lab/huis-teststraat-1/10000001/"
URL2 = "https://www.funda.nl/detail/koop/lab/huis-teststraat-2/10000002/"
NOW = datetime(2026, 11, 17, 8, 0, tzinfo=timezone.utc)


def ld(value):
    return '<script type="application/ld+json">' + json.dumps(value) + "</script>"


def search(urls, price=500000):
    return ld(
        {
            "@type": "ItemList",
            "itemListElement": [
                {
                    "url": u,
                    "name": "Synthetic home",
                    "offers": {"price": price, "priceCurrency": "EUR"},
                }
                for u in urls
            ],
        }
    )


def detail(url, price=500000, area=100):
    return ld(
        {
            "@type": "House",
            "url": url,
            "address": {"streetAddress": "Teststraat", "addressLocality": "lab"},
            "offers": {"price": price, "priceCurrency": "EUR"},
            "floorSize": {"value": area},
        }
    )


class FakeSource:
    def __init__(self):
        self.urls = [URL1]
        self.price = 500000
        self.calls = []
        self.status = 200
        self.html = None

    def __call__(self, url):
        assert urlsplit(url).netloc == "127.0.0.1:8765", "external request escaped"
        self.calls.append(url)
        if self.html is not None:
            return Document(self.status, self.html)
        if self.status != 200:
            return Document(self.status, "error")
        if "/zoeken/" in url:
            return Document(200, search(self.urls, self.price))
        source = URL2 if "10000002" in url else URL1
        return Document(200, detail(source, self.price))


@pytest.fixture
def source():
    return FakeSource()


@pytest.fixture
def config():
    return LabConfig(origin=ORIGIN, allow_local=True)


def test_real_source_is_rejected_before_fetch(tmp_path, source):
    with pytest.raises(SafetyError):
        Monitor(tmp_path / "state.sqlite", LabConfig(origin="https://www.funda.nl"), source)
    assert source.calls == []


def test_baseline_then_unchanged_never_fetches_details(tmp_path, config, source):
    with Monitor(tmp_path / "s.sqlite", config, source) as m:
        assert m.run(NOW)["baseline_items"] == 1
        assert m.run(NOW)["details_fetched"] == 0
        assert m.run(NOW)["details_fetched"] == 0
    assert len(source.calls) == 3
    assert all("/zoeken/" in u for u in source.calls)


def test_new_item_fetches_exactly_once(tmp_path, config, source):
    with Monitor(tmp_path / "s.sqlite", config, source) as m:
        m.run(NOW)
        source.urls = [URL1, URL2]
        result = m.run(NOW)
        assert result["new_items"] == 1
        assert result["details_fetched"] == 1
        assert result["valid_records"] == 1
        assert m.run(NOW)["details_fetched"] == 0
    assert sum("/detail/" in u for u in source.calls) == 1


def test_changed_card_fetches_one_new_observation(tmp_path, config, source):
    with Monitor(tmp_path / "s.sqlite", config, source) as m:
        m.run(NOW)
        source.price = 510000
        r = m.run(NOW)
        assert r["changed_items"] == 1
        assert r["details_fetched"] == 1
        assert m.records()[0]["price"] == 510000


def test_known_promoted_card_does_not_hide_new_item(tmp_path, config, source):
    with Monitor(tmp_path / "s.sqlite", config, source) as m:
        m.run(NOW)
        source.urls = [URL1, URL1, URL2]
        r = m.run(NOW)
        assert r["discovered"] == 2
        assert r["new_items"] == 1


def test_page_budget_preserves_backlog(tmp_path, source):
    config = LabConfig(origin=ORIGIN, allow_local=True, daily_page_limit=2)
    with Monitor(tmp_path / "s.sqlite", config, source) as m:
        m.run(NOW)
        source.urls = [URL1, URL2]
        r = m.run(NOW)
        assert r["deferred"] == 1
        assert r["details_fetched"] == 0
        assert len(source.calls) == 2
        r = m.run(NOW + timedelta(days=1))
        assert r["details_fetched"] == 1
        assert r["deferred"] == 0


@pytest.mark.parametrize("status", [403, 429])
def test_block_persists_across_restart_and_day(tmp_path, config, source, status):
    path = tmp_path / "s.sqlite"
    source.status = status
    with Monitor(path, config, source) as m:
        assert m.run(NOW)["status"] == "BLOCKED"
    source.status = 200
    with Monitor(path, config, source) as m:
        assert m.run(NOW + timedelta(days=1))["status"] == "PAUSED"
    assert len(source.calls) == 1


def test_captcha200_stops_without_followup(tmp_path, config, source):
    source.html = "<title>Je bent bijna op de pagina die je zoekt [funda]</title>"
    with Monitor(tmp_path / "s.sqlite", config, source) as m:
        assert m.run(NOW)["status"] == "BLOCKED"
    assert len(source.calls) == 1


def test_unknown_html_is_not_zero_success(tmp_path, config, source):
    source.html = "<html>unknown</html>"
    with Monitor(tmp_path / "s.sqlite", config, source) as m:
        r = m.run(NOW)
        assert r["status"] == "FAILED"
        assert r["reason"] == "UNRECOGNIZED_PAGE"


def test_session_budget_is_durable(tmp_path, config, source):
    path = tmp_path / "s.sqlite"
    for i in range(4):
        with Monitor(path, config, source) as m:
            r = m.run(NOW)
    assert r["status"] == "BUDGET_LIMIT"
    assert len(source.calls) == 3


def test_nl_calendar_day_resets_at_local_midnight(tmp_path, config, source):
    before = datetime(2026, 11, 17, 22, 59, tzinfo=timezone.utc)
    after = datetime(2026, 11, 17, 23, 1, tzinfo=timezone.utc)
    with Monitor(tmp_path / "s.sqlite", config, source) as m:
        for i in range(3):
            m.run(before)
        assert m.run(after)["status"] == "COMPLETE"


def test_atomic_export_keeps_previous_on_replace_failure(tmp_path, config, source, monkeypatch):
    target = tmp_path / "report.json"
    target.write_text("previous")
    with Monitor(tmp_path / "s.sqlite", config, source) as m:
        m.run(NOW)

        def fail(*args):
            raise OSError("synthetic disk failure")

        monkeypatch.setattr("funda_scraper.monitor_lab.os.replace", fail)
        with pytest.raises(OSError):
            m.export(target)
    assert target.read_text() == "previous"


def test_crash_after_commit_does_not_duplicate(tmp_path, config, source):
    path = tmp_path / "s.sqlite"
    with Monitor(path, config, source) as m:
        m.run(NOW)
    source.urls = [URL1, URL2]
    with Monitor(path, config, source) as m:
        m.run(NOW)
    with Monitor(path, config, source) as m:
        assert m.run(NOW)["details_fetched"] == 0
        assert len(m.records()) == 1


def test_foreign_redirect_fails_without_following(tmp_path, config, source):
    source.status = 302
    with Monitor(tmp_path / "s.sqlite", config, source) as m:
        assert m.run(NOW)["status"] == "FAILED"
    assert len(source.calls) == 1


@pytest.mark.parametrize(
    "field,value",
    [("daily_session_limit", 4), ("daily_page_limit", 26), ("daily_detail_limit", 11)],
)
def test_configuration_cannot_raise_hard_caps(field, value):
    with pytest.raises(SafetyError):
        LabConfig(origin=ORIGIN, allow_local=True, **{field: value}).validate()


def test_overlapping_run_is_skipped_before_fetch(tmp_path, config, source):
    path = tmp_path / "overlap.sqlite"
    calls = []
    with Monitor(path, config, source) as second:

        def nested(url):
            calls.append(second.run(NOW))
            return source(url)

        with Monitor(path, config, nested) as first:
            assert first.run(NOW)["status"] == "COMPLETE"
    assert calls[0]["status"] == "BUSY"
    assert len(source.calls) == 1


@pytest.mark.parametrize("status", [200, 403, 429, 503])
def test_captcha_on_error_status_persists_pause(tmp_path, config, source, status):
    path = tmp_path / "captcha.sqlite"
    source.status = status
    source.html = "<title>Verify you are human: CAPTCHA</title>"
    with Monitor(path, config, source) as m:
        assert m.run(NOW)["status"] == "BLOCKED"
    with Monitor(path, config, source) as m:
        assert m.run(NOW + timedelta(days=1))["status"] == "PAUSED"
    assert len(source.calls) == 1


def test_midnight_during_search_defers_detail(tmp_path, config, source, monkeypatch):
    elapsed = [0.0]
    monkeypatch.setattr("funda_scraper.monitor_lab.time.monotonic", lambda: elapsed[0])
    path = tmp_path / "midnight.sqlite"
    before = datetime(2026, 11, 17, 22, 59, tzinfo=timezone.utc)
    with Monitor(path, config, source) as m:
        m.run(before)
    source.urls = [URL1, URL2]

    def crossing(url):
        doc = source(url)
        elapsed[0] += 120
        return doc

    with Monitor(path, config, crossing) as m:
        r = m.run(before)
        assert r["details_fetched"] == 0
        assert r["deferred"] == 1
        assert r["reason"] == "DAY_ROLLOVER"


@pytest.mark.parametrize("status", [403, 429])
@pytest.mark.parametrize("body", [b"\xff", b"x" * 2000001], ids=["invalid-utf8", "oversized"])
def test_http_block_is_persisted_before_reading_body(tmp_path, config, monkeypatch, status, body):
    from funda_scraper.monitor_lab import HTTPSource

    class Response:
        status_code = status

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def iter_content(self, *args):
            pytest.fail("A blocking response body must not be read")
            yield body

    http = HTTPSource(config)
    monkeypatch.setattr(http.session, "get", lambda *args, **kwargs: Response())
    try:
        with Monitor(tmp_path / "s.sqlite", config, http) as m:
            assert m.run(NOW)["status"] == "BLOCKED"
            assert m.run(NOW + timedelta(days=1))["status"] == "PAUSED"
    finally:
        http.close()


def test_probe_cannot_pass_when_details_fail(monkeypatch):
    import requests
    from urllib.parse import parse_qs
    from scripts import probe_monitor_lab

    class Source(FakeSource):
        def close(self):
            pass

        def __call__(self, url):
            scenario = parse_qs(urlsplit(url).query)["scenario"][0]
            if "/detail/" in url and "10000002" in url:
                raise requests.ConnectionError("synthetic failure")
            self.urls = [URL1, URL2] if scenario == "new" else [URL1]
            self.price = 510000 if scenario == "changed" else 500000
            return super().__call__(url)

    monkeypatch.setattr(probe_monitor_lab, "HTTPSource", lambda config: Source())
    result = probe_monitor_lab.probe(ORIGIN, allow_local=True)
    assert result["status"] == "FAIL"
    checks = {c["case"]: c for c in result["checks"]}
    assert not checks["new_and_duplicate"]["passed"]
    assert not checks["changed"]["passed"]
