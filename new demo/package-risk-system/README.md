# Multi-Version Package Risk Analysis

A runnable local research workbench implementing **Multi-Version Package Risk Aggregation with Heterogeneous Ensemble Learning for Malicious npm and PyPI Package Detection**. FastAPI + SQLite backend, React + Vite + TypeScript + Tailwind frontend, real Random Forest/XGBoost artifacts, and the official corrected feature extractor.

The official dataset is included and the model has been trained. There are no fabricated dataset rows, placeholder predictions, or hard-coded proposed-model metrics. Raw npm/PyPI analysis is enabled because the official extraction code was located, preserved and verified.

## Run this checkout (Windows / PowerShell)

Requirements: Python 3.13 and Node.js 24 (the tested versions). Start in `package-risk-system`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-lock.txt
cd frontend
npm.cmd ci
cd ..
```

Start the backend in terminal 1:

```powershell
.\start-local.ps1
```

Equivalent command:

```powershell
cd backend
..\.venv\Scripts\python.exe run.py --port 8011
```

Start the frontend in terminal 2:

```powershell
cd frontend
npm.cmd run dev
```

Open **http://127.0.0.1:5173**. API documentation: **http://127.0.0.1:8011/docs**.

Port 8000 was already occupied in the development environment, so this checkout includes `frontend/.env.local` with `API_PROXY_TARGET=http://127.0.0.1:8011`. For a different backend port, update that setting and restart Vite. Without `.env.local`, Vite defaults to port 8000 and `backend/run.py` also defaults to 8000. The Docker setup uses port 8000 internally.

SQLite initializes automatically at `scans/research.sqlite3`. No separate database installation or migration command is needed. `scan_history`, `training_runs`, and durable job status tables are created at startup. Scans retain feature evidence and model identity; downloaded source files are not retained.

## Linux / macOS

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-lock.txt
cd frontend && npm ci && cd ..
cd backend && ../.venv/bin/python run.py --port 8011
# In a separate terminal, from project root:
cd frontend && npm run dev
```

Use the same `frontend/.env.local` proxy setting shown above. `requirements.txt` contains supported version ranges; `requirements-lock.txt` pins the versions used for the delivered trained artifacts. Retrain when changing the ML dependency versions. Model joblib files are trusted local artifacts only; the application does not offer arbitrary model uploads.

## Train or evaluate

In the browser, **Train model** → select `dataset/primary_size_matched_dataset.csv` → **Validate schema** → **Train & evaluate**. Training runs in a background job, with real fold-level progress and errors. Download metadata, fold results, seed means and package fold membership from **Model performance**.

From the project root:

```powershell
.\.venv\Scripts\python.exe scripts\inspect_dataset.py --dataset dataset\primary_size_matched_dataset.csv
.\.venv\Scripts\python.exe scripts\train_model.py --dataset dataset\primary_size_matched_dataset.csv
.\.venv\Scripts\python.exe scripts\evaluate_model.py --dataset dataset\primary_size_matched_dataset.csv --output evaluation
```

The CLI training command publishes the same artifacts as the browser. Restart a running backend after training through the CLI; browser training hot-loads its new generation automatically. Use a single backend worker and do not run CLI training concurrently with browser training. One browser training job is admitted at a time.

Training rejects mismatched row counts, class counts, package counts, mixed labels, absent features, duplicates, nonnumeric values and nonfinite values. It requires 615 rows (360 malicious, 255 benign), 180 packages (128 malicious, 52 clean), and the exact 60-feature allowlist. Other columns can be present but are excluded from predictors. Package is used only for grouping and label only as the target.

### Exact 60 → 240 transformation

`backend/app/ml/aggregation.py::aggregate_packages` is the **one shared function** called by training and prediction. It selects features in `schema.py::FEATURES` order, groups by package and concatenates:

```
[mean of all 60 features,
 maximum of all 60 features,
 median of all 60 features,
 sample standard deviation of all 60 features]
```

For each block, names are `feature__mean`, `feature__max`, `feature__median`, or `feature__std`. The output is 240 columns in block order, not interleaved statistics. Standard deviation uses **ddof=1** (the brief did not specify this convention); one-row standard deviation is zero. Metadata records the exact input and output order and ddof. No imputation, scaling, feature selection, ecosystem encoding, or identifier features are added.

### Exact ensemble and evaluation

RF: 300 estimators, sqrt features, balanced class weights, minimum leaf 1, current evaluation seed, all CPU cores. XGBoost: 250 estimators, learning rate .04, depth 3, minimum child weight 3, subsample .90, column sample .80, lambda 2, alpha .10, logloss, current seed, all CPU cores.

Each seed **7, 42, 77, 123, 2026** independently uses stratified 5-fold CV over the aggregated package profiles. Models are refit for each fold. Each package appears in only one held-out fold per seed. There are 25 evaluations with no threshold tuning or best-seed selection. Malicious is the positive class. All five metrics are reported for each fold, each seed mean, overall mean, sample fold standard deviation, minimum and maximum. The seed-42 confusion matrix combines its five out-of-fold predictions (180 packages).

The final RF and XGBoost are fitted on all 180 profiles at seed 42. `score = .5 * RF_probability + .5 * XGBoost_probability`; `score >= .50` produces **Malicious-Risk**, otherwise **Clean-Risk**.

The first completed run measured 90.78% accuracy, 94.45% precision, 92.63% recall, 93.39% F1 and 96.08% ROC-AUC. These are a record of the actual run, not constants used by the app. The UI always reads the active metadata. The requested approximate historical results were not forced or substituted; package sorting, library versions, and the explicit std convention are recorded for reproduction.

Artifacts:

```
models/package_risk_random_forest.joblib
models/package_risk_xgboost.joblib
models/package_risk_metadata.json
models/evaluation_results.csv
models/seed_summary.csv
models/fold_membership.json
```

Immutable copies are saved under `models/runs/<model_version>/`. `current.txt` is atomically replaced only after validation, preventing a serving process from mixing two model generations. The files in `models/` are convenient exports. Startup checks names, order, dimensions, model classes, fusion weights, threshold, ddof and artifact hashes. A mismatch blocks predictions while leaving the management pages available for retraining.

## Analyze genuinely new input

### Feature CSV

Use **Upload Feature Dataset** and choose `examples/new_package_features.csv`. It contains actual official-extractor output from the last three npm `is-number` releases fetched during development (5.0.0 → 6.0.0 → 7.0.0). `is-number` is not among the training packages. This is an example input, not a labeled malware finding. Do not treat its score as ground truth.

The CSV includes `package`, `previous_version`, `current_version` and all 60 numerical columns. Several packages are allowed in a single CSV; each gets its own profile and result. `examples/feature_template.csv` is a blank header-only template. No fake feature values are supplied as observations.

The complete matching JSON is in `examples/new_package_request.json`:

```powershell
curl.exe -X POST http://127.0.0.1:8011/api/predict/features -H "Content-Type: application/json" --data-binary "@examples/new_package_request.json"
curl.exe -X POST http://127.0.0.1:8011/api/predict/csv -F "file=@examples/new_package_features.csv"
```

Request shape (abbreviated here; the example file contains all 60 keys):

```text
{"package":"is-number","version_pairs":[
  {"previous_version":"5.0.0","current_version":"6.0.0","features":{all 60 exact numerical keys}},
  {"previous_version":"6.0.0","current_version":"7.0.0","features":{all 60 exact numerical keys}}
]}
```

JSON values must be finite numbers and the feature object must contain exactly the 60 keys. CSV values are parsed as numbers; extra CSV metadata is ignored. Version identifiers are read as strings. Both paths reach the same validation → aggregation → stored schema check → RF and XGBoost probabilities → 50/50 fusion → persisted package result sequence.

### Raw npm / PyPI

Use **Scan npm** or **Scan PyPI**, enter a name, fetch history, and choose the last 2, 3, 5 or all recent compatible releases. “All” is capped at 10, visibly stated in the UI. Alternatively select 2–10 adjacent compatible releases explicitly. Publication dates define ordering. PyPI uses non-yanked source distributions (`.tar.gz` or `.zip`), not wheels. Available compatible history can have gaps relative to full registry history; no missing release is fabricated.

Use **Analyze package** for ordered manual archive uploads. Enter one comma-separated version name per archive and use “Move earlier” to correct ordering. The system cannot independently verify manual archives’ claimed identities or dates.

CLI equivalents:

```powershell
.\.venv\Scripts\python.exe scripts\scan_package.py --registry npm --package is-number --count 3
.\.venv\Scripts\python.exe scripts\scan_package.py --registry pypi --package requests --count 2
.\.venv\Scripts\python.exe scripts\scan_package.py --features examples\new_package_features.csv
```

Registry scans run asynchronously through the API. `POST /api/scan/npm` or `/api/scan/pypi` accepts `{"package":"is-number","count":3}` (use a PyPI name for PyPI). The response is `{"job_id":"..."}`; poll `GET /api/jobs/<id>`. Completed jobs include result objects and scan IDs. Source inspection never installs, imports or executes submitted packages.

### Exact extractor provenance and compatibility

Official source: [Moatasem M. Draz’s repository](https://github.com/moatasem2005/Version-Context-and-Control-Construction-in-Machine-Learning-Detection-of-Malicious-Package-Updates), commit `e090c96aa6fbe5ecbc59ec83063ea3ce6ebf9754`.

The older `supply_chain_detector.py` and `dataset_repair_pipeline.py` use earlier representations. The corrected 60-feature implementation is **cell 13 of `notebooks/05_sample_hygiene.ipynb`**, confirmed by the repository README. Its functions are vendored unchanged in `backend/app/ml/vendor/official_corrected.py`. Only standard-library imports were added and the trailing notebook logging call removed. The upstream MIT license and source/dataset SHA-256 hashes are included in `vendor/`.

`base_feature_extractor.py` calls upstream `all_features` after bounded static archive reading. The adapter preserves source suffix selection, UTF-8 ignore decoding, first-component root removal, the tar-only strict 2 MB source filter, the 20,000-line cap, rounding, regex definitions and official deleted-file behavior. It does not “correct” or improve these research definitions. The archive wrapper adds rejection of unsafe or ambiguous archives instead of silently changing source content.

Tests compare safe archive maps and all 60 features with upstream behavior for both ecosystems and formats. A live `six` 1.16.0 → 1.17.0 check also reproduced **every one of the 60 values exactly** in the published CSV. Its feature record is `examples/extractor_compatibility_check.json`. Reproduce the online check with:

```powershell
.\.venv\Scripts\python.exe scripts\verify_live_extractor.py
```

If the extractor hash, returned schema, trained extractor identity, or finite-value checks fail, raw prediction is blocked with the requested compatibility message. Feature CSV mode remains available with a valid model.

### Limits and safe processing

Default limits: 25 MB compressed archive, 80 MB declared expanded total, 10,000 entries, 8 MB per file, at most 10 versions and a 60-second extraction worker timeout. Configure through environment variables in `.env.example`; for local runs export the variables before starting Python. The file is a template, not an automatically loaded environment file.

Absolute paths, traversal, Windows drive paths, backslash normalization, duplicate/colliding paths, links, device/special entries and encrypted ZIPs are rejected. Archive entries are decoded in memory, never written using archive paths. Only temporary numbered archive files are written for a fixed trusted worker command; its temporary directory is removed on success or failure. Registry URLs must be HTTPS on exact official allowlisted hosts; redirects are not followed. Responses are streamed with byte limits. Raw extraction runs in a killable subprocess; it never evaluates the scanned code.

This is a **local, single-user research application**. The training screen is not protected by a login. Servers and Docker ports bind to loopback by default. If exposing it to other users, add authenticated access, deployment-level quotas and a managed job queue before making it public. Keep artifact directories writable only by trusted operators.

## Pages and endpoints

Pages: Home, Train Model, Analyze Package, Feature CSV, npm, PyPI, Analysis Result, Version History, Model Performance, Dashboard, Scan History, About Research.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Backend and prediction readiness |
| GET | `/api/model/info` | Active metadata and extractor status |
| POST | `/api/train/validate` | Validate uploaded training CSV |
| POST | `/api/train` | Start evaluation and final fitting |
| GET | `/api/training/results` | All folds, seed means, summaries, matrix |
| POST | `/api/predict/features` | JSON feature prediction |
| POST | `/api/predict/csv` | CSV prediction, one result per package |
| POST | `/api/scan/npm` | Raw npm job |
| POST | `/api/scan/pypi` | Raw PyPI job |
| POST | `/api/scan/archive` | Multipart ordered archive job |
| GET | `/api/registry/{npm,pypi}/versions?package=...` | Compatible registry release history |
| GET | `/api/jobs/{id}` | Progress, completion or error |
| GET | `/api/scans` | Paginated scan history (`limit`, `offset`) |
| GET | `/api/scans/{id}` | Result and all version-pair feature evidence |
| GET | `/api/dashboard` | Actual persisted scan statistics |
| GET | `/api/features/schema` | Exact schema and aggregation order |
| GET | `/api/features/template` | Blank CSV header |
| GET | `/api/model/download/{name}` | Metadata/evaluation export |

## Source map

| File | Responsibility |
|---|---|
| `backend/app/ml/schema.py` | Exact 60 features, CSV and training validation |
| `backend/app/ml/aggregation.py` | **Shared training and inference aggregation** |
| `backend/app/ml/evaluation.py` | Exact estimator parameters, 25 folds, fusion |
| `backend/app/ml/training.py` | Final fitting, metadata and artifact publication |
| `backend/app/ml/model_manager.py` | Startup validation and trusted loading |
| `backend/app/ml/inference.py` | Ensemble prediction, evidence and result persistence |
| `backend/app/api/predict.py` | JSON request → version-pair DataFrame |
| `backend/app/ml/base_feature_extractor.py` | Official extractor compatibility adapter |
| `backend/app/ml/feature_extraction.py` | Registry/archive pair reconstruction and worker |
| `backend/app/security/safe_archive.py` | Safe in-memory archive reading |
| `backend/app/registry/` | Official metadata and bounded downloads |
| `backend/app/db/store.py` | SQLite schema, scan/training persistence and dashboard |
| `frontend/src/pages/` | All React pages |
| `tests/` | Backend regression and integration tests |
| `frontend/e2e/` | Browser workflows, desktop/mobile layout |

## Verification

The backend suite requires the included dataset and trained artifacts. If starting with empty `models/`, train first.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
cd frontend
npm.cmd run build
npx.cmd playwright install chromium
# With backend and frontend running:
npx.cmd playwright test
```

The mandatory integration test checks **all 180 packages**: training aggregation versus JSON web-request parsing and inference aggregation must be bit-for-bit identical. Other tests cover numeric validation, metadata exclusion, exact order and statistics, single-row std, parameters, loading, artifact tampering, threshold boundaries, API persistence, registry parsing, SSRF allowlists, archive traversal/links/limits and upstream extractor equivalence. Browser tests cover all pages, responsive overflow, CSV prediction, evidence/history, invalid inputs, training validation and live npm analysis.

The complete API training path was also verified with `python scripts/verify_training_api.py --url http://127.0.0.1:8011`. This intentionally performs a new full training run and verifies serving-model reload and a subsequent prediction. See `VERIFICATION.md` for the delivery check record.

## Docker

```powershell
docker compose up --build
```

Open **http://localhost:8080**, API docs **http://localhost:8000/docs**. SQLite and models persist in mounted `scans/` and `models/` directories. On Linux, ensure these directories are writable by container UID 1000. Train from the UI or `docker compose exec backend python /app/scripts/train_model.py --dataset /app/dataset/primary_size_matched_dataset.csv` (restart backend after CLI training).

Docker is configured but was not executed in the development environment because the Docker CLI was unavailable. The native Python and Node installations, real training, backend tests, frontend build, browser flows and both registries were exercised.

## Scientific interpretation

This application performs first-stage **package risk screening**. A result does not identify an exact malicious release, prove malware, guarantee safety, guarantee 91% accuracy for new inputs, establish generalization to future campaigns, or demonstrate ecosystem transfer. Score bands are display categories only: `<.30` low, `.30–<.50` moderate, `.50–<.75` elevated, `>=.75` high. Scores are not calibrated compromise probabilities.

Feature evidence reports observed pair values and global tree-importance ranks. The average of RF impurity importance and XGBoost gain importance is an association display, not a local explanation or a causal malware finding.

The [Scientific Reports paper](https://doi.org/10.1038/s41598-026-71750-5) reports corrected nested grouped F1 ≈ .792 and ROC-AUC ≈ .801 for individual version pairs. The proposed project evaluates aggregated package profiles. **These results represent different detection units and must not be interpreted as a direct numerical improvement under an identical protocol.** Repeated fold scores overlap across seeds; their standard deviation is descriptive, not an independent confidence interval.

Dataset and official extraction code: copyright © 2026 Moatasem M. Draz, MIT license reproduced in `backend/app/ml/vendor/LICENSE`.
