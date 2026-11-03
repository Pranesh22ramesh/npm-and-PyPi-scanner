"""The ONLY aggregation implementation, shared by training and inference."""
import numpy as np
import pandas as pd
from .schema import FEATURES, AGGREGATIONS, AGG_FEATURES, validate_features

def aggregate_packages(rows: pd.DataFrame) -> pd.DataFrame:
    rows = validate_features(rows)
    grouped = rows.groupby('package', sort=True)[FEATURES]
    blocks = []
    for operation in AGGREGATIONS:
        block = grouped.std(ddof=1).fillna(0) if operation == 'std' else getattr(grouped, operation)()
        block.columns = [f'{f}__{operation}' for f in FEATURES]
        blocks.append(block)
    result = pd.concat(blocks, axis=1).loc[:, AGG_FEATURES]
    if not np.isfinite(result.to_numpy()).all():
        raise ValueError('Aggregated features overflowed; check input magnitudes.')
    return result
