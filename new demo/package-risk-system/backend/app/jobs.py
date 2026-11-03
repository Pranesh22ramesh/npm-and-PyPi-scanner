import json
import threading
import uuid
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from .db.store import connect

executor = ThreadPoolExecutor(max_workers=2)
training_lock = threading.Lock()
capacity = threading.BoundedSemaphore(4)

def update(identifier, status, message, result=None):
    with connect() as db:
        db.execute('UPDATE jobs SET status=?,message=?,result_json=? WHERE id=?', (status,message,json.dumps(result) if result is not None else None,identifier))

def submit(kind, operation):
    if not capacity.acquire(blocking=False):
        raise ValueError('Job queue is full. Wait for an active job to complete.')
    if kind == 'training' and not training_lock.acquire(blocking=False):
        capacity.release()
        raise ValueError('A training run is already active.')
    identifier = uuid.uuid4().hex
    try:
        with connect() as db:
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?)',(identifier,kind,'queued','Waiting to start',None,datetime.now(timezone.utc).isoformat()))
    except Exception:
        capacity.release()
        if kind == 'training': training_lock.release()
        raise
    def run():
        try:
            update(identifier,'running','Starting...')
            result = operation(lambda msg:update(identifier,'running',msg))
            update(identifier,'completed','Complete',result)
        except Exception as exc:
            logging.exception('Job %s failed',identifier)
            update(identifier,'failed',str(exc) if isinstance(exc,ValueError) else 'Processing failed. See backend logs for details.')
        finally:
            capacity.release()
            if kind == 'training': training_lock.release()
    executor.submit(run)
    return {'job_id':identifier}

def get_job(identifier):
    with connect() as db:
        row = db.execute('SELECT * FROM jobs WHERE id=?',(identifier,)).fetchone()
    if row is None: return None
    result = dict(row)
    result['result'] = json.loads(result.pop('result_json') or 'null')
    return result
