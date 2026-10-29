# Contributing

Use Python 3.11+, create a virtual environment, install `pip install -e '.[dev]'`, and run `pytest -q`. Keep changes scoped and include tests for behavioral changes. Use synthetic fixtures with no real credentials. Document assertion or comparison semantics when changing them. Preserve CLI exit codes and suite compatibility checks.

Before proposing a judge, supply human labels, the labeling rubric, held-out agreement measurements, and a calibration/drift evaluation plan. Do not present model agreement as ground truth.
