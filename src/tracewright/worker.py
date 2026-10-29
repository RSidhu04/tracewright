"""Single trusted-agent trial. stdout belongs to the protocol, not agent prints."""
import contextlib
import json
import os
import sys
from .runner import Trace, load_agent
from .assertions import check
from .models import Case


def main():
    request = json.load(sys.stdin)
    trace = Trace(tuple(request['secrets']))
    try:
        # Redirect OS-level stdout/stderr too, including native dependencies.
        protocol = os.dup(1)
        with open(os.devnull, 'w') as null:
            os.dup2(null.fileno(), 1)
            os.dup2(null.fileno(), 2)
            case = Case.model_validate(request['case'])
            output = load_agent(request['agent'])(case.input, trace, request['seed'])
            encoded = json.dumps(output, allow_nan=False)
            if len(encoded.encode()) > 100_000:
                raise ValueError('output too large')
            output = json.loads(encoded)
            checks = [check(output, a) for a in case.assertions]
            result = {'output': output, 'checks': checks, 'error': None, 'events': trace.events}
    except Exception as exc:
        result = {'output': None, 'checks': [False] * len(request['case']['assertions']),
                  'error': type(exc).__name__, 'events': trace.events}
    with os.fdopen(protocol, 'w') as stream:
        json.dump(result, stream, allow_nan=False)


if __name__ == '__main__':
    main()
