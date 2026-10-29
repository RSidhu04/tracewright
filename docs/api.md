# API usage

Start the service and set `TRACEWRIGHT_API_TOKEN` in your shell. Use `tracewright export RUN_ID --output run.json` to create the ingestion payload; the full contract is in `/openapi.json` and `records.py`.

```sh
curl -fsS http://localhost:8000/ready
curl -fsS -H "Authorization: Bearer $TRACEWRIGHT_API_TOKEN" http://localhost:8000/runs
curl -fsS -X POST -H "Authorization: Bearer $TRACEWRIGHT_API_TOKEN" \
  -H 'Content-Type: application/json' --data-binary @run.json http://localhost:8000/runs
```

Promote a run by posting `{"name":"main","version":1,"run_id":"YOUR-RUN-UUID","note":"Reviewed reference"}` to `/baselines`. A run may have failing assertions and still be selected as a reference; promotion is an explicit user decision, not an all-passing certification.

To compare a versioned reference, resolve `/baselines/main/1` to its immutable `run_id`, then call `/compare?baseline=BASE_ID&candidate=CAND_ID&tolerance=0&alpha=0.05`.

- 401: missing or wrong bearer token.
- 404: missing run or baseline version.
- 409: conflicting run ID, duplicate baseline version, or incompatible comparison.
- 413: request body over 2 MB, including chunked uploads.
- 422: invalid schema, trial coverage, inconsistent score/checks, or redaction invalidating an identity field.
- 503: database unavailable or schema not migrated.

Retries are safe for identical run ingestion. Baseline creation intentionally returns 409 on repeated name/version; inspect the existing version instead of assuming a retry created a new reference. Baseline list and run list accept `limit` (1–1000) and `offset` (nonnegative).
