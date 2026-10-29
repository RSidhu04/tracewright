import copy
import hashlib
import importlib
import json
import time
import uuid
from datetime import datetime, timezone
from .assertions import check
from .models import Suite
from .redaction import redact


class Trace:
    """Agents explicitly emit JSON-compatible events. No stdout interception."""
    def __init__(self, secrets=()):
        self.events = []
        self.secrets = secrets

    def emit(self, name, data):
        # Snapshot now, so later mutations cannot change recorded evidence.
        event = json.loads(json.dumps({"name": name, "data": data}, allow_nan=False))
        self.events.append(redact(event, self.secrets))


def load_agent(spec):
    module, sep, name = spec.partition(":")
    if not sep:
        raise ValueError("agent must be module:callable")
    agent = getattr(importlib.import_module(module), name)
    if not callable(agent):
        raise ValueError("agent is not callable")
    return agent


def evaluate(suite: Suite, agent, *, agent_ref: str, revision: str, repeats=1, seed=0, secrets=()):
    if not 1 <= repeats <= 1000:
        raise ValueError("repeats must be between 1 and 1000")
    canonical = json.dumps(suite.model_dump(), sort_keys=True, separators=(",", ":"), allow_nan=False)
    rows = []
    for case in suite.cases:
        for trial in range(repeats):
            trace = Trace(secrets)
            started = time.perf_counter()
            try:
                output = agent(copy.deepcopy(case.input), trace, seed + trial)
                output = json.loads(json.dumps(output, allow_nan=False))
                checks = [check(output, assertion) for assertion in case.assertions]
                error = None
            except Exception as exc:
                output, checks = None, [False] * len(case.assertions)
                # Exception messages may contain credentials; retain only class.
                error = type(exc).__name__
            rows.append({"case_id": case.id, "trial": trial, "seed": seed + trial,
                         "passed": all(checks), "checks": checks, "output": output,
                         "error": error, "duration_ms": (time.perf_counter()-started)*1000,
                         "events": trace.events})
    return redact({"id": str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat(),
                   "suite_name": suite.name, "suite_version": suite.version,
                   "suite_hash": hashlib.sha256(canonical.encode()).hexdigest(),
                   "agent_ref": agent_ref, "revision": revision, "repeats": repeats,
                   "seed": seed, "results": rows}, secrets)
