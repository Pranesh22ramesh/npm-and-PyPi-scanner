# Delivery verification

- Official dataset validated: 615 rows, 360 malicious / 255 benign rows; 180 packages, 128 malicious / 52 clean profiles; 60 corrected numerical predictors.
- Full 25-fold, five-seed evaluation completed using the specified estimator parameters and fixed 0.50 decision threshold.
- Final 300-tree Random Forest and 250-tree XGBoost trained on all 180 package profiles; artifacts and metadata loaded successfully.
- Backend suite: **46 passed**. Includes exact equality between training and web-inference aggregation for all 180 real dataset packages, feature ordering/exclusion, probabilities, threshold, model loading/mismatch/tampering, API persistence, registry parsing and archive security.
- Frontend: TypeScript check and Vite production build passed.
- Browser suite: **4 passed**, covering all routes, mobile overflow, real feature CSV prediction, result evidence/history, validation errors, training schema validation and live npm scan completion.
- Full training API smoke check passed: upload → background job → all 25 folds → artifact publication → serving-model reload → prediction using the new model version.
- Live npm raw extraction succeeded for `is-number`, a package absent from the training dataset. Complete feature CSV and JSON request examples are included.
- Live PyPI raw extraction succeeded for `six` 1.16.0 → 1.17.0. **All 60 extracted values exactly equal the published dataset row.** The pinned online regression script and extracted feature record are included.
- Desktop and mobile screenshots were visually inspected. Local frontend is configured for http://127.0.0.1:5173 and backend for http://127.0.0.1:8011 because port 8000 was occupied by an existing service.
- Docker configuration is included but was **not executed**: Docker CLI was unavailable in this environment.

Measured mean cross-validation metrics: accuracy **90.78%**, precision **94.45%**, recall **92.63%**, F1 **93.39%**, ROC-AUC **96.08%**. Exact unrounded values, per-fold scores, seed summaries, fold membership, dependency versions and feature provenance are in `models/`.

These checks establish implementation consistency and runnable workflows. They do not establish malware ground truth for the example packages or guarantee performance on future data. Registry examples can produce high scores for ordinary packages; those scores remain screening signals.
