# Tracewright

**Regression testing for AI agent behavior.** Capture redacted execution evidence, evaluate deterministic assertions, compare candidate runs, and promote immutable baseline versions.

A production-style, single-workspace portfolio application built with **Python, FastAPI, Pydantic, PostgreSQL, SQLAlchemy, Alembic, pytest, Docker, and GitHub Actions**. Includes a responsive developer dashboard and CLI. It is not a production-certified hosted service or a calibrated LLM judge.

## What you can demonstrate

- Run a versioned suite against baseline and candidate Python agents.
- Capture tool events, outputs, assertion outcomes, errors, and durations.
- Ingest complete runs through an authenticated API with validation, redaction, bounded requests, and idempotent retries.
- Store immutable run snapshots and explicitly numbered baseline versions in PostgreSQL.
- Inspect evidence and compare runs in the dashboard; download the JSON report.
- Fail CI on observed regressions or require conservative statistical noninferiority.
- Import SWE-bench harness outcomes for a pinned task manifest without executing patches inside the web server.

## Five-minute Docker demo

Prerequisites: Git, Docker Engine/Desktop with Compose v2, and Python 3 to generate local configuration. Repository access requires your GitHub account because the repository is private.

```sh
git clone https://github.com/RSidhu04/tracewright.git
cd tracewright
python3 - <<'PY'
from pathlib import Path
import secrets
path = Path('.env')
if path.exists():
    raise SystemExit('.env already exists; keep your existing settings')
path.write_text('POSTGRES_PASSWORD=' + secrets.token_hex(24) + '\n'
                + 'TRACEWRIGHT_API_TOKEN=' + secrets.token_hex(24) + '\n')
path.chmod(0o600)
PY
docker compose up --build -d --wait
docker compose exec -T api tracewright demo --output /tmp/demo.json
```

Open **http://localhost:8000**, paste `TRACEWRIGHT_API_TOKEN` from your local `.env`, and connect. Select `demo-baseline` as the baseline run and `demo-candidate` as the candidate. Click **Compare behavior**. The candidate intentionally loses negative signs: **100% → 50% pass rate**, two observed regressions, and **inconclusive** statistical evidence for four cases. Use Inspect to read the redacted trace, or promote a reference with a new name/version.

The demo command returns 0 because generating a demonstration succeeded. The actual `compare` gate returns 1 for this regression. The dashboard token lives in memory only; refresh or Disconnect clears access. Run selectors show the current page of 20 runs; use pagination to browse other pages. Baseline cards show the first 1,000 stored versions; use the paginated API for larger histories.

```sh
docker compose exec -T api python scripts/smoke.py
docker compose down  # Keeps PostgreSQL data in the named volume
```

PostgreSQL is not exposed on a host port. The app binds to loopback. A migration service runs before the API starts; the API image runs as a non-root user with a read-only filesystem and temporary `/tmp`. `docker compose down -v` destroys the demo database; use only when you intentionally want to discard it.

## Local Python development

Requires Python 3.11 or 3.12. SQLite remains available for a quick standalone run; PostgreSQL is the primary deployment path.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-tested.txt
pip install --no-deps .
export TRACEWRIGHT_API_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(24))')"
tracewright demo
uvicorn tracewright.api:create_app --factory --host 127.0.0.1 --port 8000
```

Use `pip install -e '.[dev]'` for editable development on standard Python environments. The bundled desktop Python used during development ignored editable path files, so a regular package installation was used for CLI validation.

For PostgreSQL, set `TRACEWRIGHT_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DB`, then run `tracewright migrate` once before starting the API. URL-encode reserved characters in credentials. The SQLite default is `tracewright.db`; override it with `TRACEWRIGHT_DB` or CLI `--db` before the subcommand. PostgreSQL schemas are never created implicitly by application startup.

## CLI workflow

```sh
BASE=$(tracewright run examples/calculator.v1.json --agent tracewright.sample:baseline --revision sample-v1 --repeats 3)
CAND=$(tracewright run examples/calculator.v1.json --agent tracewright.sample:candidate --revision sample-v2 --repeats 3)
tracewright baseline calculator 1 "$BASE" --note "Reviewed synthetic reference"
tracewright compare "$BASE" "$CAND" --output reports/comparison.json
# Expected exit 1: candidate regresses.
tracewright export "$CAND" --output reports/candidate.json
tracewright upload "$CAND" --url http://127.0.0.1:8000
```

`upload` reads `TRACEWRIGHT_API_TOKEN` from the environment and requires HTTPS except for localhost. Upload from a local SQLite runner into the PostgreSQL-backed service to keep evaluation and serving separate. Exact secret values can be supplied with `--secret-env ENVIRONMENT_VARIABLE`; shared ingestion redaction values use comma-separated `TRACEWRIGHT_REDACT_VALUES`. Avoid commas within individual values for that configuration option.

Exit codes: **0** operation or selected gate passed, **1** gate failed, **2** invalid input/configuration/storage/HTTP operation. A successful `run` records failed assertions and still exits 0; `compare` owns the release decision. Compare to a known all-passing reference if you require an initial all-passing suite.

## Agent and suite contract

Agents are synchronous importable callables: `agent(inputs: dict, trace, seed: int) -> JSON value`. `trace.emit('tool.call', {...})` captures explicit events. Install custom modules as packages or set `PYTHONPATH` to their directory. The CLI launches each trial in a fresh child process with a default 10-second timeout; override with `--timeout`. It suppresses agent stdout/stderr to keep the run-ID protocol usable. This is process isolation for reliability, **not a sandbox for hostile code**.

Suites are JSON files with `schema_version`, `name`, `version`, and nonempty `cases`. Each case has a unique ID, input dictionary, and assertions. See [calculator.v1.json](examples/calculator.v1.json). Assertions support `equals`, `contains`, and JSON `type` checks with paths expressed as lists of object keys/list indices. All assertions must pass. Missing paths fail; booleans are not numbers. `equals` checks type at the selected value and then Python equality; nested equality follows Python container semantics. No code is evaluated from assertion definitions.

The suite fingerprint hashes canonical full suite content. Comparisons require matching fingerprints, repeats, seeds, and case/trial keys. Version labels alone cannot hide changed cases. Agent `--revision` is a declared label: use a Git commit plus model/prompt identifier, but do not treat it as automatic code attestation. A supplied seed is only effective if the agent/provider respects it.

## Regression policy

Each case's score is its fraction of trials passing all assertions. The overall difference averages candidate-minus-baseline scores equally across cases. Positive values mean improvement.

| Gate | Failure condition |
| --- | --- |
| `observed` (default) | Any case drops by more than `--tolerance` |
| `statistical` | Overall noninferiority is not established; inconclusive fails closed |
| `none` | Report only; no comparison-based failure |

Tolerance is a fraction, e.g. `0.05` means five percentage points. Observed regressions are a policy decision, not a significance claim. Statistical reporting uses a conservative case-level Hoeffding interval; repeated trials do not inflate the number of independent cases. Read [statistics and interpretation](docs/statistics.md) before using it as a gate for stochastic agents.

## API and dashboard

The dashboard is served at `/`; interactive schema documentation is at `/docs`. Supply `Authorization: Bearer <token>` for all run/baseline/comparison operations. Authentication fails closed if the server starts without a token of at least 16 characters. Public health checks expose no run data.

| Endpoint | Purpose |
| --- | --- |
| `GET /health`, `GET /ready` | Process liveness and database readiness |
| `POST /runs` | Ingest a complete run; 201 created, 200 identical retry, 409 conflicting ID |
| `GET /runs?limit=20&offset=0` | Paginated summaries |
| `GET /runs/{id}` | Redacted evidence |
| `POST /baselines` | Create immutable `{name, version, run_id, note}` |
| `GET /baselines`, `GET /baselines/{name}/{version}` | Inspect versioned references |
| `GET /compare?baseline=...&candidate=...` | Compare compatible run IDs |

See [API examples](docs/api.md), [architecture](docs/architecture.md), and [operations](docs/operations.md).

## SWE-bench

Tracewright can ingest the official harness summary's `resolved_ids` for a predeclared manifest of instance IDs and dataset revision. Tasks absent from the resolved list count as failures, including incomplete/error cases, so the denominator does not shrink after evaluation.

```sh
tracewright import-swebench examples/swebench-report.synthetic.json \
  --manifest examples/swebench-manifest.synthetic.json --revision synthetic-fixture
```

These bundled fixtures are **synthetic**. No official SWE-bench dataset evaluation, model inference, patch execution, leaderboard submission, or benchmark score is claimed. Run the [official harness](https://www.swebench.com/SWE-bench/api/harness/) separately in its required execution environment, then import its results. The importer does not cryptographically verify an external report or distinguish infrastructure failure from agent failure in the pass score.

## Verification and CI/CD

```sh
pytest -q
# To include PostgreSQL tests, use a disposable database:
TRACEWRIGHT_TEST_DATABASE_URL='postgresql+psycopg://...' pytest -q
```

The [CI workflow](.github/workflows/ci.yml) tests Python 3.11/3.12 with PostgreSQL, verifies regression exit codes, uploads reports, builds Docker Compose, runs real HTTP smoke checks, and checks persistence across API restart. The [release workflow](.github/workflows/release.yml) builds and publishes a version-tagged GHCR image on `v*` tags; production rollout is deliberately operator-controlled. No release tag or public deployment is created by this implementation.

[Verification results](docs/verification.md) distinguish tested behavior from configured-only features. [requirements-tested.txt](requirements-tested.txt) records tested dependency versions; it is not a hash-verified supply-chain lock.

## Limitations and next steps

This is a single-workspace application with one shared bearer token, not multi-tenant SaaS. There is no RBAC, SSO, token management UI, distributed task queue, hardened agent sandbox, CPU/memory enforcement, alerting, or fleet monitoring. The web API receives results; it does not run arbitrary agents. Redaction is best effort. Trial wall-clock durations are descriptive, not a latency significance test. Large workloads need normalized result storage, aggregate queries, trace retention, and operational load testing.

LLM judging is deferred until human-labeled rubrics and held-out validation exist. No judge is claimed calibrated. See [SECURITY.md](SECURITY.md), [contributing](CONTRIBUTING.md), and [portfolio walkthrough](docs/portfolio.md). MIT licensed; repository visibility remains private until the owner chooses to publish it.
