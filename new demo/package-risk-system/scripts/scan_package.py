import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.ml.feature_extraction import registry_rows
from app.ml.inference import predict_rows
from app.ml.model_manager import manager
from app.ml.schema import read_csv
from app.db.store import init_db

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--registry',choices=['npm','pypi'])
    parser.add_argument('--package')
    parser.add_argument('--count',choices=['2','3','5','all'],default='3')
    parser.add_argument('--features',help='CSV input instead of raw registry mode')
    args=parser.parse_args()
    if not args.features and not (args.registry and args.package): parser.error('Use --features or both --registry and --package')
    init_db(); manager.load().require()
    rows=read_csv(Path(args.features).read_bytes()) if args.features else registry_rows(args.package,args.registry,args.count,progress=lambda m:print(m,file=sys.stderr))
    print(json.dumps(predict_rows(rows,args.registry or 'features'),indent=2))
