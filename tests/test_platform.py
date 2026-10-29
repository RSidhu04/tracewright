import copy
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from tracewright.api import create_app
from tracewright.records import RunRecord
from tracewright.runner import evaluate
from tracewright.models import Suite
from tracewright.sample import baseline
from tracewright.store import Store, Conflict

TOKEN = 'test-api-token-at-least-16'

@pytest.fixture
def record():
    suite = Suite.model_validate({'name':'test','version':'1','cases':[{'id':'one','input':{'a':1,'b':2},'assertions':[{'kind':'equals','path':['answer'],'expected':3}]}]})
    return evaluate(suite,baseline,agent_ref='tracewright.sample:baseline',revision='test')

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path/'api.db', api_token=TOKEN)) as client:
        client.headers['Authorization'] = 'Bearer ' + TOKEN
        yield client


def test_ingest_redact_idempotence_conflict(client, record):
    record['results'][0]['output'] = {'secret':'hide-me','text':'person@example.com'}
    response=client.post('/runs',json=record)
    assert response.status_code == 201
    assert client.post('/runs',json=record).status_code == 200
    stored=client.get('/runs/'+record['id']).json()
    assert 'hide-me' not in str(stored) and 'person@example.com' not in str(stored)
    record['revision']='changed'
    assert client.post('/runs',json=record).status_code == 409


def test_auth_fail_closed(tmp_path):
    with pytest.raises(RuntimeError):
        create_app(tmp_path/'closed.db', api_token='short')
    with TestClient(create_app(tmp_path/'auth.db', api_token=TOKEN)) as client:
        for path in ['/runs','/baselines','/compare?baseline=a&candidate=b']:
            assert client.get(path).status_code == 401
        assert client.post('/runs',json={}).status_code == 401
        assert client.get('/health').status_code == 200
        assert client.get('/ready').status_code == 200
        assert client.get('/').status_code == 200
        assert 'frame-ancestors' in client.get('/').headers['content-security-policy']


def test_baselines_immutable(client, record):
    client.post('/runs',json=record)
    value={'name':'main','version':1,'run_id':record['id']}
    assert client.post('/baselines',json=value).status_code == 201
    assert client.post('/baselines',json=value).status_code == 409
    value['version']=2
    assert client.post('/baselines',json=value).status_code == 201
    assert client.get('/baselines/main/1').json()['run_id']==record['id']
    assert len(client.get('/baselines').json())==2
    value.update(version=3,run_id=str(uuid.uuid4()))
    assert client.post('/baselines',json=value).status_code==404


@pytest.mark.parametrize('mutation', ['duplicate','incomplete','wrong_seed','wrong_pass','empty_checks'])
def test_reject_inconsistent_runs(client,record,mutation):
    if mutation=='duplicate': record['results'].append(copy.deepcopy(record['results'][0]))
    if mutation=='incomplete': record['repeats']=2
    if mutation=='wrong_seed': record['results'][0]['seed']=100
    if mutation=='wrong_pass': record['results'][0]['passed']=False
    if mutation=='empty_checks': record['results'][0]['checks']=[]
    assert client.post('/runs',json=record).status_code==422


def test_limits_and_validation_privacy(client,record):
    record['extra']='secret-data-that-must-not-echo'
    response=client.post('/runs',json=record)
    assert response.status_code==422 and 'secret-data' not in response.text
    assert client.post('/runs',content=b'x'*2_000_001).status_code==413
    assert client.get('/runs?offset=-1').status_code==422
    assert client.get('/baselines/missing/1').status_code==404


def test_postgres_contract(record):
    url=os.getenv('TRACEWRIGHT_TEST_DATABASE_URL')
    if not url: pytest.skip('Set TRACEWRIGHT_TEST_DATABASE_URL to a disposable PostgreSQL database')
    store=Store(url,migrate=True)
    assert store.engine.dialect.name=='postgresql'
    assert store.ready()
    assert store.save(record)
    assert not store.save(record)
    name='test-'+uuid.uuid4().hex[:10]
    def promote():
        try: return store.promote(name,1,record['id'])
        except Conflict: return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:promote(),range(2)))
    assert results.count('conflict')==1
    assert store.baseline(name,1)['run_id']==record['id']
    assert store.get(record['id'])['results']==record['results']
    store.engine.dispose()


def test_swebench_import_and_manifest_consistency():
    from tracewright.swebench import import_report
    from tracewright.compare import compare
    manifest={'dataset':'synthetic-swebench','dataset_revision':'fixture-v1','instance_ids':['repo__one-1','repo__two-2']}
    a=import_report({'resolved_ids':manifest['instance_ids']},manifest,'base')
    b=import_report({'resolved_ids':['repo__one-1']},manifest,'candidate')
    assert RunRecord.model_validate(a).source=='swebench-import'
    assert compare(a,b)['delta']==-.5
    with pytest.raises(ValueError): import_report({'resolved_ids':['foreign-id']},manifest,'bad')
    with pytest.raises(ValueError): import_report({'resolved_ids':['repo__one-1','repo__one-1']},manifest,'bad')
    changed={**manifest,'dataset_revision':'other'}
    with pytest.raises(ValueError):compare(a,import_report({'resolved_ids':[]},changed,'new'))


def test_isolated_worker_prints_and_timeout(tmp_path,monkeypatch):
    from tracewright.runner import isolated_trial
    from tracewright.models import Case
    from pathlib import Path
    fixture=tmp_path/'fixture_agent.py'
    fixture.write_text('import time\ndef noisy(i,t,s):\n print("never-print-this")\n return {"answer":3}\ndef slow(i,t,s):\n time.sleep(10)\n')
    monkeypatch.setenv('PYTHONPATH',str(tmp_path)+os.pathsep+str(Path(__file__).resolve().parents[1]/'src'))
    case=Case(id='one',input={},assertions=[{'kind':'equals','path':['answer'],'expected':3}])
    result=isolated_trial('fixture_agent:noisy',case,0,(),5)
    assert result['checks']==[True]
    assert 'never-print-this' not in str(result)
    assert isolated_trial('fixture_agent:slow',case,0,(),.2)['error']=='Timeout'


def test_trace_budget():
    from tracewright.runner import Trace
    trace=Trace()
    for _ in range(100):trace.emit('event',{})
    with pytest.raises(ValueError):trace.emit('too-many',{})
    with pytest.raises(ValueError):Trace().emit('too-large',{'text':'x'*10001})


def test_database_restart_and_migration_idempotence(tmp_path,record):
    path=tmp_path/'persist.db'
    first=Store(path);first.save(record);first.engine.dispose()
    second=Store(path);second.migrate()
    assert second.get(record['id'])['revision']=='test'
    assert second.ready()
    second.engine.dispose()
