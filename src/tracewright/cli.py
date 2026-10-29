import argparse
import json
import os
import sys
from pathlib import Path
from .compare import compare
from .models import Suite
from .runner import evaluate, load_agent
from .store import Store


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tracewright local agent evaluation")
    parser.add_argument("--db", default=os.getenv("TRACEWRIGHT_DB", "tracewright.db"))
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("suite")
    run.add_argument("--agent", required=True)
    run.add_argument("--revision", required=True, help="Git SHA, model/prompt version, or descriptive revision")
    run.add_argument("--repeats", type=int, default=1)
    run.add_argument("--seed", type=int, default=0)
    run.add_argument("--secret-env", action="append", default=[], help="Environment variable whose value must be redacted")
    diff = sub.add_parser("compare")
    diff.add_argument("baseline")
    diff.add_argument("candidate")
    diff.add_argument("--tolerance", type=float, default=0)
    diff.add_argument("--alpha", type=float, default=.05)
    diff.add_argument("--gate", choices=["observed", "statistical", "none"], default="observed")
    diff.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        store = Store(args.db)
        if args.command == "run":
            suite = Suite.model_validate_json(Path(args.suite).read_text())
            secrets = tuple(os.environ[name] for name in args.secret_env)
            result = evaluate(suite, load_agent(args.agent), agent_ref=args.agent,
                              revision=args.revision, repeats=args.repeats, seed=args.seed, secrets=secrets)
            store.save(result)
            print(result["id"])
            return 0
        result = compare(store.get(args.baseline), store.get(args.candidate), args.tolerance, args.alpha)
        rendered = json.dumps(result, indent=2)
        if args.output:
            Path(args.output).write_text(rendered + "\n")
        print(rendered)
        failed = bool(result["observed_regressions"]) if args.gate == "observed" else (
            result["statistical_status"] != "noninferior" if args.gate == "statistical" else False)
        return 1 if failed else 0
    except (ValueError, OSError, KeyError, ImportError, AttributeError):
        # Do not echo validation inputs or exceptions: these can contain secrets.
        print("Tracewright error: check suite, agent, run IDs, configuration, and paths.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
