import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix
from xgboost import XGBClassifier

SEEDS = [7, 42, 77, 123, 2026]
METRICS = ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']

def make_models(seed):
    return (
        RandomForestClassifier(n_estimators=300, max_features='sqrt', class_weight='balanced', min_samples_leaf=1, random_state=seed, n_jobs=-1),
        XGBClassifier(n_estimators=250, learning_rate=0.04, max_depth=3, min_child_weight=3, subsample=0.90, colsample_bytree=0.80, reg_lambda=2.0, reg_alpha=0.10, eval_metric='logloss', random_state=seed, n_jobs=-1),
    )

def fuse(rf, xgb):
    return 0.5 * np.asarray(rf) + 0.5 * np.asarray(xgb)

def evaluate(profiles, labels, progress=lambda message: None):
    results, predictions42, actual42, memberships = [], [], [], []
    for seed in SEEDS:
        split = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
        for fold, (train, test) in enumerate(split.split(profiles, labels), 1):
            rf, xgb = make_models(seed)
            rf.fit(profiles.iloc[train], labels.iloc[train])
            xgb.fit(profiles.iloc[train], labels.iloc[train])
            score = fuse(rf.predict_proba(profiles.iloc[test])[:, 1], xgb.predict_proba(profiles.iloc[test])[:, 1])
            predicted = (score >= 0.5).astype(int)
            truth = labels.iloc[test]
            row = dict(seed=seed, fold=fold, train_packages=len(train), test_packages=len(test),
                       accuracy=accuracy_score(truth, predicted), precision=precision_score(truth, predicted, zero_division=0),
                       recall=recall_score(truth, predicted, zero_division=0), f1=f1_score(truth, predicted, zero_division=0), roc_auc=roc_auc_score(truth, score))
            results.append(row)
            memberships.append({'seed': seed, 'fold': fold, 'train': profiles.index[train].tolist(), 'test': profiles.index[test].tolist()})
            if seed == 42:
                predictions42.extend(predicted.tolist())
                actual42.extend(truth.tolist())
            progress(f'Seed {seed}, fold {fold}/5 complete ({len(results)}/25); ' + ', '.join(f'{metric}={row[metric]:.4f}' for metric in METRICS))
    folds = pd.DataFrame(results)
    seeds = folds.groupby('seed')[METRICS].mean().reset_index()
    progress('Seed-wise means:\n' + seeds.to_string(index=False))
    summary = {metric: {'mean': float(folds[metric].mean()), 'std': float(folds[metric].std(ddof=1)), 'min': float(folds[metric].min()), 'max': float(folds[metric].max())} for metric in METRICS}
    return folds, seeds, summary, confusion_matrix(actual42, predictions42, labels=[0, 1]).tolist(), memberships
