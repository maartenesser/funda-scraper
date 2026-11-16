"""Sequential Funda scraper with replaceable session-aware transports."""

import uuid
import warnings
from pathlib import Path
from urllib.parse import urlencode
import pandas as pd
from funda_scraper.config.core import config
from funda_scraper.errors import UnavailableError
from funda_scraper.extract import DataExtractor, properties_frame
from funda_scraper.html import listing_links, property_url
from funda_scraper.preprocess import preprocess_data
from funda_scraper.searchrequest import SearchRequest
from funda_scraper.transport import BrowserTransport, RequestsTransport


class FundaScraper:
    def __init__(
        self,
        search_request=None,
        *,
        area=None,
        want_to="buy",
        backend="requests",
        transport=None,
        delay=2.0,
        timeout=45.0,
        retries=2,
        headless=True,
        interactive=False,
        **search_options,
    ):
        if search_request is not None:
            if not isinstance(search_request, SearchRequest) or area is not None or search_options:
                raise ValueError("Pass a SearchRequest OR area/search keywords, not both.")
            self.search_request = search_request
        else:
            if area is None:
                raise ValueError("area is required")
            # n_pages/find_past were used in older releases.
            for old, new in (("n_pages", "number_of_pages"), ("find_past", "find_sold")):
                if old in search_options:
                    if new in search_options:
                        raise ValueError(f"Specify only one of {old} and {new}.")
                    search_options[new] = search_options.pop(old)
            self.search_request = SearchRequest(area=area, want_to=want_to, **search_options)
        self.search_request.to_buy  # Validate before making any network requests.
        if self.search_request.days_since is not None:
            self.search_request.check_days_since
        self.links = []
        self.unavailable_links = []
        self.raw_df = properties_frame([])
        self.clean_df = pd.DataFrame()
        self.base_url = config.base_url
        self.run_id = str(uuid.uuid4())
        self.data_extractor = DataExtractor()
        if transport is not None:
            self.transport = transport
        elif backend == "requests":
            self.transport = RequestsTransport(delay, timeout, retries)
        elif backend == "browser":
            self.transport = BrowserTransport(delay, timeout, headless, interactive)
        else:
            raise ValueError("backend must be 'requests' or 'browser'")

    def __repr__(self):
        return str(self.search_request)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self.transport.close()

    def _build_main_query_url(self):
        request = self.search_request
        params = {"selected_area": f'["{request.area}"]'}
        if request.property_type:
            import json

            params["object_type"] = json.dumps(
                request.property_type.split(","), separators=(",", ":")
            )
        if request.find_sold:
            params["availability"] = '["unavailable"]'
        if request.min_price is not None or request.max_price is not None:
            low = "" if request.min_price is None else request.min_price
            high = "" if request.max_price is None else request.max_price
            params["price"] = f'"{low}-{high}"'
        if request.days_since is not None:
            params["publication_date"] = request.check_days_since
        if request.min_floor_area is not None or request.max_floor_area is not None:
            low = "" if request.min_floor_area is None else request.min_floor_area
            high = "" if request.max_floor_area is None else request.max_floor_area
            params["floor_area"] = f'"{low}-{high}"'
        if request.sort is not None:
            params["sort"] = f'"{request.sort_by}"'
        market = "koop" if request.to_buy else "huur"
        return f"{self.base_url}/zoeken/{market}?{urlencode(params)}"

    @staticmethod
    def remove_duplicates(values):
        return list(dict.fromkeys(values))

    @staticmethod
    def fix_link(link):
        """Modern detail URLs work directly; never force the retired old_ldp UI."""
        result = property_url(link)
        if not result:
            raise ValueError("Not a recognized Funda property link.")
        return result

    def run(self, clean_data=None, *, raw_data=None, save=False, filepath=None):
        if raw_data is not None and clean_data is not None and clean_data == raw_data:
            raise ValueError("raw_data and clean_data contradict each other")
        clean = (
            (not raw_data) if raw_data is not None else (True if clean_data is None else clean_data)
        )
        # Do not leave stale results visible after a failed second run.
        self.links = []
        self.unavailable_links = []
        self.raw_df = properties_frame([])
        self.clean_df = pd.DataFrame()
        main = self._build_main_query_url()
        for page in range(
            self.search_request.page_start,
            self.search_request.page_start + self.search_request.number_of_pages,
        ):
            links = listing_links(self.transport.get(f"{main}&search_result={page}"))
            if not links:
                break
            self.links.extend(links)
        self.links = self.remove_duplicates(self.links)
        houses = []
        for url in self.links:
            try:
                html = self.transport.get(url)
                houses.append(
                    self.data_extractor.extract_data_from_detail_page(
                        html, self.search_request, expected_url=url
                    )
                )
            except UnavailableError:
                self.unavailable_links.append(url)
        if self.unavailable_links:
            if not houses:
                raise UnavailableError(
                    "All discovered property links are unavailable; no CSV was exported."
                )
            warnings.warn(
                f"Skipped {len(self.unavailable_links)} unavailable property links; inspect scraper.unavailable_links.",
                UserWarning,
                stacklevel=2,
            )
        self.raw_df = properties_frame(houses)
        self.data_extractor.raw_df = self.raw_df
        result = (
            preprocess_data(self.raw_df, self.search_request.find_sold)
            if clean
            else self.raw_df.copy()
        )
        if clean:
            self.clean_df = result
            self.data_extractor.clean_df = result
        if save:
            target = (
                Path(filepath) if filepath else Path(f"{self.search_request.area}_properties.csv")
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            result.to_csv(target, index=False)
        return result


if __name__ == "__main__":
    from funda_scraper.cli import main

    raise SystemExit(main())
