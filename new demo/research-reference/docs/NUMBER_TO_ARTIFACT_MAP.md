# Number-to-artifact map

Every quantitative claim in the manuscript traces to one file in this repository.
This is the reproducibility contract. Section 6.9 of the paper is authoritative; the
original random-CV tables (Sections 6.1-6.8) are superseded and kept only to show the
size of the correction.

All corrected results use `HistGradientBoostingClassifier(max_iter=300)`, class-weighted,
under `StratifiedGroupKFold(5)` grouped on package, averaged over seeds 42, 7 and 123.

## Primary detection result (size-matched clean controls)

Reproduce with: `python code/build_primary_matched_controls.py --seed 42`
which writes `data/features/primary_size_matched_dataset.csv` (360 malicious / 255 controls).

| quantity | value | file |
|---|---|---|
| ROC-AUC | 0.8012 +/- 0.0063 | results/canonical_results.json |
| PR-AUC | 0.8464 +/- 0.0049 | results/canonical_results.json |
| nested grouped CV F1 | 0.7922 [0.7297, 0.8452] | results/canonical_results.json |
| dataset | 360 malicious / 255 controls (n=615); 105 malicious pairs have no admissible control and are retained | results/primary_matching_manifest.json |
| prevalence | 0.5854 (360 / 615) | results/canonical_results.json |
| size-only baseline | ROC-AUC 0.7063, PR-AUC 0.7361 | results/canonical_results.json |
| matching rule | candidate archive file count within a factor of 3, within ecosystem, without replacement | results/primary_matching_manifest.json |
| confusion matrix at threshold 0.5 (seed 42) | 294 / 66 / 85 / 170, F1 0.7957 | results/canonical_results.json |

## Three control designs (central finding)

| design | ROC-AUC | PR-AUC | file |
|---|---|---|---|
| within-package | 0.5510 | 0.5453 | results/revision_results_v6.json (row "3. + per-package cap") |
| size-matched (primary) | 0.8012 | 0.8464 | results/canonical_results.json |
| unmatched clean | 0.8751 | 0.8363 | results/revision_results_v6.json (row "4. malicious vs clean controls") |

## Per-ecosystem (out-of-fold subsets of the single unified model)

| ecosystem | n | ROC-AUC | PR-AUC | chance |
|---|---|---|---|---|
| npm | 527 | 0.8104 | 0.8620 | 0.5996 |
| PyPI | 88 | 0.7991 | 0.7996 | 0.5000 |

(results/canonical_results.json; the PyPI row rests on 88 observations and is indicative.)

## Version context (measured on the primary malicious pairs, within-package design)

Reproduce with: `python code/version_context_experiment.py`
Uses the true predecessor features (entropy_before, ast_nodes_before, delta_*) that these
pairs carry. Because only same-package controls have predecessor features, this is a
within-package-design measurement on the same 360 malicious pairs used for detection
(n = 682, prevalence 0.528).

| condition | package-grouped PR-AUC | random PR-AUC |
|---|---|---|
| correct predecessor | 0.7175 | 0.7369 |
| candidate release only | 0.6940 | 0.7002 |
| shuffled predecessor | 0.6739 | 0.6964 |
| wrong-package predecessor | 0.6706 | 0.6771 |
| **gain (correct - shuffled)** | **+0.0436** | **+0.0405** |

(results/version_context_primary_final.json. `results/version_context_results.json` is an
earlier experiment on a different sample and is marked SUPERSEDED; do not cite it.)

## Calibration and low-budget operating points

Reproduce: calibration cell in `notebooks/07_reviewer_revision_experiments.ipynb`.
All operating points are pooled out-of-fold predictions across the three seeds.

| quantity | value | file |
|---|---|---|
| Brier score | 0.2274 | results/calibration_and_operating_points.json |
| ECE | 0.2027 | results/calibration_and_operating_points.json |
| recall @ 0.1% FPR | 0.0500 (prec 1.0000) | results/calibration_and_operating_points.json |
| recall @ 0.5% FPR | 0.0731 (prec 0.9634) | results/calibration_and_operating_points.json |
| recall @ 1% FPR | 0.1037 (prec 0.9412) | results/calibration_and_operating_points.json |
| recall @ 5% FPR | 0.3426 (prec 0.9069) | results/calibration_and_operating_points.json |
| recall @ 10% FPR | 0.4861 (prec 0.8735) | results/calibration_and_operating_points.json |
| recall @ 20% FPR | 0.6333 (prec 0.8182) | results/calibration_and_operating_points.json |

The operating points inside `results/canonical_results.json` are seed 42 only and are not
the values quoted in Table 9 of the manuscript.

## Leakage and confounding diagnostics (Section 6.9.2)

These quantify the inflation present in the **original** submission, so they are computed
on `data/features/features_original.csv` (n = 2,311), not on the corrected data.

Reproduce with: `python code/export_leakage_diagnostics.py`, which writes
`results/leakage_diagnostics.json`.

| quantity | value | key in results/leakage_diagnostics.json |
|---|---|---|
| random-CV F1, no package grouping | 0.892 | random_cv.mean_f1 |
| package-grouped CV F1 | 0.729 | package_grouped_cv.mean_f1 |
| inflation from leakage | 0.163 | leakage_gap_f1 |
| feature-signature grouping F1 | 0.891 | feature_signature_grouped_cv.mean_f1 |
| temporal hold-out F1 (pre/post 2026-01-01) | 0.310 | temporal_holdout.f1 |
| ecosystem-only baseline F1 | 0.717 | ecosystem_indicator_only.mean_f1 |
| transfer npm->PyPI ROC-AUC | 0.498 | leave_one_ecosystem_out.npm_to_pypi |
| transfer PyPI->npm ROC-AUC | 0.630 | leave_one_ecosystem_out.pypi_to_npm |

Each cross-validated entry carries its five fold-level scores for each of the three seeds
under `fold_f1_by_seed`, so the comparisons can be checked at run level rather than at the
mean. The leave-one-ecosystem-out runs drop the ecosystem indicator, which is constant
inside the training ecosystem.

`export_leakage_diagnostics.py` records the exact classifier, seeds and split definition it
used. It supersedes the diagnostic values quoted in earlier drafts, which came from earlier
experiment files that are no longer part of this archive.

## Case-study scores (Section 6.7)

Reproduce with: `python code/case_study_scores.py`, which writes
`results/case_study_scores.json`. Each score is the mean out-of-fold predicted
probability over seeds 42, 7 and 123.

The same script prints the confusion matrix at threshold 0.5 under both conventions,
so the run can be checked against the table above: the seed-42 matrix is the one the
manuscript quotes, and an independent re-run reproduces it to within about two
observations out of 615. Minor differences in fold allocation can occur across
scikit-learn versions, and each result file records the version that produced it; the
version used for the original canonical run was not recorded at the time.
The three-seed mean probability is a different estimator and gives a different matrix;
it is reported only because the case scores use it.

| pair | size-matched design | within-package design |
|---|---|---|
| twokey 1.0.4 -> 1.0.5 | 0.933 | 0.560 |
| @weirdorg/config 1.0.2 -> 1.0.3 | 1.000 | 0.011 |
| @woody-mrs-potato/utils-banking 1.0.7 -> 1.0.8 | 0.999 | 0.740 |

## Manual verification of the positive class

| quantity | value | file |
|---|---|---|
| pairs reviewed | 120 | results/manual_verification_summary.json |
| adjudicable pairs | 25 | results/manual_verification_summary.json |
| update-compromise rate (adjudicable subset) | 80.0% [60.9, 91.1] | results/manual_verification_summary.json |
| verified-subset ROC-AUC vs full class | 0.777 vs 0.832 | notebooks/06_remaining_requests.ipynb |

The per-pair adjudication labels are not redistributed; only the summary above is deposited.

## Runtime

median 0.90 s per candidate pair, 86.1% network, 69 us inference, 114 MB peak,
~3,400 pairs per hour single-threaded (results/runtime_measurements.json).

## Feature extraction

| what | where |
|---|---|
| signal patterns, original representation | code/supply_chain_detector.py |
| full extraction for the corrected 60-feature representation | extraction cell of notebooks/05_sample_hygiene.ipynb |
| corrected feature tables | data/features/features_v6_clean.csv, features_v6_controls.csv |
| original feature table | data/features/features_original.csv |

## Superseded original-protocol tables (kept to show the correction)

| table | file |
|---|---|
| Table 4 (six classifiers, random CV) | results/model_comparison_ci.csv |
| Table 5 (ablation, random CV) | results/ablation.csv |
