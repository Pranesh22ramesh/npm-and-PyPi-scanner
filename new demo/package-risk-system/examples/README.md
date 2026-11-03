# Example inputs

- `feature_template.csv`: exact required header, with no invented observations.
- `new_package_features.csv`: real `is-number` npm features, extracted using the preserved official corrected implementation. This package is absent from the 180 training packages.
- `new_package_request.json`: the same data as a complete API request, including all 60 features per pair.
- `extractor_compatibility_check.json`: live `six` 1.16.0 → 1.17.0 extraction, checked against the published dataset row for exact equality across all 60 values.

Recreate the new-package examples using `python scripts/create_examples.py`; this fetches the registry's current last three releases, so versions may change later. Recreate the pinned compatibility check using `python scripts/verify_live_extractor.py`.

These are input examples and compatibility checks, not evidence of malware in either package. A model score is a screening signal, not a calibrated probability or ground-truth label.
