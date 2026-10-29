# Verified delivery — October 29, 2026

## Automated verification

- **65 pytest tests passed** locally on Python 3.12.14, including a real temporary PostgreSQL instance. No PostgreSQL test was skipped in that run.
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

The local PostgreSQL-backed dashboard was exercised in the browser: authenticated connection, run list, baseline/candidate selection, regression report, and baseline promotion. The synthetic calculator comparison showed 100% baseline pass rate, 75% candidate pass rate, five observed regressions, and an inconclusive statistical interval of approximately [-85.7, 35.7] percentage points. That is the expected behavior for this curated 20-case suite.

## What is not claimed

No public/cloud deployment, load test, security audit, SSO/RBAC deployment, calibrated LLM judge, actual SWE-bench task evaluation, leaderboard score, or user adoption is claimed. The GHCR release workflow is configured but has not been triggered by a version tag. Docker was verified on GitHub's Linux runner; Docker is not installed on the development Mac. PostgreSQL was also exercised locally using a temporary packaged test runtime.

The earlier v0.1 milestone had 23 tests and SQLite-only validation. This delivery supersedes that milestone with the PostgreSQL-backed platform and GitHub verification above.

## Portfolio expansion verification

Gitleaks 8.30.1 `detect` scanned the available local and fetched GitHub history with zero findings before publication. The binary checksum was verified against the official release manifest. CI now repeats the full-history scan. This is a scanner result, not a guarantee that every possible secret format is detectable.

The 65-test run includes all 20 calculator cases and mocked OpenAI Responses tool protocol tests. The optional LLM example has not been run with live credentials; no measured prompt-regression result is claimed yet. The PR-summary job is configured for same-repository PRs; consult the actual PR and Actions run for execution evidence.
