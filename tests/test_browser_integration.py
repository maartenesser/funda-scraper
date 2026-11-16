"""Opt-in local browser checks: FUNDA_BROWSER_TEST=1 pytest tests/test_browser_integration.py.

Requires the browser extra and downloaded Camoufox. No Funda requests are made.
"""

import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import pytest
from funda_scraper.transport import BrowserTransport

pytestmark = pytest.mark.skipif(
    os.environ.get("FUNDA_BROWSER_TEST") != "1", reason="opt-in real browser check"
)


def test_waits_for_requested_detail_after_recommendation_card():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"""<link rel="canonical" href="https://www.funda.nl/detail/koop/amsterdam/huis-test/87654321/"><main><a href="/detail/koop/amsterdam/huis-other/99999999/">Other home</a></main>
              <button id="didomi-notice-disagree-button" onclick="window.dispatchEvent(new Event('optional-rejected'))">Disagree and close</button>
              <script>window.addEventListener('optional-rejected', () => setTimeout(() => {
                const node = document.createElement('script');
                node.type = 'application/ld+json';
                node.textContent = JSON.stringify({"@type":"House", "url":"https://www.funda.nl/en/detail/koop/amsterdam/huis-test/",
                                                  "address":{"streetAddress":"Requested home"}});
                document.head.append(node);
              }, 700));</script>""")

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with BrowserTransport(delay=0, timeout=20) as client:
            start = time.monotonic()
            html = client.get(
                f"http://127.0.0.1:{server.server_port}/detail/koop/amsterdam/huis-test/12345678/"
            )
            from funda_scraper import DataExtractor, SearchRequest

            house = DataExtractor().extract_data_from_detail_page(
                html,
                SearchRequest("amsterdam", "buy"),
                expected_url="https://www.funda.nl/detail/koop/amsterdam/huis-test/12345678/",
            )
            assert house.address == "Requested home"
            assert time.monotonic() - start >= 0.5
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
