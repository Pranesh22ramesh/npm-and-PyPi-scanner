import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.ml.schema import read_csv, validate_training
from app.ml.aggregation import aggregate_packages

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--dataset',default='dataset/primary_size_matched_dataset.csv')
    args=parser.parse_args()
    data=validate_training(read_csv(Path(args.dataset).read_bytes()))
    print(f'Valid: {len(data)} version pairs, {data.package.nunique()} packages, {aggregate_packages(data).shape[1]} aggregated features')
