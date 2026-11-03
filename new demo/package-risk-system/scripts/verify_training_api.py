"""Exercise the full upload → job → model hot-load path against a running backend."""
import argparse
import json
import time
from pathlib import Path
import httpx

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8011')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    with httpx.Client(base_url=args.url,timeout=60,trust_env=False) as client:
        before=client.get('/api/model/info').json()['metadata']['model_version']
        with (root/'dataset/primary_size_matched_dataset.csv').open('rb') as file:
            response=client.post('/api/train',files={'file':('primary_size_matched_dataset.csv',file,'text/csv')})
        response.raise_for_status()
        identifier=response.json()['job_id']
        deadline=time.monotonic()+300
        last=None
        while time.monotonic()<deadline:
            response=client.get('/api/jobs/'+identifier);response.raise_for_status();job=response.json()
            if job['message']!=last: print(job['message'],flush=True);last=job['message']
            if job['status']=='failed':raise RuntimeError(job['message'])
            if job['status']=='completed':break
            time.sleep(1)
        else:raise RuntimeError('Training verification timed out')
        info=client.get('/api/model/info').json()
        assert info['ready'] and info['metadata']['model_version']!=before
        assert len(client.get('/api/training/results').json()['folds'])==25
        request=json.loads((root/'examples/new_package_request.json').read_text())
        prediction=client.post('/api/predict/features',json=request);prediction.raise_for_status()
        assert prediction.json()['model_version']==info['metadata']['model_version']
        print('PASS: upload, 25-fold job, atomic publication, hot-load and new-model prediction.')
