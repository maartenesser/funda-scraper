"""Parse structured data and labelled features without positional assumptions."""

import json
import re
from urllib.parse import urljoin, urlsplit, urlunsplit
from bs4 import BeautifulSoup
from funda_scraper.errors import BlockedError, ParseError


def check_page(html):
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(" ", strip=True).lower() if soup.title else ""
    if (
        any(
            x in title
            for x in (
                "je bent bijna",
                "access denied",
                "verify you are human",
                "captcha",
                "just a moment",
            )
        )
        or soup.select_one("#px-captcha, #fundaCaptchaInput, form[action*='captcha']")
        or (
            not soup.select("a[href*='/detail/'], script[type='application/ld+json']")
            and any(
                x in soup.get_text(" ", strip=True).lower()
                for x in ("press & hold", "verify you are human", "je bent bijna op de pagina")
            )
        )
    ):
        raise BlockedError(
            "Funda returned a CAPTCHA or block page. Try backend='browser' or retry later."
        )
    return soup


def json_objects(soup):
    """Visit every JSON-LD object, including arrays and @graph containers."""

    def walk(value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from walk(child)

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            yield from walk(json.loads(script.get_text()))
        except (ValueError, TypeError):
            continue


def property_url(value):
    if not isinstance(value, str):
        return None
    try:
        parts = urlsplit(urljoin("https://www.funda.nl", value))
        port = parts.port
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or parts.hostname not in ("www.funda.nl", "funda.nl"):
        return None
    if parts.username or parts.password or port not in (None, 80, 443):
        return None
    path = parts.path[3:] if parts.path.startswith("/en/") else parts.path
    if not re.fullmatch(
        r"/(?:detail/(?:koop|huur)/[^/]+/[^/]+/\d+|(?:en/)?(?:koop|huur)/[^/]+/[^/]*-\d+-[^/]+)/?$",
        path,
    ):
        return None
    return urlunsplit(("https", "www.funda.nl", path.rstrip("/") + "/", "", ""))


def property_id(value):
    if not isinstance(value, str):
        return None
    path = urlsplit(value).path
    match = re.search(r"/(\d+)/?$", path) or re.search(r"-(\d+)-", path)
    return match.group(1) if match else None


def property_key(value):
    """Stable market/city/address key for Funda's canonical ID aliases."""
    if not isinstance(value, str):
        return None
    path = urlsplit(value).path
    modern = re.fullmatch(r"/(?:en/)?detail/(koop|huur)/([^/]+)/([^/]+)/\d+/?", path)
    if modern:
        return "/".join(modern.groups())
    old = re.fullmatch(r"/(?:en/)?(koop|huur)/([^/]+)/([^-]+)-\d+-(.+)/?", path)
    if old:
        market, city, kind, address = old.groups()
        return f"{market}/{city}/{kind}-{address.rstrip('/')}"
    return None


def listing_links(html):
    soup = check_page(html)
    links = []
    primary = next(
        (
            obj
            for obj in json_objects(soup)
            if obj.get("@type") == "ItemList" and isinstance(obj.get("itemListElement"), list)
        ),
        None,
    )
    if primary is not None:

        def entries(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, list):
                for item in value:
                    yield from entries(item)
            elif isinstance(value, dict):
                for key in ("url", "@id", "item"):
                    yield from entries(value.get(key))

        for candidate in entries(primary["itemListElement"]):
            value = property_url(candidate)
            if value:
                links.append(value)
        if primary["itemListElement"] and not links:
            raise ParseError("Listing items have no recognized property URLs.")
        return list(dict.fromkeys(links))
    root = soup.find("main") or soup
    for a in root.select("a[href]"):
        if a.find_parent(["aside", "footer", "nav"]):
            continue
        value = property_url(a.get("href"))
        if value:
            links.append(value)
    if not links:
        text = root.get_text(" ", strip=True).lower()
        if not any(
            x in text
            for x in (
                "geen resultaten",
                "geen woningen gevonden",
                "0 koopwoningen",
                "0 huurwoningen",
                "no results",
                "0 properties",
            )
        ):
            raise ParseError(
                "Could not recognize a Funda listing page; the HTML layout may have changed."
            )
    return list(dict.fromkeys(links))


def detail_object(soup):
    property_types = {
        "Residence",
        "House",
        "Apartment",
        "SingleFamilyResidence",
        "Accommodation",
        "Product",
        "RealEstateListing",
    }
    candidates = []
    for obj in json_objects(soup):
        if not isinstance(obj.get("address"), dict):
            continue
        types = obj.get("@type", [])
        if isinstance(types, str):
            types = [types]
        url = property_url(obj.get("url") or obj.get("@id"))
        if url or property_types.intersection(types):
            candidates.append((obj, url))
    canonical = soup.select_one('link[rel="canonical"]')
    expected = property_url(canonical.get("href")) if canonical else None
    for obj, url in candidates:
        if url and (
            expected is None
            or property_id(url) == property_id(expected)
            or property_key(url) == property_key(expected)
        ):
            return obj
    # Some property documents only use a local @id; the canonical property URL
    # can identify those, but must not relabel another recognized property URL.
    if expected:
        for obj, url in candidates:
            if url is None:
                return obj
    elif candidates:
        return candidates[0][0]
    raise ParseError("Could not recognize property JSON-LD on the detail page.")


def labelled_features(soup):
    values = {}
    for dt in soup.select("dt"):
        dd = dt.find_next_sibling("dd")
        if dd:
            label = dt.get_text(" ", strip=True).lower().rstrip(":")
            values[label] = dd.get_text(" ", strip=True)
    return values
