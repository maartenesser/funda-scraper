# Live test lab verification — 17 November 2026

Deployment: https://funda-monitor-lab.maartenjr-esser.workers.dev
Report: https://funda-monitor-lab.maartenjr-esser.workers.dev/report.json
Worker version: `1435e416-ae8e-48de-b59d-a7718251307c`.

## Observed evidence

- 73 Python tests passed with `FUNDA_BROWSER_TEST=1`, including a real browser on
  an owned local fixture. 29 of these cover the new lab monitor/probe.
- Six Worker tests passed.
- Nine scenarios passed over HTTPS against the deployed owned Worker: baseline,
  new item plus duplicate, changed price, 403, 429, CAPTCHA, unknown HTML,
  foreign redirect rejection and recognized empty search.
- Ruff, Python sdist/wheel build and Cloudflare deploy dry run passed.
- Final fresh code review found no remaining blockers within synthetic scope;
  separate security and UI code reviews found no material blockers. Findings about
  caps, concurrency, midnight, CAPTCHA503, unreadable blocking bodies and false
  positive probe outcomes were repaired and covered by regressions.
- A visual browser check could not run: the browser access host was unavailable.
  HTTP and Worker-runtime checks did run. No screenshot-based review is claimed.

## Explicit limits

This is a deployed fixture server and a snapshot of completed tests, not a running
scheduled real-property monitor. There were zero Funda requests in this phase.
Funda is `NOT_RUN`; isolated remote browser/egress remains unverified. Synthetic
success does not prove current Funda access, resistance to blocking, completeness
across pages, or IP safety. No proxies were purchased, configured or rotated.

The Worker uses the existing personal Cloudflare account and no storage/browsing
bindings. The Waimakers vault token validated once, but subsequent vault reads
needed authorization and timed out. The existing authorized Cloudflare login
provided deployment access; token values were piped only to the consuming CLI,
never printed or copied into project files.

Five npm high advisories remain in development build dependencies through an
unpatched picomatch ReDoS advisory. The deployed Worker bundles no npm runtime
libraries and accepts no glob inputs. Details and reproduction commands are in
`lab/README.md`. This limitation is recorded rather than claiming a clean audit.

## Next gate

Provision/identify a separate remote runner and prove complete network isolation
against owned endpoints. Only after that gate, perform a separate single-page,
zero-detail Funda canary, stop on the first block, and label its outcome independently.

Final public endpoint verification returned HTTP 200 for `/`, `/health` and
`/report.json`, including the expected 73/6/9 counts and Funda `NOT_RUN`, using the
lab client's direct route (`trust_env=False`). A secondary urllib request using
its default environment returned 403; that alternative client/network route was
not characterized and is not counted as a successful check.
