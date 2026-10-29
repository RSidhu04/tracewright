# Tracewright

**CI for agent behavior.** Execute versioned cases against a Python agent, capture redacted traces, evaluate deterministic assertions, and compare a candidate with a baseline.

## Quick start

Python 3.11+ is required. Run these commands from this repository:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q

BASE=$(tracewright run examples/calculator.v1.json --agent tracewright.sample:baseline --revision sample-v1 --repeats 3)
CAND=$(tracewright run examples/calculator.v1.json --agent tracewright.sample:candidate --revision sample-v2 --repeats 3)
tracewright compare "$BASE" "$CAND" --output comparison.json
```

The final command intentionally exits **1**: the candidate replaces negative answers with their absolute value. Baseline pass rate is 100%, candidate pass rate is 50%, and the mean change is −0.5 (−50 percentage points). Two cases regress. Statistical evidence remains **inconclusive** with only four cases.

`run` prints only its stored run ID and exits 0 even when assertions fail. This allows a failing baseline to be recorded. `compare` owns the gate: 0 means the chosen gate passed, 1 means it failed, and 2 means configuration/input failed. To require an initially all-passing suite, inspect its results or compare against a known all-passing baseline.

If this desktop’s bundled Python cannot load an editable installation, use `pip install '.[dev]'` instead. The existing `.venv` here already has that working regular installation.

## Inspect the API

```sh
uvicorn tracewright.api:create_app --factory --host 127.0.0.1 --port 8000
```

Open [interactive API documentation](http://127.0.0.1:8000/docs). Endpoints:

- `GET /health`
- `GET /runs?limit=100`
- `GET /runs/{id}` — assertion outcomes, redacted outputs/events, errors, durations
- `GET /compare?baseline=<id>&candidate=<id>&tolerance=0&alpha=0.05`

Set `TRACEWRIGHT_DB` for both CLI and server, or use CLI `--db PATH` **before** the subcommand. SQLite stores immutable run snapshots using transactional inserts and parameterized queries. Reads are bounded to 1,000 run summaries. No API endpoint executes arbitrary agents.

## Write an agent and suite

Install your own agent module as a package, or use `PYTHONPATH=. tracewright run ... --agent my_agent:answer --revision <version>` from its directory.

An agent is a synchronous callable `agent(inputs: dict, trace: Trace, seed: int) -> JSON value`. It receives a fresh input copy for every trial. Emit events with `trace.emit("tool.call", {...})`; outputs and exceptions are captured automatically. Use the supplied seed in your own RNG; Tracewright does not promise reproducibility from remote models or seed-ignoring agents.

```python
# my_agent.py
import random

def answer(inputs, trace, seed):
    rng = random.Random(seed)
    trace.emit("lookup", {"query": inputs["query"]})
    return {"answer": "hello", "sample": rng.random()}
```

```json
{
  "schema_version": 1,
  "name": "greeting",
  "version": "1.0.0",
  "cases": [{
    "id": "hello",
    "input": {"query": "greet me"},
    "assertions": [
      {"kind": "equals", "path": ["answer"], "expected": "hello"},
      {"kind": "contains", "path": ["answer"], "expected": "ell"},
      {"kind": "type", "path": ["sample"], "expected": "number"}
    ]
  }]
}
```

Paths are arrays of object keys or nonnegative list indexes. An empty path targets the whole output. All assertions must pass; missing paths fail. `equals` requires matching Python types at the selected value, then value equality. `contains` uses string substring, list membership, or object key membership. `type` supports JSON string, number, boolean, object, array, and null. Booleans do not count as numbers.

Keep suites in version control and bump their version when changing cases. A canonical SHA-256 includes all suite content, so a forgotten version bump cannot silently compare different suites. Comparisons require matching fingerprints, repeat counts, seeds, and case/trial pairs. `--revision` records your declared agent/model/prompt revision; it is not automatic provenance verification. Baselines are selected explicitly by immutable run ID.

## Regression policy and statistics

Each case gets the fraction of repeated trials that pass **all** assertions. The report averages candidate-minus-baseline changes equally over cases. Trial keys are paired, but matching seed labels do not guarantee shared randomness for external agents.

The default `--gate observed` fails if any case's pass-rate drop exceeds `--tolerance` (a fraction between 0 and 1). This is a deterministic policy on observed outcomes, **not a significance test**. It can be noisy for stochastic agents. `--gate none` only reports. `--gate statistical` passes only if the overall interval establishes noninferiority; both regression and inconclusive results fail closed.

For n cases, case differences lie in [−1, 1]. The two-sided Hoeffding interval is:

```
mean difference ± sqrt(2 * log(2 / alpha) / n), clipped to [-1, 1]
```

At the default alpha of 0.05, this has at least 95% coverage **under independent, representative case sampling**. It is intentionally conservative and often uninformative for small suites. Repeated trials do not inflate n. Overlapping cases, shared agent state, or correlated provider failures can violate independence. A handpicked fixed suite supports descriptive conclusions about those cases; the interval does not certify real-world reliability. No uncertainty estimate is provided for individual cases or runtime. Repeated model selection and multiple comparisons require a separate predeclared correction/holdout policy.

A statistical regression requires the upper endpoint below `-tolerance`; noninferiority requires the lower endpoint at least `-tolerance`. Otherwise, the result is inconclusive. Equal observed scores alone do not prove noninferiority.

## Trace privacy and execution boundary

Sensitive dictionary keys (password, secret, token, authorization, API key, cookie), email addresses, bearer tokens, and `sk-` keys are masked recursively. Add exact secret values without putting them in command arguments:

```sh
tracewright run examples/calculator.v1.json --agent tracewright.sample:baseline --revision demo --secret-env MY_API_KEY
```

Assertions evaluate raw output in memory before redaction; the database contains redacted results, not raw suite inputs or expected values. Explicit events are snapshotted and redacted at emission. Exception messages are discarded; only the exception class survives. Redaction may remove useful evidence and is not comprehensive PII detection. Keep original versioned suites outside the database. Do not put secrets in case IDs or metadata: redaction can change identifiers.

**Trusted local agents only:** imports and agent code run in-process with your permissions. There is no timeout, memory limit, sandbox, stdout/stderr interception, authentication, or secret scanner. Agent prints can leak data and disrupt run-ID capture. Do not expose the API publicly. See [SECURITY.md](SECURITY.md).

## Development and CI

```sh
pytest -q
```

Tests cover validation, assertion semantics, redaction, exceptions, input isolation, suite mismatch, repeat handling, comparison math, storage, API responses, and real CLI subprocesses. [GitHub Actions](.github/workflows/ci.yml) runs tests on Python 3.11 and 3.12, proves the sample regression fails, and uploads its JSON report. The sample intentionally expects a failure; replace that expectation with a normal compare command for your own candidate gate.

[requirements-tested.txt](requirements-tested.txt) records the environment used for the local test run. Install it before `pip install --no-deps -e .` to reproduce those dependency versions. It is a tested snapshot, not a hash-verified cross-platform lock.

See [architecture](docs/architecture.md), [verification results](docs/verification.md), and [contributing](CONTRIBUTING.md). The code is MIT licensed.

## Next milestones

1. Isolated worker processes with enforced time/resource budgets, structured cancellation, and bounded trace sizes.
2. Strong provenance: Git SHA, prompt/model/config hashes; controlled stochastic fixtures and predeclared statistical power experiments.
3. PostgreSQL and migrations when concurrent workers, ingestion queues, authentication, or shared deployments justify them.
4. Human-labeled evaluation sets with explicit rubrics and held-out validation, then optional LLM judges. Measure agreement, bias, drift, and uncertainty before claiming calibration. No LLM judge is implemented or claimed calibrated in this MVP.

Implementation references: [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/) and [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/).
