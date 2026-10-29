# Portfolio walkthrough

## Thirty-second explanation

Tracewright catches changes in agent behavior before a release. It executes versioned cases, stores redacted traces, and compares a candidate against an immutable baseline. The difficult parts are preserving comparison identity, making ingestion safe to retry, handling concurrent baseline writes, and reporting uncertainty without treating repeated trials as independent test cases.

## Three-minute demo

1. Start Compose and run `tracewright demo` inside the API container.
2. Connect the dashboard and inspect the baseline's tool events; sensitive fields are masked.
3. Compare the baseline and intentionally broken candidate: 100% versus 50%, two failing cases.
4. Explain why the observed CI gate fails while the statistical report stays inconclusive.
5. Promote a versioned baseline, try the same version again, and show the conflict.
6. Open GitHub Actions to show the actual PostgreSQL and Docker verification outcomes.

## Defensible project bullets

- Built an agent regression platform with FastAPI, PostgreSQL, schema migrations, authenticated trace ingestion, and immutable versioned baselines.
- Implemented deterministic assertions, per-trial process timeouts, redacted trace capture, idempotent ingestion, and a dashboard for baseline/candidate analysis.
- Designed conservative case-level uncertainty reporting and automated Python, PostgreSQL, CLI, and Docker HTTP checks in GitHub Actions.

Do not claim users, production uptime, improved model accuracy, SWE-bench scores, or latency savings without measured evidence. This work was AI-assisted; review and understand the code before presenting it as engineering experience.

## Questions to prepare for

- How do a uniqueness constraint and transaction resolve concurrent baseline promotion?
- Why can retrying the same run be safe while changing its payload must fail?
- Why aren't repeated trials extra independent cases in the interval?
- Why doesn't a child process safely sandbox malicious code?
- What would change when moving from one shared workspace to a multi-tenant service?
- Why use JSON snapshots now, and when would you normalize trial outcomes?
