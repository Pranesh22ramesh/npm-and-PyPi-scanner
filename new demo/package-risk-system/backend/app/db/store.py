import json
import sqlite3
import uuid
from datetime import datetime, timezone
from ..config import DATA_DIR

def connect():
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    db = sqlite3.connect(DATA_DIR/'research.sqlite3', timeout=30)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    with connect() as db:
        db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS scan_history (
          id TEXT PRIMARY KEY, package_name TEXT, registry TEXT, versions_analyzed TEXT,
          version_pair_count INTEGER, rf_score REAL, xgb_score REAL, fused_score REAL,
          prediction TEXT, model_version TEXT, created_at TEXT, result_json TEXT);
        CREATE TABLE IF NOT EXISTS training_runs (
          id TEXT PRIMARY KEY, dataset_name TEXT, package_count INTEGER, accuracy REAL,
          precision REAL, recall REAL, f1 REAL, roc_auc REAL, model_version TEXT, created_at TEXT);
        CREATE TABLE IF NOT EXISTS jobs (
          id TEXT PRIMARY KEY, kind TEXT, status TEXT, message TEXT, result_json TEXT, created_at TEXT);
        ''')

def save_scan(result):
    result['id'] = uuid.uuid4().hex
    result['created_at'] = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        db.execute('INSERT INTO scan_history VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (result['id'],result['package'],result['registry'],json.dumps(result['version_pairs']),result['version_pairs_used'],
             result['random_forest_score'],result['xgboost_score'],result['model_score'],result['prediction'],result['model_version'],result['created_at'],json.dumps(result)))
    return result

def scans(limit=100, offset=0):
    with connect() as db:
        return [json.loads(row[0]) for row in db.execute('SELECT result_json FROM scan_history ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit,offset))]

def scan(identifier):
    with connect() as db:
        row = db.execute('SELECT result_json FROM scan_history WHERE id=?',(identifier,)).fetchone()
    return json.loads(row[0]) if row else None

def save_training(meta):
    m = meta['evaluation_metrics']
    with connect() as db:
        db.execute('INSERT INTO training_runs VALUES (?,?,?,?,?,?,?,?,?,?)', (uuid.uuid4().hex,meta['source_dataset_name'],meta['package_count'],*[m[k]['mean'] for k in ['accuracy','precision','recall','f1','roc_auc']],meta['model_version'],meta['training_date']))

def dashboard():
    with connect() as db:
        total = db.execute('SELECT COUNT(*),AVG(fused_score) FROM scan_history').fetchone()
        unique_packages = db.execute('SELECT COUNT(*) FROM (SELECT DISTINCT package_name,registry FROM scan_history)').fetchone()[0]
        predictions = dict(db.execute('SELECT prediction,COUNT(*) FROM scan_history GROUP BY prediction').fetchall())
        registries = dict(db.execute('SELECT registry,COUNT(*) FROM scan_history GROUP BY registry').fetchall())
        features = {}
        bands = {'Low':0,'Moderate':0,'Elevated':0,'High':0}
        for row in db.execute('SELECT result_json FROM scan_history'):
            result = json.loads(row[0])
            score = result['model_score']
            bands['Low' if score<.3 else 'Moderate' if score<.5 else 'Elevated' if score<.75 else 'High'] += 1
            for category in result.get('feature_categories',[]):
                features[category] = features.get(category,0)+1
    return {'total':total[0], 'unique_packages':unique_packages, 'average_score':total[1], 'predictions':predictions, 'registries':registries,'risk_distribution':bands,'feature_categories':features,'recent':scans(8)}
