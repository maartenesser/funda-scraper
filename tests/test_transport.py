"""Exercise real HTTP against a local server; no internet needed."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import pytest
from funda_scraper.transport import RequestsTransport
from funda_scraper.errors import BlockedError, FetchError


@pytest.fixture
def server():
    class Handler(BaseHTTPRequestHandler):
        attempts = 0

        def do_GET(self):
            if self.path == "/captcha":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"<title>Je bent bijna op de pagina die je zoekt [funda]</title>")
            elif self.path == "/rate":
                self.send_response(429)
                self.end_headers()
            elif self.path == "/retry":
                Handler.attempts += 1
                self.send_response(503 if Handler.attempts == 1 else 200)
                self.end_headers()
                self.wfile.write(b"recovered")
            elif self.path == "/cookie":
                self.send_response(
                    200 if "test_session=ok" in self.headers.get("Cookie", "") else 403
                )
                self.end_headers()
                self.wfile.write(b"session kept")
            else:
                self.send_response(200)
                self.send_header("Set-Cookie", "test_session=ok; Path=/")
                self.end_headers()
                self.wfile.write(b"hello")

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()
    thread.join()


def test_http_keeps_session_in_memory(server):
    with RequestsTransport(delay=0) as client:
        assert client.get(server) == "hello"
        assert client.get(server + "/cookie") == "session kept"


def test_http_retries_transient_failure(server):
    with RequestsTransport(delay=0, retries=1) as client:
        assert client.get(server + "/retry") == "recovered"


@pytest.mark.parametrize("path", ["/captcha", "/rate"])
def test_http_detects_blocks_including_status_200(server, path):
    with RequestsTransport(delay=0) as client, pytest.raises(BlockedError):
        client.get(server + path)


def test_network_exception_does_not_leak_secrets(monkeypatch):
    import requests

    def fail(*args, **kwargs):
        raise requests.ConnectionError("https://user:fake-test-password@example.com")

    with RequestsTransport(delay=0, retries=0) as client:
        monkeypatch.setattr(client.session, "get", fail)
        with pytest.raises(FetchError) as error:
            client.get("https://www.funda.nl")
        assert "fake-test-password" not in str(error.value)
        assert error.value.__suppress_context__
