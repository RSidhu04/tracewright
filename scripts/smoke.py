"""Real HTTP smoke test against a running app. Uses only synthetic records."""
import json
import os
import uuid
import httpx
from tracewright.models import Suite
from tracewright.runner import evaluate
from tracewright.sample import baseline, candidate


def main():
    client=httpx.Client(base_url=os.getenv('TRACEWRIGHT_URL','http://127.0.0.1:8000'),
        headers={'Authorization':'Bearer '+os.environ['TRACEWRIGHT_API_TOKEN']},timeout=30)
    assert client.get('/ready').status_code==200
    assert client.get('/').status_code==200
    assert client.get('/static/app.js').status_code==200
    assert httpx.get(str(client.base_url)+'/runs').status_code==401
    suite=Suite(name='http-smoke',version='1',cases=[{'id':'negative','input':{'a':-5,'b':2},'assertions':[{'kind':'equals','path':['answer'],'expected':-3}]}])
    a=evaluate(suite,baseline,agent_ref='sample:baseline',revision='smoke-base')
    b=evaluate(suite,candidate,agent_ref='sample:candidate',revision='smoke-candidate')
    a['results'][0]['events'].append({'name':'privacy','data':{'password':'must-not-persist'}})
    for run in (a,b): assert client.post('/runs',json=run).status_code==201
    assert client.post('/runs',json=a).status_code==200
    assert 'must-not-persist' not in client.get('/runs/'+a['id']).text
    promoted=client.post('/baselines',json={'name':'smoke-'+uuid.uuid4().hex[:8],'version':1,'run_id':a['id']})
    assert promoted.status_code==201
    comparison=client.get('/compare',params={'baseline':a['id'],'candidate':b['id']})
    assert comparison.status_code==200
    assert comparison.json()['delta']==-1
    assert comparison.json()['observed_regressions']==['negative']
    print(json.dumps({'http_smoke':'passed','baseline':a['id'],'candidate':b['id'],'regression_detected':True}))
    client.close()


if __name__=='__main__':main()
