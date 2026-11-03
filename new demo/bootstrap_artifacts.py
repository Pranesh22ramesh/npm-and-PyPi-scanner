import hashlib
import json
import pathlib
import shutil

root = pathlib.Path('package-risk-system')
for folder in ('backend/app/ml/vendor', 'dataset', 'models', 'scans', 'examples'):
    (root / folder).mkdir(parents=True, exist_ok=True)
reference = pathlib.Path('research-reference')
shutil.copy2(reference / 'data/features/primary_size_matched_dataset.csv', root / 'dataset')
shutil.copy2(reference / 'LICENSE', root / 'backend/app/ml/vendor/LICENSE')
notebook = json.loads((reference / 'notebooks/05_sample_hygiene.ipynb').read_text(encoding='utf-8'))
cell = ''.join(notebook['cells'][13]['source'])
source = 'import re, io, tarfile, zipfile, difflib, math, json\nfrom collections import Counter\n\n' + cell[:cell.rfind('\nlog(')] + '\n'
target = root / 'backend/app/ml/vendor/official_corrected.py'
target.write_text(source, encoding='utf-8')
provenance = {
    'repository': 'https://github.com/moatasem2005/Version-Context-and-Control-Construction-in-Machine-Learning-Detection-of-Malicious-Package-Updates',
    'commit': 'e090c96aa6fbe5ecbc59ec83063ea3ce6ebf9754',
    'source': 'notebooks/05_sample_hygiene.ipynb, cell 13',
    'changes': 'Added standard-library imports and removed final notebook log call. Feature functions unchanged.',
    'extractor_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
    'dataset_sha256': hashlib.sha256((root / 'dataset/primary_size_matched_dataset.csv').read_bytes()).hexdigest(),
}
(root / 'backend/app/ml/vendor/provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
print(json.dumps(provenance, indent=2))
