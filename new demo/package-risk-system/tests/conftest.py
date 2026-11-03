import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))

@pytest.fixture(scope='session')
def dataset():
    from app.ml.schema import read_csv, validate_training
    return validate_training(read_csv((ROOT/'dataset/primary_size_matched_dataset.csv').read_bytes()))

@pytest.fixture
def client(tmp_path,monkeypatch):
    from app.db import store
    from app.main import app
    from fastapi.testclient import TestClient
    monkeypatch.setattr(store,'DATA_DIR',tmp_path)
    with TestClient(app) as client:
        yield client
