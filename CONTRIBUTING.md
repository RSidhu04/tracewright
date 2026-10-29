# Contributing

Use Python 3.11 or 3.12. Install `pip install -e '.[dev]'` in a virtual environment and run `pytest -q`. Set `TRACEWRIGHT_TEST_DATABASE_URL` to a disposable PostgreSQL database to exercise migrations and concurrent baseline writes. Tests without that variable skip only the PostgreSQL contract test.

Keep changes scoped, use synthetic data, and include behavioral tests. Preserve ingestion idempotency, baseline immutability, CLI exit codes, and suite compatibility rules. Add an Alembic revision for schema changes; do not edit an applied migration. Review both SQLite and PostgreSQL paths. New UI interactions must handle unauthorized/empty/error states and avoid inserting untrusted HTML.

Use meaningful commits describing implemented behavior, not fabricated dates or a simulated development timeline. Run Docker Compose smoke checks before merging deployment changes. For judge proposals, include a labeling rubric, human labels, held-out validation, disagreement analysis, and drift/calibration measurements. Model agreement alone is not ground truth.
