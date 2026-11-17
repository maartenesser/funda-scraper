# Managed browser canary — 17 November 2026

## Actual result

At 19:21 UTC the final Cloudflare Browser Run test passed all required owned-route
checks, then performed one JavaScript-disabled Funda search-document attempt.
Funda returned HTTP200 with a recognized CAPTCHA page. The result is BLOCKED,
not a successful empty search. Four additional requests were aborted, zero detail
pages fetched, zero retries performed. The remote context closed and the result
was saved in the persistent target latch. There were no subsequent Funda calls.

The network monitor counted4066encoded bytes; the DOM HTML was13940bytes in
memory and was discarded. No HTML, screenshots, HAR, cookies, browser profiles,
recordings, CDP URLs or tokens were exported. The code/evidence digests and
sanitized result are bundled in `lab/src/evidence.json`.

## Remote route evidence

- Browser runs on Cloudflare; the local harness only connects to Cloudflare API/CDP.
- The owned observer saw Cloudflare ASN13335 and a different nonce-salted source
  digest from the operator's direct observer request. Digests stayed in memory.
- Denied navigation, redirect, image and worker fetches did not reach their owned
  receiving endpoints. A positive receiver control was counted each run.
- Final receiving totals: allowed5(remote5), forbidden5(remote0; all five were
  deliberate direct positive controls), worker-control3(remote3). No forbidden
  image/worker or same-host redirect target buckets were created.
- CDP response interception continued an owned200 and blocked an owned302 before
  following; receiver counters remained unchanged. Real target policy only
  permits the exact URL/main frame/document once; every other request aborts.
- Page JavaScript disabled was verified against an owned inline-script fixture.
- The reserved unresolvable host produced ERR_CONNECTION_RESET. This demonstrates
  a closed path plus a verified remote source after the fault; the managed
  provider's internal DNS error is NOT_OBSERVABLE. It is not claimed as a specific
  resolver error or as an audit of all host protocols.
- Proxy credential/407/CONNECT/tunnel cases are inapplicable to this managed-direct
  variant. The bounded target has no page JS or subresources, so WebRTC/STUN is
  not an enabled target path. No broader scraping readiness is inferred.

## Test and review record

86 Python tests including the owned local browser, 11 Worker tests, and the nine
previous live synthetic HTTP scenarios passed. Code/security review identified
and fixed automatic Playwright redirect following and lost request counts on
cleanup/persistence failures. Regression tests cover those paths and prove the
conditional canary cannot run after a failed live gate. A forced late gate error
cannot produce a false PASS. Visual browser verification remains unavailable.

Three owned-only attempts and two conditional-runner attempts were used. Earlier
failures were measurement issues (worker response event scope; DNS error-document
navigation race and over-specific error classification), with zero Funda requests.
The independent bounded runner counter was explicitly revised without resetting
spent counters. The actual source attempt stayed capped at one throughout.

## Operational consequence

This proves the tested managed route is separate from the operator's source
identity and enforces the tested HTTP(S) boundaries. It does not solve Funda's bot
challenge, prove continuous availability, or guarantee future IP acceptance.
The periodic monitor stays disabled and the target stays paused. No automatic
challenge solving, proxy rotation, browser change or further source probe follows.

A fresh state connection confirmed BLOCKED with one document attempt; both a
second target reservation and an additional conditional runner reservation were
rejected. This check issued no Funda or browser request.

Protocol references: [Cloudflare hostname guardrails](https://developers.cloudflare.com/browser-run/features/guardrails/),
[Chrome DevTools Fetch interception](https://chromedevtools.github.io/devtools-protocol/tot/Fetch/),
and [Cloudflare Browser Run FAQ](https://developers.cloudflare.com/browser-run/faq/).
