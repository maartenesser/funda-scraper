# FundaScraper

A repaired fork of [whchien/funda-scraper](https://github.com/whchien/funda-scraper).
Fetch public sale/rental listings, parse their details and export a pandas
DataFrame or CSV. Python **3.9 through 3.13**.

## Install

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install 'git+https://github.com/maartenesser/funda-scraper.git@main'
```

For the optional **free local browser**, install the browser extra and download
Camoufox's Firefox binary (a large download):

```sh
python -m pip install 'funda-scraper[browser] @ git+https://github.com/maartenesser/funda-scraper.git@main'
python -m camoufox fetch
```

No ScrapingBee account, API key or paid proxy is required. The browser runs on
your computer or your own worker server. Linux hosts also need the browser's
system libraries.

## Python

```python
from funda_scraper import FundaScraper, BlockedError

try:
    with FundaScraper(
        area="amsterdam",
        want_to="buy",           # "rent" also works
        number_of_pages=1,
        backend="browser",       # "requests" is the lightweight default
        delay=2.0,               # minimum interval, with small random jitter
    ) as scraper:
        df = scraper.run(raw_data=False, save=True, filepath="homes.csv")
        print(df.head())
except BlockedError as error:
    print(error)
```

The object API also works:

```python
from funda_scraper import FundaScraper, SearchRequest

request = SearchRequest(area="utrecht", want_to="rent", min_price=500, max_price=2000)
with FundaScraper(request, backend="browser") as scraper:
    raw_df = scraper.run(clean_data=False)
```

`run()` returns cleaned data by default. Use `raw_data=True` or `clean_data=False`
for the raw property fields. Saving is opt-in (`save=True`); default filename is
`<area>_properties.csv`. An explicit `filepath` sets the CSV destination. Missing
optional source fields remain `na`. Cleaning removes rows without a usable
price or living area. No HTML archives, cookies or browser state are written.
Use the context manager or call `close()` to release sessions/browser resources.

Search options: `area`, `want_to`, `find_sold`, `page_start`, `number_of_pages`,
`min_price`, `max_price`, `days_since` (1/3/5/10/30), `property_type` (comma-separated),
`min_floor_area`, `max_floor_area`, `sort`. Legacy aliases `n_pages` and `find_past`
are accepted. `find_sold` asks for unavailable listings, which can include more
than completed sales. `price_sold` is a legacy field containing the displayed
last asking price where available, **not a verified transaction price**. Login-only
fields are not fetched.

## CLI

```sh
funda-scraper --area amsterdam --want_to buy --backend browser --number_of_pages 1 --save --filepath homes.csv
# Equivalent:
python -m funda_scraper --area amsterdam --backend browser --save
```

If a headless browser is challenged, run a visible local browser and solve the
challenge yourself:

```sh
funda-scraper --area amsterdam --backend browser --headed --interactive --save
```

The browser rejects optional cookies in Funda's known consent dialog. It keeps
one context, cookies and fingerprint for the run, executes
JavaScript and requests pages sequentially. It does not export cookies to the
HTTP client, rotate fingerprints per request or solve CAPTCHAs automatically.
A future worker/API can use the same transport interface (`get(url) -> HTML`,
`close()`) without changing extraction.

## Access limitations

A browser is **not a guarantee of access**. Funda can still block your IP or
require a CAPTCHA. HTTP 200 challenge pages raise `BlockedError`; unknown layouts
raise `ParseError`, and network/provider failures raise `FetchError`. The CLI
exits with code 2 for these failures instead of reporting an empty successful
scrape. Legitimate recognized empty searches return an empty DataFrame. Indexed detail
links returning 404/410 or a recognized search redirect are reported in
`scraper.unavailable_links` and skipped with a warning. Canonical ID aliases
are accepted only for the same market, city and address path; unrelated property
data is rejected. If every discovered
property is unavailable, the run fails and exports no CSV.

Direct HTTP retries transient network/5xx errors at most twice by default, with
backoff; it does not hammer 403/429 or CAPTCHA responses. Browser navigation has
bounded waits and stops on a block. `timeout`, `delay`, and HTTP `retries` are
configurable. Check site terms and permission for your intended use. The inherited
code license remains GPL-3.0.

## Development and verification

```sh
python -m pip install -e '.[dev,browser]'
pytest
ruff check funda_scraper tests main.py setup.py
python -m build
```

For the opt-in real-browser test against a local delayed JavaScript page:

```sh
FUNDA_BROWSER_TEST=1 pytest tests/test_browser_integration.py
```

The default tests run offline against synthetic HTML and a local HTTP server. They exercise
real extraction, pricing, current/legacy links, CSV export, request sessions,
transient failure recovery and block detection. They do not prove that every
live Funda layout or network will work. Live checks must be run explicitly with
the CLI; no network scraping is part of CI.

## Optional self-hosted service

For scheduled collection, use a small browser worker running this Python package.
Cloudflare Workers can expose an authenticated API; Queues can dispatch bounded
jobs, and D1/R2 can hold status and exported public data. The browser worker keeps
session state in memory, returns structured records, and stops on blocks. Do not
expose a public arbitrary-URL proxy or store browser profiles/session tokens in
R2. This repository implements the scraper component, not that deployment.

Cloudflare's own [Browser Run FAQ](https://developers.cloudflare.com/browser-run/faq/)
notes that traffic originates from Cloudflare IPs and is identifiable as bot
traffic. Hosting coordination there does not itself reproduce a managed proxy
network or promise access to Funda.

The free-browser approach follows the session, rendering and pacing principles
in the [ScrapingBee article](https://www.scrapingbee.com/blog/how-to-bypass-perimeterx-anti-bot-system/)
and [Camoufox documentation](https://camoufox.com/python/usage/).
