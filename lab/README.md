# Synthetic monitor test lab

Live: https://funda-monitor-lab.maartenjr-esser.workers.dev

The dashboard is a public, stateless fixture server and timestamped test report.
It has no arbitrary URL inputs, external resources or outbound fetches. The manual
remote harness additionally performed the bounded Funda canary documented below;
there is no scheduled collection or proxy rotation. The Python lab monitor only accepts this exact lab hostname or,
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

## Managed remote browser verification (executed)

The managed Browser Run route was exercised on five bounded browser acquisitions
(three owned QA attempts and two conditional-runner attempts). The final run
passed hostname guardrails for navigation, redirects, images and worker fetches;
server counters confirmed no forbidden hits from the remote browser. A positive
control demonstrated that the denied receiver could count a real request. Source
identity differed from the local operator and was observed as Cloudflare ASN13335.
Only a nonce-salted source digest was compared in memory; no IP was persisted.

The reserved `.invalid` hostname produced `ERR_CONNECTION_RESET`, a closed-path
result through the managed provider. Its internal DNS diagnostic is NOT_OBSERVABLE.
This is not a complete self-hosted firewall/namespace or arbitrary-protocol audit.
No proxy, tunnel or WARP route is used. The real target context disabled page
JavaScript, service workers and downloads and allowed only one exact main-frame
search URL. Remote CDP response interception aborted redirects before they could
be followed. `route.fetch()` is deliberately not used: it can issue requests from
the local Playwright driver.

Measured Funda outcome: one permitted document attempt, HTTP200 with CAPTCHA,
BLOCKED; four other requests aborted, zero detail pages and zero retries. The
persistent target reservation remains consumed across restarts and days. Periodic
collection stays disabled. No alternative IP, browser or proxy was tried after
this source block.

State lives in ignored `lab/.cloudflare/remote-canary.sqlite`. Do not delete it to
retest a blocked source. The runner has separate persistent bounds of three QA
starts and two conditional-runner starts for this test day; there is a permanent
single target-attempt latch. The development budget was explicitly revised in the
managed-egress plan while source attempts were still zero. No counters were reset.

The two observer Workers (`cf deploy --mode egress` and `--mode denied`) share the
small D1 `funda-egress-observations` database. Fixed buckets and a single expiring
public trial ID bound the stored rows; no credentials, source digests, IPs or
request headers are stored. The public ID is a test identifier, not an access
credential. After expiry, observer routes return410. The fixture dashboard has no
D1 binding and remains a read-only snapshot of sanitized results.

The manual harness requires the browser extra's Playwright library, but never
launches a local browser or downloads a browser binary. Supply an authorized
Browser Rendering Write token directly from the vault through stdin, never a file
or an argument. Ordinary invocations after this block stop; they cannot reset the
target latch. No scheduled canary job was added.
