"""Extract public listing values from JSON-LD and labelled property features."""

from dataclasses import asdict
from urllib.parse import urlsplit
import pandas as pd
from funda_scraper.config.core import config
from funda_scraper.errors import ParseError, UnavailableError
from funda_scraper.filerepository import FileRepository
from funda_scraper.html import (
    check_page,
    detail_object,
    labelled_features,
    property_url,
    property_id,
    property_key,
    listing_links,
)
from funda_scraper.preprocess import preprocess_data
from funda_scraper.property import Property

LABELS = {
    "year_of_construction": ("bouwjaar", "year of construction"),
    "living_area": ("woonoppervlakte", "wonen", "living area"),
    "house_type": ("soort woonhuis", "soort appartement", "kind of house", "apartment type"),
    "building_type": ("soort bouw", "building type"),
    "number_of_rooms": ("aantal kamers", "number of rooms"),
    "number_of_bathrooms": ("aantal badkamers", "number of bath rooms", "number of bathrooms"),
    "energy_label": ("energielabel", "energy label"),
    "insulation": ("isolatie", "insulation"),
    "heating": ("verwarming", "heating"),
    "ownership": ("eigendomssituatie", "ownership situation"),
    "parking": ("soort parkeergelegenheid", "type of parking facilities"),
    "listed_since": ("aangeboden sinds", "listed since"),
    "date_list": ("aangeboden sinds", "listed since"),
    "date_sold": ("verkoopdatum", "date of sale"),
    "term": ("looptijd", "term"),
    "price_sold": ("laatste vraagprijs", "last asking price"),
    "last_ask_price": ("laatste vraagprijs", "last asking price", "vraagprijs", "asking price"),
    "last_ask_price_m2": ("vraagprijs per m²", "asking price per m²"),
}
SELECTOR_NAMES = {
    "house_type": "kind_of_house",
    "number_of_rooms": "num_of_rooms",
    "number_of_bathrooms": "num_of_bathrooms",
}


def properties_frame(houses):
    columns = list(asdict(Property()))
    rows = []
    for house in houses:
        row = asdict(house)
        row["photos"] = house.photos_string
        rows.append(row)
    return pd.DataFrame(rows, columns=columns)


class DataExtractor:
    def __init__(self):
        self.selectors = config.css_selector
        self.raw_df = pd.DataFrame()
        self.clean_df = pd.DataFrame()
        self.file_repo = FileRepository()

    def extract_data(self, search_request, run_id, clean_data=False):
        """Reprocess an existing archive. New runs do not write raw HTML."""
        pages = self.file_repo.get_detail_pages(run_id)
        houses = [
            self.extract_data_from_detail_page(page, search_request) for page in pages.values()
        ]
        self.raw_df = properties_frame(houses)
        df = preprocess_data(self.raw_df, search_request.find_sold) if clean_data else self.raw_df
        self.clean_df = df if clean_data else pd.DataFrame()
        self.file_repo.save_result_file(df, run_id)
        return df

    def extract_data_from_detail_page(self, page, search_request, expected_url=None):
        soup = check_page(page)
        canonical = soup.select_one('link[rel="canonical"]')
        if canonical and "/zoeken/" in canonical.get("href", ""):
            listing_links(page)
            raise UnavailableError("Requested property redirected to recognized search results.")
        obj = detail_object(soup)
        house = Property()
        canonical = soup.select_one('link[rel="canonical"]')
        house.url = property_url(obj.get("url") or obj.get("@id"))
        if not house.url and canonical:
            house.url = property_url(canonical.get("href"))
        if not house.url:
            raise ParseError("Property document has no recognized Funda URL.")
        canonical_url = property_url(canonical.get("href")) if canonical else None
        if canonical_url:
            house.url = canonical_url
        if expected_url and property_id(house.url) != property_id(expected_url):
            if not (canonical_url and property_key(canonical_url) == property_key(expected_url)):
                raise ParseError("Property identity does not match the requested listing.")
        address = obj["address"]
        house.address = address.get("streetAddress", "na")
        house.city = address.get("addressLocality", search_request.area)
        house.zip_code = address.get("postalCode", "na")
        house.description = obj.get("description", "na")
        offers = obj.get("offers", {})
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if isinstance(offers, dict) and offers.get("price") is not None:
            house.price = f"{offers.get('priceCurrency', 'EUR')} {offers['price']}"
        features = labelled_features(soup)
        for name in asdict(house):
            if name in ("photos", "url", "address", "city", "description"):
                continue
            value = next(
                (features[label] for label in LABELS.get(name, ()) if label in features), None
            )
            if value is None and getattr(house, name) == "na":
                selector = self.selectors.get(SELECTOR_NAMES.get(name, name))
                if selector:
                    value = self.get_value_from_css(soup, selector)
            if value is not None:
                setattr(house, name, self.format_string(value))
        if house.price == "na":
            house.price = features.get("vraagprijs", features.get("asking price", "na"))
        if house.house_type == "na":
            house.house_type = "appartement" if "/appartement-" in house.url else "huis"
        if house.living_area == "na":
            area = obj.get("floorSize", {})
            if isinstance(area, dict) and area.get("value") is not None:
                house.living_area = f"{area['value']} m²"
        if house.number_of_rooms == "na" and obj.get("numberOfRooms"):
            house.number_of_rooms = f"{obj['numberOfRooms']} rooms"
        images = obj.get("image", [])
        if not isinstance(images, list):
            images = [images]
        for image in images:
            value = (
                image.get("contentUrl") or image.get("url") if isinstance(image, dict) else image
            )
            if isinstance(value, str) and urlsplit(value).scheme == "https":
                house.photos.append(value)
        return house

    @staticmethod
    def get_value_from_css(soup, selector):
        element = soup.select_one(selector)
        return element.get_text(" ", strip=True) if element else "na"

    @staticmethod
    def format_string(value):
        return " ".join(value.split()) if isinstance(value, str) else value
