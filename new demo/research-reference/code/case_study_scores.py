"""
case_study_scores.py

Computes the out-of-fold model score for the three version pairs discussed in
Section 6.7 of the manuscript, using exactly the configuration recorded in
results/canonical_results.json: HistGradientBoostingClassifier(max_iter=300),
class-weighted, under StratifiedGroupKFold(5) grouped on package, on the primary
size-matched dataset (360 malicious / 255 controls).

Each case score is the mean of the three out-of-fold probabilities obtained with seeds
42, 7 and 123.

The script also prints the confusion matrix at threshold 0.5 under two conventions,
because they are not the same quantity and the manuscript uses the first:

  * seed 42 alone, which is the convention behind `confusion_at_0.5` in
    results/canonical_results.json and behind Figure 10 and Section 6.8;
  * the three-seed mean probability thresholded at 0.5, which is the convention
    behind the case scores below.

An independent re-run of this script reproduces the seed-42 matrix to within about
two observations out of 615. The residual is small and does not indicate a different
model or dataset; minor differences in fold allocation can occur across scikit-learn
versions, so each run records the version it used in the output file.

Usage:
    python code/case_study_scores.py
"""

import json
import os

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.utils.class_weight import compute_sample_weight

SEEDS = [42, 7, 123]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIMARY = os.path.join(ROOT, "data", "features", "primary_size_matched_dataset.csv")
WITHIN = os.path.join(ROOT, "data", "features", "features_v6_clean.csv")
OUT = os.path.join(ROOT, "results", "case_study_scores.json")

NOTES = {
    "primary_size_matched": (
        "The manuscript quotes the seed-42 matrix for this design; canonical_results.json "
        "records 294/66/85/170 for it. The three-seed mean is a different estimator and is "
        "reported here only because the case scores use it."
    ),
    "within_package": (
        "The matrices in this section are reported for diagnostic context only. "
        "canonical_results.json does not define a threshold-0.5 confusion matrix for the "
        "within-package design; that design is summarised there by ROC-AUC and PR-AUC."
    ),
}

CASES = [
    ("twokey", "1.0.4", "1.0.5"),
    ("@weirdorg/config", "1.0.2", "1.0.3"),
    ("@woody-mrs-potato/utils-banking", "1.0.7", "1.0.8"),
]

META = {"package", "ecosystem", "label", "version_before", "version_after",
        "origin", "gap", "consecutive", "size_ok"}


def oof_scores(path):
    df = pd.read_csv(path)
    feats = [c for c in df.columns if c not in META]
    X = df[feats].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    y = df["label"].to_numpy(dtype=int)
    groups = df["package"].astype(str).to_numpy()

    oof = np.zeros((len(SEEDS), len(df)), dtype=float)
    for si, seed in enumerate(SEEDS):
        splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
        for tr, te in splitter.split(X, y, groups):
            clf = HistGradientBoostingClassifier(max_iter=300, random_state=seed)
            clf.fit(X[tr], y[tr], sample_weight=compute_sample_weight("balanced", y[tr]))
            oof[si, te] = clf.predict_proba(X[te])[:, 1]

    mean_score = oof.mean(axis=0)
    pred = (mean_score >= 0.5).astype(int)
    return df, y, mean_score, oof, pred


def confusion(y, prob):
    pred = (prob >= 0.5).astype(int)
    return {
        "tp": int(((pred == 1) & (y == 1)).sum()),
        "fn": int(((pred == 0) & (y == 1)).sum()),
        "fp": int(((pred == 1) & (y == 0)).sum()),
        "tn": int(((pred == 0) & (y == 0)).sum()),
    }


def main():
    results = {}
    for name, path, desc in (
        ("primary_size_matched", PRIMARY,
         "primary_size_matched_dataset.csv (360 malicious / 255 size-matched clean controls)"),
        ("within_package", WITHIN,
         "features_v6_clean.csv (360 malicious / 347 same-package controls)"),
    ):
        df, y, mean_score, oof, pred = oof_scores(path)
        cm = {
            "seed_42_only": confusion(y, oof[0]),
            "three_seed_mean_probability": confusion(y, mean_score),
            "note": NOTES[name],
        }

        out = {
            "config": {
                "model": "HistGradientBoostingClassifier(max_iter=300), class-weighted",
                "cv": "StratifiedGroupKFold(5) grouped on package",
                "seeds": SEEDS,
                "dataset": desc,
                "score": "mean out-of-fold predicted probability over the three seeds",
                "threshold": 0.5,
                "sklearn_version": sklearn.__version__,
            },
            "confusion_at_0.5": cm,
            "cases": [],
        }

        for pkg, vb, va in CASES:
            m = ((df["package"].astype(str) == pkg) &
                 (df["version_before"].astype(str) == vb) &
                 (df["version_after"].astype(str) == va))
            if not m.any():
                out["cases"].append({"package": pkg, "pair": f"{vb} -> {va}", "error": "not found"})
                continue
            i = int(np.flatnonzero(m.to_numpy())[0])
            out["cases"].append({
                "package": pkg,
                "pair": f"{vb} -> {va}",
                "label": int(y[i]),
                "score": round(float(mean_score[i]), 3),
                "score_by_seed": [round(float(v), 3) for v in oof[:, i]],
                "predicted_at_0.5": int(mean_score[i] >= 0.5),
            })
        results[name] = out

    json.dump(results, open(OUT, "w"), indent=2)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
