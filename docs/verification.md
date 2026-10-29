# Local verification

Executed on October 21, 2026 with Python 3.12.14 on macOS ARM64.

- Installed the built package and its dependencies in an isolated virtual environment.
- `python -m pytest -q`: **23 passed**, 1 third-party deprecation warning, 0.84 seconds.
- The warning is Starlette's notice that its HTTPX-based test client is deprecated in favor of HTTPX2. Tests currently pass; migrate the test dependency in a future maintenance change.
- Actual `tracewright` executable tested through subprocesses, including exit codes 0 (gate pass), 1 (regression/inconclusive statistical gate), and 2 (invalid configuration).
- Separate demo execution: four cases, three trials each, baseline 100%, candidate 50%; observed gate exit 1; statistical status inconclusive; interval [-1, 0.8581015157406195].
- Saved actual demo output in [sample-comparison.json](sample-comparison.json).
- FastAPI tested in-process using TestClient; no external server deployment was performed.
- GitHub Actions configuration was written but has not run on GitHub. Python 3.11 is configured there but was not tested locally.

The bundled desktop Python did not process the editable-install path file. A regular `pip install '.[dev]'` worked and was used for validation. Standard Python environments may use the documented editable installation. Dependency versions are recorded in `requirements-tested.txt`.

These results describe the synthetic calculator fixture, not measured performance or reliability of an LLM agent.
