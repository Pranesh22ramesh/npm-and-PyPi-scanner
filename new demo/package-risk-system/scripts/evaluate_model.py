import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.ml.schema import read_csv, validate_training
from app.ml.aggregation import aggregate_packages
from app.ml.evaluation import evaluate

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--dataset',default='dataset/primary_size_matched_dataset.csv')
    parser.add_argument('--output',default='evaluation')
    args=parser.parse_args()
    rows=validate_training(read_csv(Path(args.dataset).read_bytes()))
    profiles=aggregate_packages(rows)
    folds,seeds,summary,matrix,memberships=evaluate(profiles,rows.groupby('package').label.first().loc[profiles.index],print)
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    folds.to_csv(out/'evaluation_results.csv',index=False)
    seeds.to_csv(out/'seed_summary.csv',index=False)
    (out/'summary.json').write_text(json.dumps({'metrics':summary,'seed42_confusion_matrix':matrix},indent=2))
    print(seeds.to_string(index=False)); print(json.dumps(summary,indent=2))
