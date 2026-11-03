import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.ml.training import train
from app.db.store import init_db, save_training

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset',required=True)
    args = parser.parse_args()
    path = Path(args.dataset)
    metadata = train(path.read_bytes(),path.name,lambda message:print(message,flush=True))
    init_db()
    save_training(metadata)
    print(json.dumps(metadata['evaluation_metrics'],indent=2))
    print('Fold and seed results saved in models/evaluation_results.csv and models/seed_summary.csv')
