from .aggregation import aggregate_packages
from .schema import AGG_FEATURES, FEATURES, SIGNALS, validate_features
from .evaluation import fuse
from .model_manager import manager
from ..db.store import save_scan

def predict_rows(rows, registry='features', model=None, persist=True, progress=lambda text:None):
    active = (model or manager).require()
    rows = validate_features(rows, versions=True)
    progress('Constructing package risk profile...')
    profiles = aggregate_packages(rows)
    if profiles.columns.tolist() != active.metadata['aggregated_feature_names']:
        raise ValueError('Model/schema mismatch. Retraining or compatible metadata required.')
    progress('Running Random Forest...')
    rf = active.rf.predict_proba(profiles)[:,1]
    progress('Running XGBoost...')
    xgb = active.xgb.predict_proba(profiles)[:,1]
    progress('Combining model scores...')
    scores = fuse(rf,xgb)
    ranked = sorted(active.metadata['feature_importance'],key=lambda item:item['importance'],reverse=True)[:12]
    results = []
    for i,(package, profile) in enumerate(profiles.iterrows()):
        subset = rows[rows.package == package]
        pairs = []
        for _,row in subset.iterrows():
            observations = []
            if row.ih_install_hook_added > 0: observations.append('Install-hook indicator detected')
            if row.add_subprocess_exec > 0: observations.append('Subprocess indicator detected')
            if row.add_net_http > 0: observations.append('Network indicator detected')
            if row.added_lines > 1000: observations.append('Large source change (>1,000 added lines)')
            pairs.append({'previous_version':row.previous_version,'current_version':row.current_version,'status':'60 features validated','observations':observations or ['No added hook, subprocess or network indicators detected'], 'features':{f:float(row[f]) for f in FEATURES}})
        result = {'package':package,'registry':registry,'prediction':'malicious-risk' if scores[i]>=.5 else 'clean-risk',
            'model_score':float(scores[i]),'random_forest_score':float(rf[i]),'xgboost_score':float(xgb[i]),
            'version_pairs_used':len(subset),'model_version':active.metadata['model_version'],
            'warning':'Package-level screening result; does not identify a specific malicious release.',
            'score_notice':'Model score — not calibrated probability.',
            'interpretation':('This package profile resembles malicious-labeled package histories in the training dataset. This result is a screening signal and does not prove that a specific release contains malware.' if scores[i]>=.5 else 'This profile falls below the model screening threshold. A clean-risk result does not establish that the package is safe.'),
            'version_pairs':pairs,'feature_categories':[signal for signal in SIGNALS if (subset[f'add_{signal}']>0).any()],
            'indicators':[dict(item,value=float(profile[item['feature']])) for item in ranked],
            'indicator_notice':'Global mean tree importance with this profile’s values; not local contributions or causal explanations.'}
        results.append(save_scan(result) if persist else result)
    progress('Analysis complete.')
    return results
