"""Browser lifecycle tests; the Camoufox boundary is replaced, parsing is real."""

import sys
import types
from unittest.mock import Mock
import pytest
from funda_scraper.transport import BrowserTransport
from funda_scraper.errors import BlockedError, FetchError


@pytest.fixture
def browser(monkeypatch):
    page = Mock()
    page.goto.return_value.status = 200
    page.content.return_value = (
        '<script type="application/ld+json">{"@type":"ItemList","itemListElement":[]}</script>'
    )
    context = Mock()
    context.new_page.return_value = page
    instance = Mock()
    instance.new_context.return_value = context
    manager = Mock()
    manager.__enter__ = Mock(return_value=instance)
    manager.__exit__ = Mock()
    factory = Mock(return_value=manager)
    monkeypatch.setitem(sys.modules, "camoufox.sync_api", types.SimpleNamespace(Camoufox=factory))
    return page, factory, manager, instance


def test_context_is_reused_and_closed(browser):
    page, factory, manager, instance = browser
    with BrowserTransport(delay=0) as client:
        assert "ItemList" in client.get("https://www.funda.nl/search")
        assert "ItemList" in client.get("https://www.funda.nl/detail")
    assert factory.call_count == 1
    assert instance.new_context.call_count == 1
    assert page.goto.call_count == 2
    assert manager.__exit__.call_count == 1


def test_headless_captcha_raises(browser):
    page, *_ = browser
    page.content.return_value = '<div id="px-captcha">Challenge</div>'
    with BrowserTransport(delay=0) as client, pytest.raises(BlockedError):
        client.get("https://www.funda.nl")


def test_interactive_http403_can_be_completed(browser, monkeypatch):
    page, *_ = browser
    page.goto.return_value.status = 403
    page.content.side_effect = ['<div id="px-captcha">Challenge</div>', "<main>success</main>"]
    monkeypatch.setattr("builtins.input", lambda prompt: "")
    with BrowserTransport(delay=0, headless=False, interactive=True) as client:
        assert client.get("https://www.funda.nl") == "<main>success</main>"


def test_http500_is_not_exported_as_html(browser):
    page, *_ = browser
    page.goto.return_value.status = 500
    with BrowserTransport(delay=0) as client, pytest.raises(FetchError):
        client.get("https://www.funda.nl")


def test_browser_error_is_redacted(browser):
    page, *_ = browser
    page.goto.side_effect = RuntimeError("fake-credential-test")
    with BrowserTransport(delay=0) as client, pytest.raises(FetchError) as error:
        client.get("https://www.funda.nl")
    assert "fake-credential-test" not in str(error.value)
    assert error.value.__suppress_context__


def test_search_redirect_is_unavailable(browser):
    from funda_scraper.errors import UnavailableError

    page, *_ = browser
    page.content.return_value = '<link rel="canonical" href="https://www.funda.nl/en/zoeken/koop/"><script type="application/ld+json">{"@type":"ItemList","itemListElement":[]}</script>'
    with BrowserTransport(delay=0) as client, pytest.raises(UnavailableError):
        client.get("https://www.funda.nl/detail/koop/amsterdam/huis-test/12345678/")


def test_rich_search_redirect_never_becomes_another_property(browser):
    from funda_scraper.errors import UnavailableError

    page, *_ = browser
    page.content.return_value = '<link rel="canonical" href="https://www.funda.nl/zoeken/koop/"><script type="application/ld+json">{"@type":"ItemList","itemListElement":[{"item":{"@type":"House","url":"https://www.funda.nl/detail/koop/amsterdam/huis-other/99999999/","address":{"streetAddress":"Wrong home"}}}]}</script>'
    with BrowserTransport(delay=0) as client, pytest.raises(UnavailableError):
        client.get("https://www.funda.nl/detail/koop/amsterdam/huis-test/12345678/")
