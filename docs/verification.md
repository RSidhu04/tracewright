# Verified delivery — October 29, 2026

## Automated verification

- **37 pytest tests passed** locally on Python 3.12.14, including a real temporary PostgreSQL instance. No PostgreSQL test was skipped in that run.
- Covered assertions, schema validation, redaction, trace budgets, worker timeout/stdout isolation, suite mismatch, comparison math, trial pairing, storage restart, migrations, ingestion idempotency/conflicts, authorization, request limits, immutable baselines, concurrent PostgreSQL promotion, SWE-bench import invariants, and actual CLI subprocesses.
- One third-party warning remains: Starlette deprecates its HTTPX TestClient integration in favor of HTTPX2. It does not fail the tests; migrate that test dependency in a maintenance change.
- Live HTTP smoke checks passed against a PostgreSQL-backed uvicorn server: health/readiness, static dashboard assets, unauthorized access rejection, ingestion, retry, redaction, baseline creation, and regression comparison.

## GitHub Actions evidence

[Verified CI run](https://github.com/RSidhu04/tracewright/actions/runs/40964120012), commit `5d49d650dcaea8bc35e70373d891c2e2f1073a41`:

| Job | Verified outcome |
| --- | --- |
| Python 3.11 + PostgreSQL | Success |
| Python 3.12 + PostgreSQL | Success |
| Docker Compose build/startup | Success |
| Docker live HTTP smoke checks | Success |
| Persistence after API restart | Success |

The workflow uploads JUnit test and comparison artifacts. Subsequent documentation commits trigger the same workflow; use the repository's Actions page for the latest commit status.

## Browser verification

The local PostgreSQL-backed dashboard was exercised in the browser: authenticated connection, run list, baseline/candidate selection, regression report, and baseline promotion. The synthetic calculator comparison showed 100% baseline pass rate, 50% candidate pass rate, two observed regressions, and an inconclusive statistical interval of approximately [-100, 85.8] percentage points. That is the expected behavior for this small suite.

## What is not claimed

No public/cloud deployment, load test, security audit, SSO/RBAC deployment, calibrated LLM judge, actual SWE-bench task evaluation, leaderboard score, or user adoption is claimed. The GHCR release workflow is configured but has not been triggered by a version tag. Docker was verified on GitHub's Linux runner; Docker is not installed on the development Mac. PostgreSQL was also exercised locally using a temporary packaged test runtime.

The earlier v0.1 milestone had 23 tests and SQLite-only validation. This delivery supersedes that milestone with the PostgreSQL-backed platform and GitHub verification above.
