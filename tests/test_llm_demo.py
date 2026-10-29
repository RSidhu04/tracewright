import json
import httpx
import pytest
from tracewright.llm_demo import run_agent, BASE_PROMPT, CANDIDATE_PROMPT, baseline, prompt_hash
from tracewright.runner import Trace


def test_responses_tool_protocol_and_prompt_variants():
    for prompt,expected in [(BASE_PROMPT,True),(CANDIDATE_PROMPT,False)]:
        seen=[]
        reasoning={'type':'reasoning','id':'fixture-reasoning','summary':[],'encrypted_content':'fixture-protocol-state'}
        def respond(request):
            body=json.loads(request.content);seen.append(body)
            assert body['store'] is False
            if len(seen)==1:
                assert body['tool_choice']=='required'
                output=[reasoning,{'type':'function_call','name':'lookup_stock','call_id':'fixture-call','arguments':'{"sku":"boundary"}'}]
            else:
                assert reasoning in body['input']
                tool_output=body['input'][-1]
                assert tool_output['type']=='function_call_output'
                assert json.loads(tool_output['output'])=={'sku':'boundary','stock':5}
                output=[{'type':'message','content':[{'type':'output_text','text':json.dumps({'sku':'boundary','stock':5,'reorder':expected})}]}]
            return httpx.Response(200,json={'status':'completed','output':output,'model':'fixture-model'})
        trace=Trace()
        with httpx.Client(transport=httpx.MockTransport(respond),base_url='https://api.openai.com/v1') as client:
            answer=run_agent({'sku':'boundary','threshold':5},trace,prompt=prompt,model='fixture-model',client=client)
        assert answer['reorder'] is expected
        assert len(seen)==2
        assert 'fixture-protocol-state' not in str(trace.events)
        assert trace.events[0]['data']['prompt_sha256']==prompt_hash(prompt)
    assert prompt_hash(BASE_PROMPT)!=prompt_hash(CANDIDATE_PROMPT)


@pytest.mark.parametrize('mode',['wrong-tool','incomplete','no-tool','too-many-turns','bad-json'])
def test_reject_invalid_model_behavior(mode):
    def respond(request):
        output=[{'type':'function_call','name':'lookup_stock','call_id':'fixture-call','arguments':'{"sku":"boundary"}'}]
        if mode=='wrong-tool':output[0]['name']='execute_shell'
        if mode=='bad-json':output[0]['arguments']='not-json'
        if mode=='no-tool':output=[{'type':'message','content':[{'type':'output_text','text':'{}'}]}]
        return httpx.Response(200,json={'status':'incomplete' if mode=='incomplete' else 'completed','output':output})
    with httpx.Client(transport=httpx.MockTransport(respond),base_url='https://api.openai.com/v1') as client:
        with pytest.raises(ValueError):
            run_agent({'sku':'boundary','threshold':5},Trace(),prompt=BASE_PROMPT,model='fixture',client=client)


def test_missing_credentials_fail_without_network(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    with pytest.raises(RuntimeError):baseline({'sku':'empty','threshold':5},Trace(),0)
