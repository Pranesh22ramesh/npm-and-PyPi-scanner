"""Online regression against an actual official dataset row; no model prediction."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import numpy as np
from app.ml.schema import FEATURES,read_csv,validate_training
from app.ml.feature_extraction import registry_rows

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    data=validate_training(read_csv((root/'dataset/primary_size_matched_dataset.csv').read_bytes()))
    expected=data[(data.package=='six') & (data.version_before=='1.16.0') & (data.version_after=='1.17.0')].iloc[0]
    observed=registry_rows('six','pypi',selected=['1.16.0','1.17.0'],progress=print).iloc[0]
    np.testing.assert_array_equal(expected[FEATURES].to_numpy(dtype=float),observed[FEATURES].to_numpy(dtype=float))
    record={'package':'six','registry':'pypi','previous_version':'1.16.0','current_version':'1.17.0','features_compared':60,'exact_match':True,'features':{f:float(observed[f]) for f in FEATURES}}
    (root/'examples/extractor_compatibility_check.json').write_text(json.dumps(record,indent=2))
    print('PASS: all 60 features exactly match the published dataset row.')
