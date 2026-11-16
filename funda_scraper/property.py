"""Stable raw property schema, including empty search results."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Property:
    url: str = "na"
    price: str = "na"
    address: str = "na"
    city: str = "na"
    description: str = "na"
    listed_since: str = "na"
    zip_code: str = "na"
    size: str = "na"
    year_of_construction: str = "na"
    living_area: str = "na"
    house_type: str = "na"
    building_type: str = "na"
    number_of_rooms: str = "na"
    number_of_bathrooms: str = "na"
    layout: str = "na"
    energy_label: str = "na"
    insulation: str = "na"
    heating: str = "na"
    ownership: str = "na"
    exteriors: str = "na"
    parking: str = "na"
    neighborhood_name: str = "na"
    date_list: str = "na"
    date_sold: str = "na"
    term: str = "na"
    price_sold: str = "na"
    last_ask_price: str = "na"
    last_ask_price_m2: str = "na"
    photos: List[str] = field(default_factory=list)

    @property
    def photos_string(self) -> str:
        return "|".join(self.photos)
