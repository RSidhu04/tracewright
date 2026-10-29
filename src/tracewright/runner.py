import copy
import os
import signal
import subprocess
import sys
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
        if len(self.events) >= 100 or len(json.dumps(event).encode()) > 10_000:
            raise ValueError('trace event budget exceeded')
        self.events.append(redact(event, self.secrets))


def load_agent(spec):
    module, sep, name = spec.partition(":")
    if not sep:
        raise ValueError("agent must be module:callable")
    agent = getattr(importlib.import_module(module), name)
    if not callable(agent):
        raise ValueError("agent is not callable")
    return agent


def evaluate(suite: Suite, agent, *, agent_ref: str, revision: str, repeats=1, seed=0, secrets=(), timeout=None):
    if not 1 <= repeats <= 1000:
        raise ValueError("repeats must be between 1 and 1000")
    canonical = json.dumps(suite.model_dump(), sort_keys=True, separators=(",", ":"), allow_nan=False)
    rows = []
    for case in suite.cases:
        for trial in range(repeats):
            trace = Trace(secrets)
            started = time.perf_counter()
            try:
                if isinstance(agent, str):
                    result = isolated_trial(agent, case, seed + trial, secrets, timeout or 10)
                    output, checks, error = result['output'], result['checks'], result['error']
                    trace.events = result['events']
                else:
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


def isolated_trial(agent, case, seed, secrets, timeout):
    if timeout <= 0 or timeout > 3600:
        raise ValueError('timeout must be in (0, 3600]')
    request = json.dumps({'agent': agent, 'case': case.model_dump(), 'seed': seed, 'secrets': secrets})
    proc = subprocess.Popen([sys.executable, '-m', 'tracewright.worker'], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                            start_new_session=(os.name == 'posix'))
    try:
        out, _ = proc.communicate(request, timeout=timeout)
        if proc.returncode != 0:
            raise RuntimeError('worker exited')
        return json.loads(out)
    except subprocess.TimeoutExpired:
        if os.name == 'posix':
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
        proc.communicate()
        return {'output': None, 'checks': [False] * len(case.assertions), 'error': 'Timeout', 'events': []}
