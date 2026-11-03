"""Runs only the trusted static extractor, never submitted package code."""
import json
import sys
from pathlib import Path
from .base_feature_extractor import extract_pair

if __name__ == '__main__':
    try:
        request = json.loads(Path(sys.argv[1]).read_text())
        archives = [Path(p).read_bytes() for p in request['archives']]
        features = [extract_pair(a,b,request['ecosystem']) for a,b in zip(archives,archives[1:])]
        Path(sys.argv[2]).write_text(json.dumps({'features': features}), encoding='utf-8')
    except Exception as exc:
        Path(sys.argv[2]).write_text(json.dumps({'error': str(exc)}), encoding='utf-8')
        sys.exit(1)
