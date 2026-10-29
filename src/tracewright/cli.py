import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
import httpx
from sqlalchemy.exc import SQLAlchemyError
from .compare import compare
from .models import Suite
from .records import BaselineRequest
from .runner import evaluate
from .store import Store
from .swebench import import_report


def main(argv=None):
    parser = argparse.ArgumentParser(description='Tracewright agent regression platform')
    parser.add_argument('--db', default=None, help='SQLite path or PostgreSQL URL; defaults to environment')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('migrate')
    run = sub.add_parser('run')
    run.add_argument('suite')
    run.add_argument('--agent', required=True)
    run.add_argument('--revision', required=True)
    run.add_argument('--repeats', type=int, default=1)
    run.add_argument('--seed', type=int, default=0)
    run.add_argument('--timeout', type=float, default=10, help='Seconds per isolated trial')
    run.add_argument('--secret-env', action='append', default=[])
    diff = sub.add_parser('compare')
    diff.add_argument('baseline')
    diff.add_argument('candidate')
    diff.add_argument('--tolerance', type=float, default=0)
    diff.add_argument('--alpha', type=float, default=.05)
    diff.add_argument('--gate', choices=['observed', 'statistical', 'none'], default='observed')
    diff.add_argument('--output')
    promote = sub.add_parser('baseline')
    promote.add_argument('name'); promote.add_argument('version', type=int); promote.add_argument('run_id')
    promote.add_argument('--note', default='')
    export = sub.add_parser('export'); export.add_argument('run_id'); export.add_argument('--output', required=True)
    upload = sub.add_parser('upload'); upload.add_argument('run_id'); upload.add_argument('--url', required=True)
    swe = sub.add_parser('import-swebench'); swe.add_argument('report'); swe.add_argument('--manifest', required=True); swe.add_argument('--revision',required=True)
    demo = sub.add_parser('demo'); demo.add_argument('--output', default='reports/demo.json')
    args = parser.parse_args(argv)
    try:
        secrets = tuple(filter(None, os.getenv('TRACEWRIGHT_REDACT_VALUES','').split(',')))
        store = Store(args.db, secrets=secrets)
        if args.command == 'migrate':
            store.migrate(); print('Schema is current'); return 0
        if args.command == 'run':
            if not 0 < args.timeout <= 3600: raise ValueError('invalid timeout')
            suite = Suite.model_validate_json(Path(args.suite).read_text())
            exact_secrets = secrets + tuple(os.environ[name] for name in args.secret_env)
            result = evaluate(suite, args.agent, agent_ref=args.agent, revision=args.revision,
                              repeats=args.repeats, seed=args.seed, secrets=exact_secrets, timeout=args.timeout)
            store.save(result); print(result['id']); return 0
        if args.command == 'baseline':
            body = BaselineRequest(name=args.name,version=args.version,run_id=args.run_id,note=args.note)
            print(json.dumps(store.promote(body.name,body.version,body.run_id,body.note))); return 0
        if args.command == 'export':
            Path(args.output).write_text(json.dumps(store.get(args.run_id),indent=2)+'\n'); return 0
        if args.command == 'upload':
            url = urlparse(args.url)
            if url.scheme != 'https' and not (url.scheme=='http' and url.hostname in ('127.0.0.1','localhost')):
                raise ValueError('HTTPS required except loopback')
            token = os.environ['TRACEWRIGHT_API_TOKEN']
            response = httpx.post(args.url.rstrip('/')+'/runs',json=store.get(args.run_id),
                                  headers={'Authorization':'Bearer '+token},timeout=30)
            response.raise_for_status(); print(json.dumps(response.json())); return 0
        if args.command == 'import-swebench':
            result=import_report(json.loads(Path(args.report).read_text()),json.loads(Path(args.manifest).read_text()),args.revision)
            store.save(result); print(result['id']); return 0
        if args.command == 'demo':
            suite=Suite(name='calculator',version='1.0.0',cases=[{'id':name,'input':{'a':a,'b':b},'assertions':[{'kind':'equals','path':['answer'],'expected':a+b}]} for name,a,b in [('positive',2,3),('negative',-5,2),('zero',2,-2),('both-negative',-2,-3)]])
            a=evaluate(suite,'tracewright.sample:baseline',agent_ref='tracewright.sample:baseline',revision='demo-baseline')
            b=evaluate(suite,'tracewright.sample:candidate',agent_ref='tracewright.sample:candidate',revision='demo-candidate')
            store.save(a);store.save(b)
            store.promote('demo-'+a['id'][:8],1,a['id'],'Synthetic calculator reference')
            result=compare(store.get(a['id']),store.get(b['id']))
            Path(args.output).parent.mkdir(parents=True,exist_ok=True)
            Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(result,indent=2)); return 0
        result=compare(store.get(args.baseline),store.get(args.candidate),args.tolerance,args.alpha)
        rendered=json.dumps(result,indent=2)
        if args.output:
            Path(args.output).parent.mkdir(parents=True,exist_ok=True)
            Path(args.output).write_text(rendered+'\n')
        print(rendered)
        failed=bool(result['observed_regressions']) if args.gate=='observed' else (
            result['statistical_status']!='noninferior' if args.gate=='statistical' else False)
        return 1 if failed else 0
    except (ValueError,OSError,KeyError,ImportError,AttributeError,SQLAlchemyError,httpx.HTTPError):
        print('Tracewright error: check configuration, schema, credentials, run IDs, and input files.',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
