# Eerste uitvoerbare testfase

Goal: build and publish an isolated synthetic monitor test lab; measure outcomes before enabling any Funda navigation.
Spec: ../specs/2026-11-17-ip-isolated-test-plan.md and ../specs/2026-11-17-personal-incremental-scope.md.

## Task 1: persistent low-volume monitor tested against owned fixtures
- [ ] Write failing incremental/safety/budget/recovery tests.
- [ ] Implement SQLite state, explicit outcomes, persistent daily caps, source allowlist and atomic exports.
- [ ] Run baseline and new tests, including real local browser fixture.

## Task 2: deploy owned live fixtures and status
- [ ] Build Worker fixture endpoints/status and tests.
- [ ] Deploy separate test Worker with existing authorized Cloudflare credential.
- [ ] Probe deployed fixtures and publish timestamped evidence with Funda disabled.

## Task 3: verify remote canary prerequisites and report
- [ ] Read-only discover appropriate existing remote/test route; do not reuse unrelated client production resources.
- [ ] Run isolated remote tests if suitable infrastructure exists; mark unproved egress NOT_RUN.
- [ ] Fresh whole-branch review, fix important findings, deploy final version and report exact scope.

Ruling: this user turn prioritizes a deployed test environment over the entire prior eight-task production system. No source-Funda traffic is allowed through the local test runner. The first deployment is synthetic-only; enabling Funda requires the separate egress gate. Existing client infra must not be repurposed merely because credentials are available. No new paid subscription is purchased for the lab.
