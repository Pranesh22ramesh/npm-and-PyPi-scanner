"""
export_leakage_diagnostics.py

Recomputes the leakage and confounding diagnostics reported in Section 6.9.2 of the
manuscript and writes them to results/leakage_diagnostics.json, so that every one of
those numbers has a machine-readable source in this archive.

Quantities produced:
    random_cv_f1                 F1 under random stratified 5-fold CV (no package grouping)
    package_grouped_cv_f1        F1 under 5-fold CV grouped on package
    feature_signature_group_f1   F1 under 5-fold CV grouped on the exact feature vector
    ecosystem_only_f1            F1 of a classifier given only the ecosystem indicator
    transfer_npm_to_pypi         ROC-AUC, trained on npm, tested on PyPI
    transfer_pypi_to_npm         ROC-AUC, trained on PyPI, tested on npm

Not produced here:
    temporal_holdout_f1          F1 when training on pairs published before the median
                                 publication date and testing on pairs published after it

Not produced here:
    verified-positive ROC-AUC    requires the per-pair manual adjudication labels, which
                                 are summarised in results/manual_verification_summary.json
                                 but are not redistributed at pair level.

Usage:
    python code/export_leakage_diagnostics.py
"""

import json
import os

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedKFold, StratifiedGroupKFold
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.utils.class_weight import compute_sample_weight

SEEDS = [42, 7, 123]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "features")
OUT = os.path.join(ROOT, "results", "leakage_diagnostics.json")

SOURCE = "features_original.csv"   # the dataset of the original submission (Section 6.9.2)
META = {"package", "ecosystem", "label", "version_after_date"}


def load():
    df = pd.read_csv(os.path.join(DATA, SOURCE))
    df["eco_npm"] = (df["ecosystem"].astype(str).str.lower() == "npm").astype(int)
    feats = [c for c in df.columns if c not in META] 
    df[feats] = df[feats].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return df, feats


def model():
    return HistGradientBoostingClassifier(max_iter=300, random_state=0)


def cv_folds(X, y, groups, seed, grouped):
    """Return the five fold-level F1 scores for one seed."""
    if grouped:
        folds = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed).split(X, y, groups)
    else:
        folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed).split(X, y)
    scores = []
    for tr, te in folds:
        clf = model()
        clf.fit(X[tr], y[tr], sample_weight=compute_sample_weight("balanced", y[tr]))
        scores.append(round(float(f1_score(y[te], clf.predict(X[te]))), 4))
    return scores


def protocol(X, y, groups, grouped):
    """Mean F1 over seeds, with every fold-level value retained."""
    per_seed = {str(s): cv_folds(X, y, groups, s, grouped) for s in SEEDS}
    allv = [v for vs in per_seed.values() for v in vs]
    return {"mean_f1": round(float(np.mean(allv)), 4),
            "std_f1": round(float(np.std(allv)), 4),
            "fold_f1_by_seed": per_seed}


def main():
    df, feats = load()
    X = df[feats].to_numpy(dtype=float)
    y = df["label"].to_numpy(dtype=int)
    pkg = df["package"].astype(str).to_numpy()
    sig = pd.util.hash_pandas_object(df[feats], index=False).astype(str).to_numpy()
    eco = df["eco_npm"].to_numpy(dtype=bool)

    out = {
        "config": {
            "seeds": SEEDS,
            "model": "HistGradientBoostingClassifier(max_iter=300), class-weighted",
            "source": SOURCE,
            "n": int(len(df)),
            "n_features": len(feats),
            "sklearn_version": sklearn.__version__,
            "prevalence": round(float(y.mean()), 4),
            "note": ("These diagnostics quantify the inflation present in the original "
                     "submission, so they are computed on the dataset of the original "
                     "submission, as described in Section 6.9.2 of the manuscript."),
        },
        "random_cv": protocol(X, y, None, False),
        "package_grouped_cv": protocol(X, y, pkg, True),
        "feature_signature_grouped_cv": protocol(X, y, sig, True),
        "ecosystem_indicator_only": protocol(df[["eco_npm"]].to_numpy(dtype=float), y, pkg, True),
    }
    out["leakage_gap_f1"] = round(out["random_cv"]["mean_f1"] - out["package_grouped_cv"]["mean_f1"], 4)

    # temporal hold-out: train on the earlier half, test on the later half
    if "version_after_date" in df.columns:
        dates = pd.to_datetime(df["version_after_date"], errors="coerce", utc=True)
        ok = dates.notna().to_numpy()
        cut = pd.Timestamp("2026-01-01", tz="UTC")   # matches the pre/post-2026 split of Figure 1
        tr = (ok & (dates < cut).to_numpy())
        te = (ok & (dates >= cut).to_numpy())
        clf = model()
        clf.fit(X[tr], y[tr], sample_weight=compute_sample_weight("balanced", y[tr]))
        out["temporal_holdout"] = {
            "definition": "train on pairs whose candidate release was published before "
                          "2026-01-01, test on pairs published on or after that date "
                          "(the pre/post-2026 split shown in Figure 1)",
            "cutoff": str(cut),
            "n_train": int(tr.sum()),
            "n_test": int(te.sum()),
            "f1": round(float(f1_score(y[te], clf.predict(X[te]))), 4),
        }

    # leave-one-ecosystem-out: the ecosystem indicator is dropped, since it is
    # constant within the training ecosystem and carries no information there.
    tf = [c for c in feats if c != "eco_npm"]
    Xt = df[tf].to_numpy(dtype=float)
    transfer = {}
    for src, dst, name in ((True, False, "npm_to_pypi"), (False, True, "pypi_to_npm")):
        a, b = eco == src, eco == dst
        seeds = []
        for s in SEEDS:
            clf = HistGradientBoostingClassifier(max_iter=300, random_state=s)
            clf.fit(Xt[a], y[a], sample_weight=compute_sample_weight("balanced", y[a]))
            seeds.append(round(float(roc_auc_score(y[b], clf.predict_proba(Xt[b])[:, 1])), 4))
        transfer[name] = {"mean_roc_auc": round(float(np.mean(seeds)), 4), "by_seed": seeds}
    out["leave_one_ecosystem_out"] = transfer

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
