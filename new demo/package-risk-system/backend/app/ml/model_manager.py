import hashlib
import copy
import json
from pathlib import Path
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from .schema import FEATURES, AGG_FEATURES, AGGREGATIONS
from ..config import MODEL_DIR

MISMATCH = 'Model/schema mismatch. Retraining or compatible metadata required.'

class ModelManager:
    def __init__(self, directory=None):
        self.directory = Path(directory or MODEL_DIR)
        self.metadata = None
        self.rf = self.xgb = None
        self.error = None

    def load(self):
        self.metadata = self.rf = self.xgb = None
        try:
            folder = self.directory
            if (folder / 'current.txt').exists():
                version = (folder / 'current.txt').read_text().strip()
                if Path(version).name != version or '/' in version or '\\' in version:
                    raise ValueError(MISMATCH)
                folder = folder / 'runs' / version
            metadata_path = folder / 'package_risk_metadata.json'
            if not metadata_path.exists():
                self.error = 'No trained model available. Train the model first.'
                return self
            meta = json.loads(metadata_path.read_text(encoding='utf-8'))
            if not (meta['raw_feature_count'] == 60 and meta['aggregated_feature_count'] == 240
                    and meta['original_feature_names'] == FEATURES and meta['aggregated_feature_names'] == AGG_FEATURES
                    and meta['aggregation_order'] == AGGREGATIONS and meta['std_ddof'] == 1
                    and meta['fusion_weights'] == [0.5, 0.5] and meta['decision_threshold'] == 0.5):
                raise ValueError(MISMATCH)
            for name in ['package_risk_random_forest.joblib', 'package_risk_xgboost.joblib']:
                if hashlib.sha256((folder/name).read_bytes()).hexdigest() != meta['artifact_sha256'][name]:
                    raise ValueError(MISMATCH)
            # Only application-produced, trusted local artifacts are deserialized.
            rf = joblib.load(folder / 'package_risk_random_forest.joblib')
            xgb = joblib.load(folder / 'package_risk_xgboost.joblib')
            if not isinstance(rf, RandomForestClassifier) or not isinstance(xgb, XGBClassifier):
                raise ValueError(MISMATCH)
            for model in [rf, xgb]:
                if model.n_features_in_ != 240 or not np.array_equal(model.classes_, [0,1]) or model.feature_names_in_.tolist() != AGG_FEATURES:
                    raise ValueError(MISMATCH)
            self.rf, self.xgb, self.metadata, self.folder = rf, xgb, meta, folder
            self.error = None
        except Exception as exc:
            self.error = MISMATCH
            raise ValueError(MISMATCH) from exc
        return self

    def require(self):
        if self.metadata is None:
            raise ValueError(self.error or 'No trained model available. Train the model first.')
        return copy.copy(self)

manager = ModelManager()
