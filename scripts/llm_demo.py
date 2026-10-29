"""Paid opt-in run. Missing configuration fails before any API request."""
import json
import os
from pathlib import Path
from tracewright.models import Suite
from tracewright.runner import evaluate
from tracewright.store import Store
from tracewright.compare import compare
from tracewright.llm_demo import BASE_PROMPT,CANDIDATE_PROMPT,prompt_hash


def main():
    if not os.getenv('OPENAI_API_KEY') or not os.getenv('OPENAI_MODEL'):
        raise SystemExit('Configure OPENAI_API_KEY and OPENAI_MODEL locally; never paste or commit your key.')
    suite=Suite.model_validate_json((Path(__file__).resolve().parents[1]/'examples/inventory-llm.v1.json').read_text())
    store=Store(secrets=(os.environ['OPENAI_API_KEY'],))
    records=[]
    for name,prompt in [('baseline',BASE_PROMPT),('candidate',CANDIDATE_PROMPT)]:
        run=evaluate(suite,'tracewright.llm_demo:'+name,agent_ref='tracewright.llm_demo:'+name,
            revision=name+'-'+prompt_hash(prompt)[:12],secrets=(os.environ['OPENAI_API_KEY'],),timeout=100)
        run['provenance']={'model':os.environ['OPENAI_MODEL'],'prompt_sha256':prompt_hash(prompt)}
        store.save(run);records.append(run)
    report=compare(*records)
    Path('reports').mkdir(exist_ok=True)
    Path('reports/llm-comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if any(row['error'] for run in records for row in run['results']):
        raise SystemExit('Live run incomplete: inspect errors; do not claim an LLM regression from infrastructure failures.')
    if report['baseline_pass_rate'] != 1:
        raise SystemExit('Baseline did not pass every case; inspect evidence before attributing a change to the prompt.')
    return 1 if report['observed_regressions'] else 0


if __name__=='__main__':raise SystemExit(main())
