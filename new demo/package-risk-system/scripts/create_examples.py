"""Generate clearly identified fixtures and fetch a real, new package example."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.ml.schema import FEATURES,read_csv
from app.ml.feature_extraction import registry_rows

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    examples=root/'examples';examples.mkdir(exist_ok=True)
    (examples/'feature_template.csv').write_text(','.join(['package','previous_version','current_version',*FEATURES])+'\n')
    rows=registry_rows('is-number','npm',3,progress=print)
    rows.to_csv(examples/'new_package_features.csv',index=False)
    body={'package':'is-number','version_pairs':[{'previous_version':r.previous_version,'current_version':r.current_version,'features':{f:float(r[f]) for f in FEATURES}} for _,r in rows.iterrows()]}
    (examples/'new_package_request.json').write_text(json.dumps(body,indent=2))
    print('Saved actual registry-extracted is-number features and API request.')
