"""Exact upstream feature function behind a fail-closed compatibility guard."""
import hashlib
import json
from pathlib import Path
import numpy as np
from .vendor import official_corrected as official
from .schema import FEATURES
from ..security.safe_archive import safe_map

BLOCKED = 'Feature extraction is not compatible with the trained model. Prediction has been blocked to avoid invalid results.'

def compatibility():
    path = Path(__file__).parent / 'vendor'
    try:
        info = json.loads((path / 'provenance.json').read_text())
        valid = hashlib.sha256((path / 'official_corrected.py').read_bytes()).hexdigest() == info['extractor_sha256']
        valid = valid and list(official.all_features({}, {}, 'npm')) == FEATURES
        return {'enabled': valid, 'reason': None if valid else BLOCKED, 'provenance': info}
    except Exception:
        return {'enabled': False, 'reason': BLOCKED}

def extract_pair(previous: bytes, current: bytes, ecosystem: str):
    if not compatibility()['enabled']:
        raise ValueError(BLOCKED)
    before, after = safe_map(previous, ecosystem), safe_map(current, ecosystem)
    try:
        features = official.all_features(before, after, ecosystem)
        if list(features) != FEATURES or not np.isfinite(list(features.values())).all():
            raise ValueError(BLOCKED)
    except Exception as exc:
        raise ValueError(BLOCKED) from exc
    return features
