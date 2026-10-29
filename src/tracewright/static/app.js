'use strict';
const $ = id => document.getElementById(id);
let token = '', offset = 0, lastReport = null;
const pageSize = 20;
function status(message, error=false) { $('status').textContent=message; $('status').className=error?'error':''; }
async function api(path, options={}) {
  if (!token) throw new Error('Connect with a workspace API token first.');
  const response = await fetch(path, {...options, headers:{'Authorization':`Bearer ${token}`,'Content-Type':'application/json'}});
  if (!response.ok) { const body=await response.json().catch(()=>({})); throw new Error(body.detail || `Request failed (${response.status})`); }
  return response.json();
}
function node(tag, text, cls) { const el=document.createElement(tag); if(text!==undefined)el.textContent=text; if(cls)el.className=cls; return el; }
function clearEvidence() { lastReport=null; $('download').disabled=true; $('report-title').textContent='Awaiting comparison'; $('report').replaceChildren(node('p','Choose compatible baseline and candidate runs.','muted')); $('evidence').hidden=true; $('evidence-json').textContent=''; }
function disconnect() { token=''; $('token').value=''; offset=0; clearEvidence(); $('run-rows').replaceChildren(); $('baseline-list').replaceChildren(); ['base','candidate','promote-run'].forEach(id=>$(id).replaceChildren()); ['run-count','pass-rate','baseline-count'].forEach(id=>$(id).textContent='—'); $('next').disabled=$('previous').disabled=true; status('Disconnected. Credentials and displayed evidence cleared.'); }
async function refresh() {
  const [runs,baselines]=await Promise.all([api(`/runs?limit=${pageSize}&offset=${offset}`),api('/baselines?limit=1000')]);
  $('run-count').textContent=runs.length; $('pass-rate').textContent=runs.length?`${(runs[0].pass_rate*100).toFixed(0)}%`:'—'; $('baseline-count').textContent=baselines.length;
  $('run-rows').replaceChildren();
  for(const run of runs){ const tr=node('tr'); const suite=node('td',run.suite_name); suite.append(node('small',run.revision)); tr.append(suite,node('td',run.id.slice(0,8)),node('td',`${(run.pass_rate*100).toFixed(0)}%`,'rate'),node('td',String(run.trials)),node('td',new Date(run.created_at).toLocaleString())); const cell=node('td'); const button=node('button','Inspect ↗','secondary'); button.onclick=()=>inspect(run.id); cell.append(button);tr.append(cell);$('run-rows').append(tr); }
  if(!runs.length){const tr=node('tr');const td=node('td','No runs on this page. Run the demo or ingest a trace.','empty');td.colSpan=6;tr.append(td);$('run-rows').append(tr);}
  for(const id of ['base','candidate','promote-run']){const previous=$(id).value;$(id).replaceChildren();for(const run of runs){const option=node('option',`${run.suite_name} / ${run.revision} · ${run.id.slice(0,8)}`);option.value=run.id;$(id).append(option);}if(runs.some(r=>r.id===previous))$(id).value=previous;}
  $('baseline-list').replaceChildren(); for(const baseline of baselines){ const card=node('div',`${baseline.name} · v${baseline.version}`,'baseline-card');card.append(node('small',` / ${baseline.run_id.slice(0,8)}`));$('baseline-list').append(card); }
  if(!baselines.length)$('baseline-list').append(node('p','No versions yet. Promote a reference run.','muted'));
  $('previous').disabled=offset===0;$('next').disabled=runs.length<pageSize;$('page').textContent=`Page ${offset/pageSize+1}`;
  status(`Connected. Loaded ${runs.length} runs and ${baselines.length} baseline versions.`);
}
async function inspect(id){try{const run=await api(`/runs/${id}`);$('evidence-title').textContent=`${run.suite_name} / ${run.revision}`;$('evidence-json').textContent=JSON.stringify(run,null,2);$('evidence').hidden=false;$('evidence').scrollIntoView({behavior:'smooth'});}catch(error){status(error.message,true);}}
$('connect').onsubmit=async event=>{event.preventDefault();token=$('token').value;$('token').value='';clearEvidence();offset=0;try{await refresh();}catch(error){disconnect();status(error.message,true);}};
$('disconnect').onclick=disconnect;
$('refresh').onclick=()=>refresh().catch(e=>status(e.message,true));
$('previous').onclick=()=>{offset=Math.max(0,offset-pageSize);refresh().catch(e=>status(e.message,true));};
$('next').onclick=()=>{offset+=pageSize;refresh().catch(e=>status(e.message,true));};
$('close-evidence').onclick=()=>{$('evidence').hidden=true;};
$('comparison').onsubmit=async event=>{event.preventDefault();clearEvidence();try{const query=new URLSearchParams({baseline:$('base').value,candidate:$('candidate').value,tolerance:$('tolerance').value,alpha:$('alpha').value});const report=await api(`/compare?${query}`);lastReport=report;$('report-title').textContent=report.observed_regressions.length?'Observed regression':'No observed regression';const area=$('report');area.replaceChildren(node('div',`${(report.delta*100).toFixed(1)} pp`,report.delta<0?'delta bad':'delta good'),node('p',`Pass rate: ${(report.baseline_pass_rate*100).toFixed(0)}% → ${(report.candidate_pass_rate*100).toFixed(0)}%`),node('p',`Statistical evidence: ${report.statistical_status}`),node('p',`Interval: [${report.interval.map(v=>(v*100).toFixed(1)).join(', ')}] pp · ${report.case_count} cases`));if(report.observed_regressions.length)area.append(node('p',`Regressed: ${report.observed_regressions.join(', ')}`,'bad'));area.append(node('div',report.caveat,'note'));$('download').disabled=false;status('Comparison complete. Observed policy and statistical evidence are shown separately.');}catch(error){status(error.message,true);}};
$('promotion').onsubmit=async event=>{event.preventDefault();try{await api('/baselines',{method:'POST',body:JSON.stringify({name:$('baseline-name').value,version:Number($('version').value),run_id:$('promote-run').value,note:'Promoted from dashboard'})});await refresh();status('Baseline version created. Existing versions cannot be overwritten.');}catch(error){status(error.message,true);}};
$('download').onclick=()=>{if(!lastReport)return;const url=URL.createObjectURL(new Blob([JSON.stringify(lastReport,null,2)],{type:'application/json'}));const a=node('a');a.href=url;a.download='tracewright-comparison.json';a.click();URL.revokeObjectURL(url);};
