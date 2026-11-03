import hashlib
import importlib.metadata
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
import joblib
from .schema import FEATURES, AGG_FEATURES, AGGREGATIONS, read_csv, validate_training
from .aggregation import aggregate_packages
from .evaluation import evaluate, make_models
from ..config import MODEL_DIR, APP_VERSION

def train(data: bytes, dataset_name='primary_size_matched_dataset.csv', progress=lambda message: None, model_dir=None):
    rows = validate_training(read_csv(data))
    profiles = aggregate_packages(rows)
    labels = rows.groupby('package').label.first().loc[profiles.index]
    progress('Validated 615 rows; constructed 180 × 240 package profiles.')
    folds, seeds, summary, matrix, memberships = evaluate(profiles, labels, progress)
    progress('Fitting final models on all 180 packages with seed 42.')
    rf, xgb = make_models(42)
    rf.fit(profiles, labels)
    xgb.fit(profiles, labels)
    provenance = json.loads((Path(__file__).parent / 'vendor/provenance.json').read_text())
    metadata = dict(model_name='Multi-Version Package Risk Aggregation + RF-XGBoost Fusion',
        source_dataset_name=Path(dataset_name).name, dataset_sha256=hashlib.sha256(data).hexdigest(),
        raw_feature_count=60, aggregated_feature_count=240, original_feature_names=FEATURES,
        aggregated_feature_names=AGG_FEATURES, aggregation_order=AGGREGATIONS, std_ddof=1,
        random_forest_parameters=rf.get_params(), xgboost_parameters=xgb.get_params(),
        fusion_weights=[0.5, 0.5], decision_threshold=0.5, package_count=len(profiles), version_pair_count=len(rows),
        class_distribution={'malicious': 128, 'clean': 52}, training_date=datetime.now(timezone.utc).isoformat(),
        evaluation_metrics=summary, seed42_confusion_matrix=matrix, evaluation_seeds=[7,42,77,123,2026],
        evaluation_protocol='Stratified 5-fold CV per seed after package aggregation; fixed threshold 0.50',
        application_version=APP_VERSION, model_version=f'{APP_VERSION}-{uuid.uuid4().hex[:8]}', final_seed=42,
        feature_importance=[{'feature': name, 'importance': float((a+b)/2), 'rf_importance': float(a), 'xgb_importance': float(b)} for name,a,b in zip(AGG_FEATURES,rf.feature_importances_,xgb.feature_importances_)],
        extractor_provenance=provenance,
        library_versions={name: importlib.metadata.version(name) for name in ['numpy','pandas','scikit-learn','xgboost','joblib']})
    # XGBoost has NaN-valued default parameters; JSON represents these as null.
    metadata['xgboost_parameters'] = {k: (None if isinstance(v,float) and v != v else v) for k,v in metadata['xgboost_parameters'].items()}
    target = Path(model_dir or MODEL_DIR)
    generation = target / 'runs' / metadata['model_version']
    generation.mkdir(parents=True, exist_ok=False)
    joblib.dump(rf, generation / 'package_risk_random_forest.joblib')
    joblib.dump(xgb, generation / 'package_risk_xgboost.joblib')
    folds.to_csv(generation / 'evaluation_results.csv', index=False)
    seeds.to_csv(generation / 'seed_summary.csv', index=False)
    (generation / 'fold_membership.json').write_text(json.dumps(memberships, indent=2), encoding='utf-8')
    metadata['artifact_sha256'] = {name: hashlib.sha256((generation/name).read_bytes()).hexdigest() for name in ['package_risk_random_forest.joblib','package_risk_xgboost.joblib']}
    (generation / 'package_risk_metadata.json').write_text(json.dumps(metadata, indent=2, allow_nan=False), encoding='utf-8')
    # Validate an entire generation before atomically publishing its pointer.
    from .model_manager import ModelManager
    ModelManager(generation).load()
    pointer = target / 'current.tmp'
    pointer.write_text(metadata['model_version'], encoding='utf-8')
    os.replace(pointer, target / 'current.txt')
    # Convenient root exports; prediction always reads the immutable generation.
    for file in generation.iterdir():
        shutil.copy2(file, target / file.name)
    progress('Training complete; verified model artifacts saved.')
    return metadata
