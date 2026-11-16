"""Public exceptions. Messages never contain response bodies or credentials."""


class ScraperError(RuntimeError):
    """Base error for a failed scrape."""


class BlockedError(ScraperError):
    """Funda returned a CAPTCHA, access denial or rate limit."""


class ParseError(ScraperError):
    """The page does not contain a recognized search or property document."""


class FetchError(ScraperError):
    """The transport could not retrieve a page."""


class UnavailableError(FetchError):
    """A previously indexed property returned 404/410 or redirected to search."""
