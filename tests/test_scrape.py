"""Offline regression tests using synthetic fixtures, never live captures."""

import json
from pathlib import Path
import pandas as pd
import pytest
from funda_scraper import FundaScraper
from funda_scraper.searchrequest import SearchRequest

URL = "https://www.funda.nl/detail/koop/amsterdam/huis-teststraat-1/12345678/"


def ld(data):
    return '<script type="application/ld+json">' + json.dumps(data) + "</script>"


@pytest.fixture
def listing():
    return ld({"@type": "BreadcrumbList", "itemListElement": []}) + ld(
        {
            "@graph": [
                {
                    "@type": "ItemList",
                    "itemListElement": [{"@type": "ListItem", "item": {"@id": URL}}, {"url": URL}],
                }
            ]
        }
    )


@pytest.fixture
def detail():
    return (
        ld({"@type": "BreadcrumbList"})
        + ld(
            [
                {
                    "@type": "Residence",
                    "url": URL,
                    "description": "A test home",
                    "address": {
                        "streetAddress": "Teststraat 1",
                        "addressLocality": "Amsterdam",
                        "postalCode": "1000 AA",
                    },
                    "offers": {"price": 500000, "priceCurrency": "EUR"},
                    "image": ["https://images.funda.nl/test.jpg"],
                }
            ]
        )
        + """<dl>
        <dt>Woonoppervlakte</dt><dd>100 m²</dd>
        <dt>Bouwjaar</dt><dd>1990</dd>
        <dt>Soort woonhuis</dt><dd>Eengezinswoning</dd>
        <dt>Soort bouw</dt><dd>Bestaande bouw</dd>
        <dt>Aantal kamers</dt><dd>4 kamers (3 slaapkamers)</dd>
        <dt>Aantal badkamers</dt><dd>1 badkamer</dd>
        <dt>Energielabel</dt><dd>A</dd>
    </dl>"""
    )


class FixtureTransport:
    def __init__(self, listing, detail):
        self.listing, self.detail = listing, detail
        self.urls = []

    def get(self, url):
        self.urls.append(url)
        return self.listing if "/zoeken/" in url else self.detail

    def close(self):
        pass


def test_readme_api_exports_real_values(tmp_path, monkeypatch, listing, detail):
    monkeypatch.chdir(tmp_path)
    transport = FixtureTransport(listing, detail)
    with FundaScraper(area="amsterdam", want_to="buy", transport=transport, delay=0) as scraper:
        df = scraper.run(raw_data=False, save=True, filepath="homes.csv")
    assert df.shape == (1, 18)
    assert df.iloc[0]["house_id"] == 12345678
    assert df.iloc[0]["price"] == 500000
    assert df.iloc[0]["living_area"] == 100
    assert df.iloc[0]["bedroom"] == 3
    assert df.iloc[0]["address"] == "Teststraat 1"
    assert scraper.links == [URL]
    assert pd.read_csv("homes.csv").iloc[0]["price_m2"] == 5000
    assert len(transport.urls) == 2
    assert not list(Path(".").rglob("*.html"))


def test_searchrequest_api_and_raw_data(listing, detail):
    scraper = FundaScraper(
        SearchRequest("amsterdam", "rent"), transport=FixtureTransport(listing, detail), delay=0
    )
    row = scraper.run(clean_data=False).iloc[0]
    assert row["zip_code"] == "1000 AA"
    assert isinstance(row["layout"], str)
    assert row["description"] == "A test home"


def test_link_parser_uses_cards_without_jsonld(detail):
    scraper = FundaScraper(
        area="amsterdam",
        want_to="buy",
        delay=0,
        transport=FixtureTransport(
            f'<a href="{URL}">home</a><a href="https://evil.example/detail/koop/a/b/123/">ignore</a>',
            detail,
        ),
    )
    assert len(scraper.run(raw_data=True)) == 1


def test_empty_results_are_valid(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    transport = FixtureTransport(ld({"@type": "ItemList", "itemListElement": []}), "")
    df = FundaScraper(area="amsterdam", want_to="buy", transport=transport, delay=0).run(
        save=True, filepath="empty.csv"
    )
    assert df.empty
    assert "house_id" in pd.read_csv("empty.csv").columns


def test_pagination_and_filters(listing, detail):
    transport = FixtureTransport(listing, detail)
    scraper = FundaScraper(
        area="amsterdam",
        want_to="buy",
        min_price=100000,
        max_price=500000,
        number_of_pages=2,
        page_start=3,
        transport=transport,
        delay=0,
    )
    scraper.run(raw_data=True)
    from urllib.parse import parse_qs, urlsplit

    queries = [parse_qs(urlsplit(u).query) for u in transport.urls if "/zoeken/" in u]
    assert [q["search_result"] for q in queries] == [["3"], ["4"]]
    assert queries[0]["price"] == ['"100000-500000"']


def test_unrecognized_html_is_not_empty_success():
    scraper = FundaScraper(
        area="amsterdam",
        want_to="buy",
        transport=FixtureTransport("<html>unexpected</html>", ""),
        delay=0,
    )
    with pytest.raises(Exception, match="(?i)(parse|recogn|listing)"):
        scraper.run()


def test_detail_captcha_is_not_silently_skipped(listing):
    scraper = FundaScraper(
        area="amsterdam",
        want_to="buy",
        transport=FixtureTransport(
            listing, "<title>Je bent bijna op de pagina die je zoekt [funda]</title>"
        ),
        delay=0,
    )
    with pytest.raises(Exception, match="(?i)(captcha|block)"):
        scraper.run()


def test_sold_search_without_days_since_is_allowed(listing, detail):
    transport = FixtureTransport(listing, detail)
    scraper = FundaScraper(
        area="amsterdam", want_to="buy", find_sold=True, transport=transport, delay=0
    )
    assert len(scraper.run(raw_data=True)) == 1
    assert "availability=" in transport.urls[0]


def test_legacy_aliases_and_old_url(detail):
    old = "https://www.funda.nl/koop/amsterdam/huis-12345678-teststraat-1/?old_ldp=true"
    scraper = FundaScraper(
        area="amsterdam",
        want_to="buy",
        n_pages=1,
        find_past=False,
        transport=FixtureTransport(
            ld({"@type": "ItemList", "itemListElement": [{"url": old}]}), detail.replace(URL, old)
        ),
        delay=0,
    )
    assert scraper.run().iloc[0]["house_id"] == 12345678


def test_bad_card_url_is_ignored(detail):
    bad = "https://www.funda.nl:invalid/detail/koop/a/b/123/"
    page = f'<a href="{bad}">invalid</a><a href="{URL}">home</a>'
    scraper = FundaScraper(
        area="amsterdam", want_to="buy", transport=FixtureTransport(page, detail), delay=0
    )
    assert len(scraper.run()) == 1


def test_agent_jsonld_does_not_replace_property(listing, detail):
    agent = ld(
        {
            "@type": "RealEstateAgent",
            "url": "https://agent.example",
            "address": {"streetAddress": "Wrong address"},
        }
    )
    page = '<link rel="canonical" href="' + URL + '">' + agent + detail
    scraper = FundaScraper(
        area="amsterdam", want_to="buy", transport=FixtureTransport(listing, page), delay=0
    )
    df = scraper.run()
    assert len(df) == 1
    assert df.iloc[0]["address"] == "Teststraat 1"


def test_float_jsonld_area_not_dropped(listing):
    page = ld(
        {
            "@type": "House",
            "url": URL,
            "address": {"streetAddress": "Teststraat 1"},
            "offers": {"price": 500000.0},
            "floorSize": {"value": 100.0},
        }
    )
    scraper = FundaScraper(
        area="amsterdam", want_to="buy", transport=FixtureTransport(listing, page), delay=0
    )
    df = scraper.run()
    assert len(df) == 1
    assert df.iloc[0]["living_area"] == 100


def test_empty_primary_list_ignores_recommendations(detail):
    page = (
        ld({"@type": "ItemList", "itemListElement": []})
        + f'<aside><a href="{URL}">recommended</a></aside>'
    )
    scraper = FundaScraper(
        area="amsterdam", want_to="buy", transport=FixtureTransport(page, detail), delay=0
    )
    assert scraper.run().empty


def test_missing_price_returns_clean_empty_frame(listing, detail):
    scraper = FundaScraper(
        area="amsterdam",
        want_to="buy",
        transport=FixtureTransport(listing, detail.replace('"price": 500000', '"price": "na"')),
        delay=0,
    )
    assert scraper.run().empty


def test_reset_changes_pagination(listing, detail):
    request = SearchRequest("amsterdam", "buy")
    request.reset(page_start=3, number_of_pages=2)
    transport = FixtureTransport(listing, detail)
    scraper = FundaScraper(request, transport=transport, delay=0)
    assert len(scraper.run()) == 1
    assert "search_result=3" in transport.urls[0]
    assert "search_result=4" in transport.urls[1]


def test_english_property_links_use_canonical_route(listing, detail):
    english_url = URL.replace("/detail/", "/en/detail/")
    transport = FixtureTransport(listing.replace(URL, english_url), detail)
    scraper = FundaScraper(area="amsterdam", want_to="buy", transport=transport, delay=0)
    assert len(scraper.run()) == 1
    assert transport.urls[-1] == URL


def test_unavailable_listing_is_reported_and_other_homes_are_kept(detail):
    from funda_scraper.errors import UnavailableError

    second = URL.replace("12345678", "23456789")

    class Transport(FixtureTransport):
        def get(self, url):
            if url == URL:
                raise UnavailableError("Property no longer available")
            return super().get(url)

    page = ld({"@type": "ItemList", "itemListElement": [{"url": URL}, {"url": second}]})
    scraper = FundaScraper(
        area="amsterdam",
        want_to="buy",
        transport=Transport(page, detail.replace(URL, second)),
        delay=0,
    )
    with pytest.warns(UserWarning, match="1 unavailable"):
        df = scraper.run()
    assert df.iloc[0]["house_id"] == 23456789
    assert scraper.unavailable_links == [URL]


def test_all_unavailable_does_not_export_success(tmp_path, monkeypatch, listing):
    from funda_scraper.errors import UnavailableError

    monkeypatch.chdir(tmp_path)

    class Gone(FixtureTransport):
        def get(self, url):
            if "/zoeken/" not in url:
                raise UnavailableError("gone")
            return super().get(url)

    scraper = FundaScraper(area="amsterdam", want_to="buy", transport=Gone(listing, ""), delay=0)
    with pytest.raises(UnavailableError, match="All discovered"):
        scraper.run(save=True, filepath="homes.csv")
    assert not Path("homes.csv").exists()


def test_different_property_is_never_exported(listing, detail):
    from funda_scraper import ParseError

    scraper = FundaScraper(
        area="amsterdam",
        want_to="buy",
        transport=FixtureTransport(
            listing,
            detail.replace("12345678", "99999999").replace(
                "huis-teststraat-1", "huis-otherstraat-99"
            ),
        ),
        delay=0,
    )
    with pytest.raises(ParseError, match="(?i)(identity|requested|match)"):
        scraper.run()


def test_same_address_canonical_id_alias_is_accepted(listing, detail):
    alias = URL.replace("12345678", "87654321")
    page = '<link rel="canonical" href="' + alias + '">' + detail.replace(URL, alias)
    scraper = FundaScraper(
        area="amsterdam", want_to="buy", transport=FixtureTransport(listing, page), delay=0
    )
    assert scraper.run().iloc[0]["house_id"] == 87654321


def test_canonical_does_not_mask_unrelated_schema(listing, detail):
    from funda_scraper import ParseError

    other = detail.replace("12345678", "99999999").replace(
        "huis-teststraat-1", "huis-otherstraat-99"
    )
    page = '<link rel="canonical" href="' + URL + '">' + other
    scraper = FundaScraper(
        area="amsterdam", want_to="buy", transport=FixtureTransport(listing, page), delay=0
    )
    with pytest.raises(ParseError):
        scraper.run()
