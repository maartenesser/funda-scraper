"""Command line entrypoint with safe, concise failure messages."""

import argparse
from funda_scraper.errors import ScraperError
from funda_scraper.scrape import FundaScraper


def main():
    parser = argparse.ArgumentParser(description="Scrape public Funda property data")
    parser.add_argument("--area", required=True)
    parser.add_argument("--want_to", choices=["buy", "rent"], default="buy")
    parser.add_argument("--number_of_pages", "--n_pages", type=int, default=1)
    parser.add_argument("--page_start", type=int, default=1)
    parser.add_argument("--find_sold", action="store_true")
    for name in ("min_price", "max_price", "min_floor_area", "max_floor_area", "days_since"):
        parser.add_argument("--" + name, type=int)
    parser.add_argument("--property_type")
    parser.add_argument("--sort")
    parser.add_argument("--backend", choices=["requests", "browser"], default="requests")
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--raw_data", action="store_true")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--filepath")
    args = vars(parser.parse_args())
    raw, save, filepath = (args.pop(k) for k in ("raw_data", "save", "filepath"))
    args["headless"] = not args.pop("headed")
    try:
        with FundaScraper(**args) as scraper:
            df = scraper.run(raw_data=raw, save=save, filepath=filepath)
        print(f"Retrieved {len(df)} properties.")
        if not df.empty:
            print(df.head().to_string(index=False))
        return 0
    except (ScraperError, ValueError) as error:
        parser.exit(2, f"Scrape failed: {error}\n")
