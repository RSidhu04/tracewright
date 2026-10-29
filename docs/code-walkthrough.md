# Explain Tracewright in your own words

This is a rehearsal guide, not evidence that you already understand the implementation. For each topic: read the code, close this page, explain it aloud for two minutes, then answer the follow-up without notes. Record what you could not explain. Do not claim independent authorship of AI-assisted work.

## 1. Transactions and uniqueness

Read `Store.save` and `Store.promote` in `src/tracewright/store.py`, then migration `0001_initial.py`.

**Two-minute outline:** A transaction groups a database operation into a unit that commits or rolls back. `engine.begin()` opens that boundary. Run IDs are unique; baseline identity is the composite `(name, version)` primary key. Two callers can both check that a version is absent, so an application-level check alone is unsafe. The database constraint arbitrates concurrent inserts: one commits and one receives an integrity error. Tracewright turns the losing baseline write into a conflict. For run ingestion, an identical redacted payload is a safe retry, while a different payload with the same ID is rejected. A foreign key ties each baseline to a stored run. The application exposes no update/delete methods, but an administrator can still edit the database; this is not tamper-proof storage.

**Live change:** Add a test that two concurrent promotions of the same version yield one winner. Explain why using `MAX(version)+1` without locking is unsafe.

## 2. Ingestion validation

Read `records.py` and the `POST /runs` endpoint in `api.py`.

**Two-minute outline:** A valid JSON document can still be an invalid experiment. Pydantic rejects unknown fields and enforces identifiers, sizes, finite durations, and strict booleans. The record validator checks trial uniqueness, seeds, and coverage: each case must contain exactly the configured number of repeats. It also checks that the reported pass flag agrees with assertion booleans and error presence. The API bounds actual request bytes, including chunked uploads, and validates again after redaction before storage. Error responses do not echo the raw submitted input, because that could expose credentials. These checks establish internal consistency, not honesty: an authenticated client can invent assertion results. We would need trusted execution/attestation for a stronger guarantee.

**Live change:** Add an ingestion test where a trial is missing or duplicated, and explain why both requests must fail instead of silently changing the denominator.

## 3. Subprocess timeouts

Read `isolated_trial` in `runner.py` and `worker.py`.

**Two-minute outline:** Each CLI trial launches a fresh Python worker. A serialized request arrives through stdin; stdout is reserved for a JSON response, while ordinary agent output is suppressed. The parent waits with a timeout. On POSIX a new process session lets it kill the process group on timeout, then collect the terminated process. The timeout becomes failed evidence rather than hanging the whole suite. Fresh workers also avoid ordinary module-global contamination across trials. Startup overhead is included in measured duration. This is not a hostile-code sandbox: the child still inherits privileges and environment, and malicious code can escape or exhaust resources. Direct Python callable evaluation remains an in-process integration path without this timeout.

**Live change:** Write a sleeping test agent, prove the timeout records failure, then explain what a hardened container/VM worker would add.

## 4. Redaction

Read `redaction.py`, `Trace.emit`, and `Store.save`.

**Two-minute outline:** We need raw values in memory for meaningful assertions, but should not persist recognizable secrets. The redactor traverses dictionaries and lists, masks values whose keys look sensitive, applies patterns for emails, bearer strings, and `sk-` credentials, and replaces configured exact values. Trace emission snapshots and redacts events immediately. Storage validates and redacts the entire result again, so external ingestion crosses the same boundary. Exceptions retain their class rather than a message containing secrets. Exact configured values help cover credentials patterns cannot recognize. This is best effort: it can miss PII or over-redact evidence, and changing rules does not clean historical records. It is not a substitute for permission boundaries or source-history scanning.

**Live change:** Add a nested secret fixture and verify the stored record lacks its value without changing the assertion outcome.

## 5. Suite fingerprints

Read `evaluate` in `runner.py` and `compare.py`.

**Two-minute outline:** A suite's human-readable version can be forgotten or mistyped. Tracewright also serializes the validated suite canonically using sorted keys, hashes it with SHA-256, and stores that fingerprint with every run. Inputs, assertions, IDs, and version metadata contribute to it. Comparison requires identical fingerprints, repeat settings, seeds, and trial pair keys. That prevents comparing a hard candidate suite against an easier baseline and calling the score difference a model regression. A source-order change can also change the hash even if the suite is semantically similar; conservative rejection is acceptable here. The hash proves matching supplied suite content, not that the evaluator is honest or that the claimed agent revision really ran.

**Live change:** Modify one expected answer without bumping the version and show that comparison still rejects the runs.

## 6. Hoeffding bounds and assumptions

Read `compare.py`, `docs/statistics.md`, and its mathematical test.

**Two-minute outline:** Each case contributes a candidate-minus-baseline pass-fraction difference in [-1,1]. We average these case differences. Hoeffding's inequality gives a conservative two-sided interval with radius `sqrt(2 log(2/alpha) / n)`, clipped to [-1,1]. The factor comes from the range width of two. Here n is the number of independent cases, not the number of repeated trials. More repeats improve a case's measured fraction but do not magically create independent tasks. Independence and representative sampling are assumptions; related calculator cases violate a naive population interpretation. The observed gate can fail for a known case even when the statistical interval remains inconclusive. Failure to detect significance does not prove equivalence. Selecting many prompts after looking at results also needs holdouts or multiple-comparison control.

**Live change:** Increase repeats from one to ten and demonstrate that n and the interval radius stay unchanged. Explain why this is intentional.

## 7. Docker and CI

Read `Dockerfile`, `compose.yaml`, and `.github/workflows/ci.yml`.

**Two-minute outline:** Docker packages the app and dependencies; Compose wires it to PostgreSQL. Database readiness precedes a one-shot migration job, and the API waits for migrations. The API runs as a non-root user with a read-only filesystem, and only loopback exposes its port. A named volume persists database state across container restarts. CI tests Python 3.11 and 3.12 with PostgreSQL, runs the deliberately broken comparison and expects exit 1, then builds Compose and exercises HTTP behavior and restart persistence. Gitleaks scans history. A separate write-enabled job reads only the comparison artifact to post a same-repository PR summary; it does not execute PR code. Fork PRs do not receive comment privileges. Green CI means the specified checks passed, not that every behavior is correct or deployment is secure.

**Live change:** Introduce a real test failure and explain why the intentionally expected demo regression is different from a failing test job.

## Self-assessment

For each topic, score 0 (cannot explain), 1 (can explain with notes), or 2 (can explain and change a test without notes). You are ready for that topic when you score 2 twice on different days. Keep a private list of weak areas. Start with the transaction race and the statistical assumptions—they reveal more understanding than memorizing framework names.
