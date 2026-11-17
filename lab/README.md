# Synthetic monitor test lab

Live: https://funda-monitor-lab.maartenjr-esser.workers.dev

This is a public, stateless fixture server and a timestamped test report. It does
not scrape Funda, run a scheduled collection job, rotate proxies or prove isolated
egress. There are no arbitrary URL inputs, external resources or outbound fetches
in the Worker. The Python lab monitor only accepts this exact lab hostname or,
with an explicit test flag, local HTTP fixtures. Canonical Funda URLs in JSON-LD
are synthetic identifiers, never fetch destinations.

## Reproduce

Use Python 3.9–3.13 with the repository dependencies. Use Node 26.13.1 for `cf`.

```sh
python -m pytest -q
# Optional, requires the browser extra and installed Camoufox binary:
FUNDA_BROWSER_TEST=1 python -m pytest -q
cd lab
npm ci
npm test
npx cf deploy --dry-run
cd ..
PYTHONPATH=. python scripts/probe_monitor_lab.py \
  --origin https://funda-monitor-lab.maartenjr-esser.workers.dev
```

The probe uses temporary SQLite databases per synthetic scenario so each check is
independent. A future real monitor must keep one persistent state database: deleting
it resets budgets and pauses. The current runner targets Linux/macOS (`flock`).
`Monitor.run` persists 3 runs, 25 page attempts and 10 detail attempts per Amsterdam
calendar day; a run crossing midnight defers remaining work. It skips overlapping
runs. Initial discovery seeds a baseline without fetching details; subsequent runs
fetch only new or changed cards. HTTP 403/429 and CAPTCHA HTML persist a pause.
Redirects are never followed. Unknown pages are failures, not empty successes.
State is committed with SQLite; exports replace the previous file atomically.

For local Worker-runtime integration:

```sh
cd lab
npx cf dev --port 8765
# Separate terminal, repository root:
PYTHONPATH=. python scripts/probe_monitor_lab.py \
  --origin http://localhost:8765 --allow-local
```

## Deployment and evidence

`cloudflare.config.ts` targets a separate Worker on the personal Cloudflare account.
No production database or paid binding is used. `cf deploy --dry-run` precedes
`cf deploy`. Use an existing authorized Cloudflare CLI login or a vault reference
passed directly into the consuming deployment command. Never copy tokens into
files, logs or commits. Evidence is bundled into `src/evidence.json`; update it only
from actual completed checks. Its timestamps describe a snapshot, not a live
heartbeat. `/health` is a current availability check.

`npm audit` currently reports five high findings in the development build tool
chain, all through picomatch (GHSA-fc5q-39xc-vjpf, latest 4.0.7 still affected).
There is no npm runtime dependency in the deployed Worker. This lab accepts no
user-supplied glob patterns and does not publish a Vite development server. Track
an upstream patch before broadening this build service; no forced incompatible
package downgrade was applied.

Before any Funda canary: prove dedicated remote browser and network egress with
fail-closed routing and complete request accounting. Do not run that canary from
home/office, automatically retry a block or infer that these fixture results imply
Funda access. See the isolated IP test spec in `docs/superpowers/specs/`.
