# Managed browser egress test

Continue the existing isolated PR worktree. Extend the live fixture lab with two
owned observer hostnames and a bounded D1 counter. Never store raw IPs or headers.

1. Test observer expiry, source hashing, fixed bucket bounds and no forwarding.
2. Deploy allowed/denied hosts sharing a small counter; activate a single expiring
   public test ID. Positively verify the denied observer can count a control hit.
3. Create a Cloudflare-managed browser with immutable HTTP(S) hostname guardrails,
   no recording, and a one-minute idle expiry. Connect using remote CDP only.
4. Test allowed navigation, salted source difference from the local operator,
   denied navigation/redirect/subresource/worker fetch, and controlled DNS failure.
   Verify server-side forbidden counter deltas are zero. Close every session.
5. Review the measured gate. A narrower, HTML-only first Funda canary may follow
   in a new guarded remote browser: one exact search URL, JavaScript and service
   workers disabled, every other request intercepted/aborted, no redirects,
   details, personal login/cookies, retries, HAR, tracing or raw HTML export.
6. Persist canary attempt/stop before sending; publish aggregate status/counts only.
   A block remains a block. Do not switch egress or browser fingerprints to retry.

Ruling: this managed architecture replaces a self-hosted VM/proxy for this bounded
probe. Cloudflare controls the browser/network; the local process only calls its
API/CDP endpoint. There is no browser launcher or local transport fallback. Proxy
407/CONNECT/tunnel fault cases are inapplicable because no proxy/tunnel is used.
Guardrails document HTTP(S), not arbitrary protocols; do not claim a full network
namespace audit. The optional Funda probe disables page JavaScript and blocks all
subresources, so this probe does not exercise WebRTC/STUN or broad JS scraping.
All limitations stay explicit; managed browser bot identification is unchanged.

Execution ruling: the conditional final canary may share a managed browser with
its immediately preceding owned route verification, using a fresh nonpersistent
JavaScript-disabled context. Every required owned check (including context cleanup)
must pass before target navigation. Full session cleanup is measured afterwards.

Budget clarification after three owned-only QA attempts: preserve the existing QA
counter at three; add an independent single canary-browser acquisition counter.
The maximum for this test day is three owned-only QA browsers plus one conditional
canary browser, and still exactly one Funda document attempt. No counters or target
pauses are reset. This is a bounded test-phase budget, not a recurring collection
schedule. A failed route gate consumes the conditional canary browser and sends
zero Funda requests. There is no second conditional canary acquisition that day.

Final bounded revision after measured attempt four: the reserved `.invalid` host
returns `ERR_CONNECTION_RESET` through the managed provider. Record this as an
unresolvable-host closed-path outcome, not proof of an internal DNS error code.
The actual resolver diagnostic remains NOT_OBSERVABLE. All other measured checks
passed and receiving counters showed no forbidden hits. Rename that prerequisite
to `unresolvable_host_fail_closed`; a timeout/unclassified error still fails.

Allow a second conditional runner acquisition (total cap: three QA plus two
conditional runners, max five for this test day). Preserve all spent counters;
this is not a reset or a source retry: Funda attempts so far are zero. The permanent
single Funda document reservation remains unchanged. No further automatic runner
acquisition is allowed after this final bounded attempt in this test window.
