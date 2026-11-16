"""Replaceable in-memory fetchers for local runs or a future scraping worker."""

import math
import random
import time
import re
from urllib.parse import urlsplit
import requests
from funda_scraper.errors import BlockedError, FetchError, UnavailableError
from funda_scraper.html import check_page, listing_links, property_key


class Transport:
    def __init__(self, delay=2.0, timeout=45.0):
        if not math.isfinite(delay) or delay < 0 or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("delay must be nonnegative and timeout must be positive and finite")
        self.delay = delay
        self.timeout = timeout
        self._last_request = None

    def _pace(self):
        if self._last_request is not None:
            remaining = self.delay * random.uniform(1.0, 1.3) - (
                time.monotonic() - self._last_request
            )
            if remaining > 0:
                time.sleep(remaining)
        self._last_request = time.monotonic()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class RequestsTransport(Transport):
    """A single cookie jar and bounded retries, without storing session state."""

    def __init__(self, delay=2.0, timeout=45.0, retries=2):
        super().__init__(delay, timeout)
        if not isinstance(retries, int) or not 0 <= retries <= 5:
            raise ValueError("retries must be an integer between 0 and 5")
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "funda-scraper/1.3 (personal research)",
                "Accept-Language": "en-GB,en;q=0.9,nl;q=0.8",
            }
        )

    def get(self, url):
        for attempt in range(self.retries + 1):
            self._pace()
            try:
                response = self.session.get(url, timeout=self.timeout)
            except requests.RequestException:
                if attempt == self.retries:
                    raise FetchError("HTTP request failed after bounded retries.") from None
            else:
                status = response.status_code
                if status in (404, 410):
                    response.close()
                    raise UnavailableError("Property is no longer available (HTTP 404/410).")
                if status in (401, 403, 429):
                    response.close()
                    raise BlockedError(
                        f"Funda denied the request (HTTP {status}). Try backend='browser' or retry later."
                    )
                if 200 <= status < 300:
                    html = response.text
                    response.close()
                    check_page(html)
                    return html
                response.close()
                if status < 500 or attempt == self.retries:
                    raise FetchError(f"HTTP request failed (status {status}).")
            time.sleep(min(2**attempt, 8))
        raise FetchError("HTTP request failed.")

    def close(self):
        self.session.close()


class BrowserTransport(Transport):
    """One local Camoufox context with JS and a stable session for the whole run.

    No browser state, cookies or raw pages are saved. CAPTCHA solving is manual
    when interactive=True; otherwise blocks stop the run immediately.
    """

    def __init__(self, delay=2.0, timeout=45.0, headless=True, interactive=False):
        super().__init__(delay, timeout)
        if interactive and headless:
            raise ValueError("interactive requires headless=False")
        self.headless, self.interactive = headless, interactive
        self._manager = self._browser = self._context = self._page = None
        self._consent_handled = False

    def _start(self):
        try:
            from camoufox.sync_api import Camoufox
        except ImportError:
            raise FetchError(
                "Install the browser extra: pip install 'funda-scraper[browser]', then python -m camoufox fetch."
            ) from None
        try:
            self._manager = Camoufox(headless=self.headless)
            self._browser = self._manager.__enter__()
            self._context = self._browser.new_context(locale="en-GB")
            self._page = self._context.new_page()
        except Exception:
            self.close()
            raise FetchError(
                "Cannot start Camoufox. Run python -m camoufox fetch and check browser system dependencies."
            ) from None

    def _reject_optional_cookies(self):
        if self._consent_handled:
            return
        button = self._page.locator(
            "#didomi-notice-disagree-button, .didomi-continue-without-agreeing"
        ).first
        try:
            button.wait_for(state="visible", timeout=1500)
            button.click(timeout=2000)
            self._consent_handled = True
        except Exception:
            # No known consent dialog. Never opt into optional tracking.
            pass

    def get(self, url):
        if self._page is None:
            self._start()
        self._pace()
        stage = "navigation"
        try:
            response = self._page.goto(
                url, wait_until="domcontentloaded", timeout=self.timeout * 1000
            )
            self._reject_optional_cookies()
            stage = "content rendering"
            status = response.status if response else 200
            if status in (404, 410):
                raise UnavailableError("Property is no longer available (HTTP 404/410).")
            if status in (401, 429):
                raise BlockedError(
                    f"Funda denied the browser request (HTTP {status}). Retry later."
                )
            if status != 403 and not 200 <= status < 300:
                raise FetchError(f"Browser request failed (HTTP {status}).")
            if status != 403:
                path = urlsplit(url).path
                match = re.search(r"/(\d+)/?$", path) or re.search(r"-(\d+)-", path)
                expected_id = match.group(1) if match else None
                self._page.wait_for_function(
                    r"""({isSearch, expectedId, expectedKey}) => {
                        if (document.querySelector('#px-captcha, #fundaCaptchaInput') ||
                            /je bent bijna|captcha|access denied/i.test(document.title)) return true;
                        if (isSearch && document.querySelector('main a[href*="/detail/"]')) return true;
                        if (!isSearch && (document.querySelector('link[rel="canonical"]')?.href || '').includes('/zoeken/')) return true;
                        const ready = v => {
                            if (Array.isArray(v)) return v.some(ready);
                            if (!v || typeof v !== 'object') return false;
                            if (isSearch && v['@type'] === 'ItemList' && Array.isArray(v.itemListElement)) return true;
                            if (!isSearch && v.address &&
                                !['Organization', 'RealEstateAgent'].includes(v['@type'])) {
                                const targets = [v.url, v['@id'], v.id, document.querySelector('link[rel="canonical"]')?.href];
                                if (expectedId && targets.some(target => String(target || '').split(/[/?#-]/).includes(expectedId))) return true;
                                const canonical = document.querySelector('link[rel="canonical"]')?.href;
                                if (canonical && expectedKey) {
                                    const match = new URL(canonical, location.href).pathname.match(/^\/(?:en\/)?detail\/(koop|huur)\/([^/]+)\/([^/]+)\/\d+\/?$/);
                                    if (match && match.slice(1).join('/') === expectedKey) return true;
                                }
                            }
                            return Object.values(v).some(ready);
                        };
                        return [...document.querySelectorAll('script[type="application/ld+json"]')].some(s => {
                            try { return ready(JSON.parse(s.textContent)); } catch { return false; }
                        }) || isSearch && /geen resultaten|geen woningen gevonden|0 koopwoningen|0 huurwoningen|no results|0 properties/i.test(document.body.innerText);
                    }""",
                    arg={
                        "isSearch": "/zoeken/" in path,
                        "expectedId": expected_id,
                        "expectedKey": property_key(url),
                    },
                    polling=100,
                    timeout=self.timeout * 1000,
                )
            html = self._page.content()
            try:
                if status == 403:
                    raise BlockedError("Funda returned a browser challenge (HTTP 403).")
                check_page(html)
            except BlockedError:
                if not self.interactive:
                    raise
                input("Complete the challenge in the browser, then press Enter here: ")
                html = self._page.content()
                check_page(html)
            if "/zoeken/" not in urlsplit(url).path:
                soup = check_page(html)
                canonical = soup.select_one('link[rel="canonical"]')
                if canonical and "/zoeken/" in urlsplit(canonical.get("href", "")).path:
                    # Search results may contain rich nested House objects; they
                    # never identify the requested detail page.
                    listing_links(html)
                    raise UnavailableError(
                        "Property link redirects to a search page; it may have expired."
                    )
            return html
        except (BlockedError, FetchError):
            raise
        except Exception as error:
            raise FetchError(
                f"Browser {stage} failed ({type(error).__name__}) or timed out; no page was exported."
            ) from None

    def close(self):
        if self._manager is not None:
            try:
                self._manager.__exit__(None, None, None)
            except Exception:
                pass
        self._manager = self._browser = self._context = self._page = None
