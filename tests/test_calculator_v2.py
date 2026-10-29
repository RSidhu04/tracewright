import json
from pathlib import Path
import pytest
from tracewright.assertions import check
from tracewright.models import Suite
from tracewright.runner import Trace, evaluate
from tracewright.sample import baseline, candidate
from tracewright.compare import compare

ROOT=Path(__file__).resolve().parents[1]
SUITE=Suite.model_validate_json((ROOT/'examples/calculator.v2.json').read_text())

@pytest.mark.parametrize('case',SUITE.cases,ids=lambda c:c.id)
def test_calculator_contract(case):
    output=baseline(case.input,Trace(),0)
    assert all(check(output,a) for a in case.assertions)


def test_packaged_fixture_and_fingerprint():
    import tracewright
    packaged=Path(tracewright.__file__).parent/'fixtures/calculator.v2.json'
    assert Suite.model_validate_json(packaged.read_text())==SUITE
    a=evaluate(SUITE,baseline,agent_ref='baseline',revision='v2')
    b=evaluate(SUITE,candidate,agent_ref='candidate',revision='v2-bug')
    report=compare(a,b)
    assert len(SUITE.cases)==20
    assert report['baseline_pass_rate']==1
    assert report['candidate_pass_rate']==.75
    assert len(report['observed_regressions'])==5
    assert report['statistical_status']=='inconclusive'
    old=Suite.model_validate_json((ROOT/'examples/calculator.v1.json').read_text())
    with pytest.raises(ValueError,match='suite_hash'):
        compare(evaluate(old,baseline,agent_ref='baseline',revision='v1'),a)
