import copy
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from tracewright.api import create_app
from tracewright.assertions import check
from tracewright.compare import compare
from tracewright.models import Assertion, Suite
from tracewright.redaction import redact
from tracewright.runner import Trace, evaluate
from tracewright.store import Store

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def suite():
    return Suite.model_validate_json((ROOT / 'examples/calculator.v1.json').read_text())


def good(inputs, trace, seed):
    return {'answer': inputs['a'] + inputs['b']}


def bad(inputs, trace, seed):
    return {'answer': abs(inputs['a'] + inputs['b'])}


def run(suite, agent=good, **kwargs):
    return evaluate(suite, agent, agent_ref='test:agent', revision='test-v1', **kwargs)


@pytest.mark.parametrize('output,kind,path,expected,passed', [
    ({'x': 2}, 'equals', ['x'], 2, True),
    ({'x': True}, 'equals', ['x'], 1, False),
    ({'x': True}, 'type', ['x'], 'number', False),
    ({'x': 1.5}, 'type', ['x'], 'number', True),
    ({}, 'equals', ['missing'], None, False),
    ([1], 'equals', [-1], 1, False),
    ({'x': 'hello'}, 'contains', ['x'], 'ell', True),
    ({'x': 12}, 'contains', ['x'], 1, False),
    ({'x': [1, 2]}, 'contains', ['x'], 2, True),
])
def test_assertions(output, kind, path, expected, passed):
    assert check(output, Assertion(kind=kind, path=path, expected=expected)) is passed


def test_suite_validation(suite):
    data = suite.model_dump()
    data['cases'].append(data['cases'][0])
    with pytest.raises(ValidationError):
        Suite.model_validate(data)
    with pytest.raises(ValidationError):
        Assertion(kind='type', expected='nonsense')
    with pytest.raises(ValidationError):
        Suite.model_validate({**suite.model_dump(), 'schema_version': 2})


def test_redaction_recursive():
    value = {'password': 'pw', 'nested': [{'Authorization': 'abc', 'text': 'me@example.com Bearer abc.def sk-abcdef literal-value'}]}
    result = json.dumps(redact(value, ('literal-value',)))
    for secret in ('pw', 'abc.def', 'me@example.com', 'sk-abcdef', 'literal-value'):
        assert secret not in result
    assert value['password'] == 'pw'


def test_trace_snapshot():
    trace = Trace()
    payload = {'value': 1}
    trace.emit('event', payload)
    payload['value'] = 2
    assert trace.events[0]['data']['value'] == 1


def test_runner_error_and_input_isolation(suite):
    original = suite.model_dump()
    def broken(inputs, trace, seed):
        inputs['a'] = 42
        trace.emit('request', {'token': 'never-store'})
        raise RuntimeError('never-store')
    result = run(suite, broken, repeats=2)
    assert len(result['results']) == 8
    assert all(not r['passed'] and r['error'] == 'RuntimeError' for r in result['results'])
    assert 'never-store' not in json.dumps(result)
    assert suite.model_dump() == original


def test_assert_before_redaction(suite):
    case = suite.cases[0]
    case.assertions = [Assertion(kind='equals', path=['token'], expected='raw-secret')]
    result = run(suite, lambda i,t,s: {'token': 'raw-secret'})
    assert result['results'][0]['passed']
    assert 'raw-secret' not in json.dumps(result)


def test_non_json_output_is_failure(suite):
    result = run(suite, lambda i,t,s: {'x': float('nan')})
    assert all(r['error'] == 'ValueError' for r in result['results'])


def test_fingerprint_and_compatibility(suite):
    a = run(suite)
    assert a['suite_hash'] == run(suite)['suite_hash']
    suite.cases[0].input['a'] = 42
    with pytest.raises(ValueError, match='suite_hash'):
        compare(a, run(suite))


@pytest.mark.parametrize('change', ['repeats', 'seed'])
def test_comparison_configuration(suite, change):
    a = run(suite)
    with pytest.raises(ValueError, match=change):
        compare(a, run(suite, **{change: 2}))


def test_regression_report_and_no_pseudoreplication(suite):
    a, b = run(suite, repeats=10), run(suite, bad, repeats=10)
    report = compare(a, b)
    assert report['baseline_pass_rate'] == 1
    assert report['candidate_pass_rate'] == .5
    assert report['delta'] == -.5
    assert report['observed_regressions'] == ['both-negative', 'negative']
    assert report['statistical_status'] == 'inconclusive'
    assert report['interval'] == compare(run(suite), run(suite, bad))['interval']
    assert report['case_count'] == 4
    assert report['paired_trials'] == 40


def test_large_independent_case_formula(suite):
    suite.cases = [suite.cases[1].model_copy(update={'id': str(i)}, deep=True) for i in range(100)]
    report = compare(run(suite), run(suite, bad))
    assert report['statistical_status'] == 'regression'
    assert report['interval'][1] == pytest.approx(-1 + math.sqrt(2*math.log(40)/100))
    # Duplicating cases exercises the formula, NOT its independence assumption.


def test_pair_integrity(suite):
    a, b = run(suite), run(suite)
    b['results'].pop()
    with pytest.raises(ValueError, match='pairs'):
        compare(a, b)
    b = copy.deepcopy(a)
    b['results'].append(b['results'][0])
    with pytest.raises(ValueError, match='duplicate'):
        compare(a, b)


def test_storage_and_api(tmp_path, suite):
    db = tmp_path / 'runs.db'
    store = Store(db)
    a, b = run(suite), run(suite, bad)
    store.save(a)
    store.save(b)
    assert Store(db).get(a['id']) == a
    with TestClient(create_app(db)) as client:
        assert client.get('/health').status_code == 200
        assert len(client.get('/runs').json()) == 2
        assert client.get('/runs', params={'limit': -1}).status_code == 422
        assert client.get('/runs/missing').status_code == 404
        assert client.get('/runs/' + a['id']).json() == a
        report = client.get('/compare', params={'baseline': a['id'], 'candidate': b['id']})
        assert report.status_code == 200
        assert report.json()['delta'] == -.5
        assert client.get('/compare', params={'baseline': a['id'], 'candidate': b['id'], 'alpha': 0}).status_code == 422
        c = run(suite, seed=10)
        store.save(c)
        assert client.get('/compare', params={'baseline': a['id'], 'candidate': c['id']}).status_code == 409
    with pytest.raises(KeyError):
        store.get("' OR 1=1 --")


def test_cli_end_to_end(tmp_path):
    prefix = [str(Path(sys.executable).parent/'tracewright'), '--db', str(tmp_path/'demo.db')]
    def invoke(*args):
        return subprocess.run(prefix+list(args), cwd=ROOT, text=True, capture_output=True)
    a = invoke('run', 'examples/calculator.v1.json', '--agent', 'tracewright.sample:baseline', '--revision', 'base')
    b = invoke('run', 'examples/calculator.v1.json', '--agent', 'tracewright.sample:candidate', '--revision', 'candidate')
    assert a.returncode == b.returncode == 0, a.stderr + b.stderr
    report_path = tmp_path/'report.json'
    diff = invoke('compare', a.stdout.strip(), b.stdout.strip(), '--output', str(report_path))
    assert diff.returncode == 1
    assert json.loads(report_path.read_text())['delta'] == -.5
    assert invoke('compare', a.stdout.strip(), a.stdout.strip()).returncode == 0
    assert invoke('compare', a.stdout.strip(), a.stdout.strip(), '--gate', 'statistical').returncode == 1
    assert invoke('compare', 'missing', a.stdout.strip()).returncode == 2
    assert invoke('run', 'examples/calculator.v1.json', '--agent', 'tracewright.sample:baseline', '--revision', 'x', '--repeats', '0').returncode == 2
