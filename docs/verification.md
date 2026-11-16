# Verification of the repair

This check began 14 November 2026 and completed after local browser debugging.
The upstream starting commit was `c011570`.

## Observed live result

A local Camoufox run against one Amsterdam buying-results page discovered **15**
property links, extracted **15** detail records and produced **15** cleaned rows.
No API key, ScrapingBee account or paid proxy was used. A later repeated live
run returned HTTP 403 and correctly raised BlockedError. Access was therefore
observed to work for the successful run, but was not reliable across repeated runs. The run kept one browser
context, rejected optional consent and spaced navigation by at least two seconds.
The sample prices/areas were EUR 695000 / 121 m², EUR 650000 / 117 m² and
EUR 395000 / 75 m². No raw HTML or session state was saved.

Funda exposed different indexed and canonical numeric IDs for the same exact
address path. The scraper accepts this explicit canonical alias, checks the
market/city/address identity, and rejects unrelated property data. Search pages
can contain rich House JSON-LD; they must never be exported as requested details.

## Local verification

- Python 3.12: 44 tests passed, including the opt-in real-browser test.
- Python 3.9: 43 passed, 1 browser test skipped; Apple LibreSSL warning noted below.
- A real headless browser against a local server: rejects optional cookies, waits
  for delayed JavaScript property data, and honors a same-address canonical alias.
- Real HTTP session/cookie handling, transient retry, CAPTCHA/403/429 handling,
  unknown HTML, CSV export, empty results, unavailable links and identity checks.
- Ruff, sdist/wheel build, and installation smoke check.
- GitHub Actions matrix: Python 3.9 through 3.13 (results linked from the PR).

Browser combination tested on macOS ARM64: Camoufox Python 0.4.11, browser
158.0.1-beta.41 and Playwright 1.62.0. Playwright 1.65.2 failed to create a context
because its download protocol added an unsupported `legacyInterceptor` field;
the browser extra now keeps Playwright below 1.63.

Apple's system Python 3.9 uses LibreSSL and emits urllib3's OpenSSL warning.
Its regression tests pass; Python 3.12 is the recommended local interpreter.

## Limits

This is a bounded smoke test, not a guarantee of future or large-scale access.
Funda may change its HTML, return a CAPTCHA or restrict an IP. The scraper reports
blocks instead of treating them as successful empty data. Historical/rental
access and every optional property field were not independently live-verified.
No Cloudflare infrastructure or external scraping service was deployed.
