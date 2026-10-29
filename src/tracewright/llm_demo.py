"""Opt-in OpenAI tool-calling demo; no live requests are made by pytest or normal CI."""
import hashlib
import json
import os
import httpx
from pydantic import BaseModel, ConfigDict, StrictBool, StrictInt, StrictStr

CATALOG = {'empty': 0, 'boundary': 5, 'healthy': 12}
BASE_PROMPT = ('You are an inventory assistant. Use lookup_stock for the requested SKU. '
               'Recommend reorder when stock is less than OR EQUAL TO the user threshold. '
               'Return only the required JSON object, preserving SKU and stock exactly.')
CANDIDATE_PROMPT = BASE_PROMPT.replace('less than OR EQUAL TO', 'strictly less than')
TOOL = {'type':'function','name':'lookup_stock','description':'Look up stock in a synthetic read-only catalog.',
        'strict':True,'parameters':{'type':'object','properties':{'sku':{'type':'string','enum':list(CATALOG)}},
        'required':['sku'],'additionalProperties':False}}


class Answer(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sku: StrictStr
    stock: StrictInt
    reorder: StrictBool


def prompt_hash(prompt):
    return hashlib.sha256(prompt.encode()).hexdigest()


def run_agent(inputs, trace, *, prompt, model, client):
    sku, threshold = inputs.get('sku'), inputs.get('threshold')
    if sku not in CATALOG or type(threshold) is not int or threshold < 0:
        raise ValueError('invalid demo input')
    conversation=[{'role':'user','content':json.dumps({'sku':sku,'threshold':threshold})}]
    trace.emit('llm.config', {'model':model,'prompt_sha256':prompt_hash(prompt),'seed_supported':False})
    looked_up=False
    for turn in range(3):
        response=client.post('/responses',json={
            'model':model,'instructions':prompt,'input':conversation,'tools':[TOOL],
            'tool_choice':'required' if turn==0 else 'auto','parallel_tool_calls':False,
            'store':False,'include':['reasoning.encrypted_content'],'max_output_tokens':1500,
            'text':{'format':{'type':'json_schema','name':'inventory_decision','strict':True,
                             'schema':Answer.model_json_schema()}}})
        response.raise_for_status()
        body=response.json()
        if body.get('status')!='completed':
            raise ValueError('model response not completed')
        output=body.get('output',[])
        # Preserve all protocol items (including reasoning) for follow-up requests,
        # but do not log raw reasoning or encrypted state in the trace.
        conversation.extend(output)
        trace.emit('llm.response',{'turn':turn,'model':body.get('model',model),'usage':body.get('usage',{})})
        calls=[item for item in output if item.get('type')=='function_call']
        if calls:
            if len(calls)!=1:
                raise ValueError('one tool call per turn required')
            call=calls[0]
            arguments=json.loads(call['arguments'])
            if call.get('name')!='lookup_stock' or arguments != {'sku':sku}:
                raise ValueError('unexpected tool or arguments')
            result={'sku':sku,'stock':CATALOG[sku]}
            trace.emit('tool.call',{'tool':'lookup_stock','arguments':arguments})
            trace.emit('tool.result',result)
            looked_up=True
            conversation.append({'type':'function_call_output','call_id':call['call_id'],'output':json.dumps(result)})
            continue
        texts=[part['text'] for item in output if item.get('type')=='message'
               for part in item.get('content',[]) if part.get('type')=='output_text']
        if not looked_up or len(texts)!=1:
            raise ValueError('expected a tool-grounded final answer')
        return Answer.model_validate_json(texts[0]).model_dump()
    raise ValueError('model exceeded three-turn budget')


def _call(inputs,trace,prompt):
    key=os.environ.get('OPENAI_API_KEY')
    model=os.environ.get('OPENAI_MODEL')
    if not key or not model:
        raise RuntimeError('OPENAI_API_KEY and OPENAI_MODEL are required')
    with httpx.Client(base_url='https://api.openai.com/v1',
                      headers={'Authorization':'Bearer '+key},timeout=30) as client:
        return run_agent(inputs,trace,prompt=prompt,model=model,client=client)


def baseline(inputs,trace,seed):
    return _call(inputs,trace,BASE_PROMPT)


def candidate(inputs,trace,seed):
    return _call(inputs,trace,CANDIDATE_PROMPT)
