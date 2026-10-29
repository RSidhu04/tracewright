"""Import official harness summary outcomes; never execute untrusted patches here."""
import hashlib
import json
import uuid
from datetime import datetime, timezone


def import_report(report, manifest, revision):
    required = {'dataset', 'dataset_revision', 'instance_ids'}
    if set(manifest) != required or not all(isinstance(manifest[k], str) and manifest[k] for k in ('dataset','dataset_revision')):
        raise ValueError('manifest requires dataset, dataset_revision, instance_ids')
    ids = manifest['instance_ids']
    if not isinstance(ids, list) or not ids or len(set(ids)) != len(ids) or not all(isinstance(x,str) for x in ids):
        raise ValueError('instance IDs must be unique strings')
    resolved = report.get('resolved_ids')
    if not isinstance(resolved, list) or not all(isinstance(x,str) for x in resolved) or len(set(resolved)) != len(resolved) or not set(resolved) <= set(ids):
        raise ValueError('report resolved_ids must be unique and within the manifest')
    canonical = json.dumps({**manifest, 'instance_ids': sorted(ids)}, sort_keys=True)
    return {'id':str(uuid.uuid4()),'created_at':datetime.now(timezone.utc).isoformat(),
            'suite_name':manifest['dataset'],'suite_version':manifest['dataset_revision'],
            'suite_hash':hashlib.sha256(canonical.encode()).hexdigest(),
            'agent_ref':'swebench:harness-report','revision':revision,'repeats':1,'seed':0,
            'source':'swebench-import','provenance':{'dataset_revision':manifest['dataset_revision'],
                'report_sha256':hashlib.sha256(json.dumps(report,sort_keys=True).encode()).hexdigest()},
            'results':[{'case_id':i,'trial':0,'seed':0,'passed':i in resolved,'checks':[i in resolved],
                'output':{'resolved':i in resolved},'error':None,'duration_ms':0,'events':[]} for i in sorted(ids)]}
