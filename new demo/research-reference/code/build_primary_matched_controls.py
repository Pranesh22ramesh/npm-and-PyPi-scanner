"""
build_primary_matched_controls.py

Reproduces the PRIMARY size-matched evaluation set used for the headline result
(ROC-AUC = 0.801). Reads the 360 malicious pairs and the 477-control clean pool,
performs nearest-neighbour matching within ecosystem on the number of source files in
the candidate archive, and writes the matched dataset plus a manifest.

Rule: a control c matches malicious m if same ecosystem and
      |log1p(files_total_c) - log1p(files_total_m)| <= log(3),
      i.e. the candidate archive file count differs by at most a factor of three.
Each control is used at most once. The full positive class is retained: of the 360
malicious pairs, 255 receive an admissible control and 105 do not, and the manifest
reports both counts. The evaluation set is therefore 360 malicious against 255
controls (n = 615, prevalence 0.586).

Usage:  python code/build_primary_matched_controls.py --seed 42
Outputs: primary_size_matched_dataset.csv   (malicious + matched controls, with 'label')
         primary_matching_manifest.json     (counts, seed, rule, per-ecosystem breakdown)
"""
import argparse, json, os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "features")
RESULTS_DIR = os.path.join(ROOT, "results")

RULE_RATIO = 3.0  # size ratio; implemented as |log1p diff| <= log(RULE_RATIO)

def build(seed: int, clean_path: str, controls_path: str):
    mal = pd.read_csv(clean_path, dtype={"package": str, "ecosystem": str,
                                         "version_before": str, "version_after": str})
    mal = mal[mal.label.astype(int) == 1].copy()
    pool = pd.read_csv(controls_path, dtype={"package": str, "ecosystem": str,
                                             "version_before": str, "version_after": str})
    pool["label"] = 0
    thr = np.log(RULE_RATIO)

    pool = pool.copy(); pool["_used"] = False
    picked = []
    for _, m in mal.sample(frac=1, random_state=seed).iterrows():
        cand = pool[(pool.ecosystem == m.ecosystem) & (~pool._used)]
        if not len(cand):
            continue
        d = (np.log1p(cand.files_total.astype(float)) - np.log1p(float(m.files_total))).abs()
        j = d.idxmin()
        if d.loc[j] > thr:
            continue
        pool.loc[j, "_used"] = True
        picked.append(j)

    controls = pool.loc[picked].drop(columns="_used")
    matched_mal = mal.iloc[: len(controls)] if False else mal  # all malicious retained; unmatched reported
    n_matched = len(controls)
    dataset = pd.concat([mal, controls], ignore_index=True, sort=False)
    dataset["label"] = dataset["label"].astype(int)

    manifest = {
        "seed": seed,
        "matching_rule": "size ratio <= 3 within ecosystem (|log1p(s1)-log1p(s2)| <= log 3) on files_total",
        "n_malicious_input": int(len(mal)),
        "n_control_pool": int(len(pool)),
        "n_controls_matched": int(n_matched),
        "n_malicious_unmatched": int(len(mal) - n_matched),
        "final_n": int(len(dataset)),
        "prevalence": round(float((dataset.label == 1).mean()), 4),
        "per_ecosystem": {
            eco: {
                "malicious": int(((mal.ecosystem == eco)).sum()),
                "controls": int((controls.ecosystem == eco).sum()),
            }
            for eco in sorted(dataset.ecosystem.unique())
        },
    }
    dataset.to_csv(os.path.join(DATA_DIR, "primary_size_matched_dataset.csv"), index=False)
    json.dump(manifest, open(os.path.join(RESULTS_DIR, "primary_matching_manifest.json"), "w"), indent=2)
    return manifest

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--clean", default=os.path.join(DATA_DIR, "features_v6_clean.csv"))
    ap.add_argument("--controls", default=os.path.join(DATA_DIR, "features_v6_controls.csv"))
    args = ap.parse_args()
    man = build(args.seed, args.clean, args.controls)
    print(json.dumps(man, indent=2))
