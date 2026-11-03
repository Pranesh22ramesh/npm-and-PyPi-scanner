# Malicious npm & PyPI Package Scanner

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg?style=flat&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5+-3178C6.svg?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3+-06B6D4.svg?style=flat&logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![Python](https://img.shields.io/badge/Python-3.13+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-1.6+-F7931E.svg?style=flat&logo=scikit-learn&logoColor=white)](https://scikit-learn.org)
[![XGBoost](https://img.shields.io/badge/XGBoost-2.1+-EB5424.svg?style=flat)](https://xgboost.readthedocs.io)

An end-to-end research workbench and security intelligence system implementing **Multi-Version Package Risk Aggregation with Heterogeneous Ensemble Learning for Malicious npm and PyPI Package Detection**.

The system extracts dynamic and static AST security features across package versions, aggregates version histories into statistical package profiles (mean, max, median, standard deviation), and detects malicious software with high precision using an ensemble of **Random Forest** and **XGBoost** models.

---

## 📑 Table of Contents

- [Overview & Architecture](#-overview--architecture)
- [Repository Structure](#-repository-structure)
- [Key Features](#-key-features)
- [Machine Learning Pipeline](#-machine-learning-pipeline)
  - [Feature Extraction (60 Features)](#feature-extraction-60-features)
  - [Statistical Aggregation (60 → 240 Dimensions)](#statistical-aggregation-60--240-dimensions)
  - [Heterogeneous Ensemble](#heterogeneous-ensemble)
  - [Validation Metrics](#validation-metrics)
- [Prerequisites](#-prerequisites)
- [Getting Started & Running](#-getting-started--running)
  - [Option A: Running Locally (PowerShell / Windows)](#option-a-running-locally-powershell--windows)
  - [Option B: Running Locally (Linux / macOS)](#option-b-running-locally-linux--macos)
  - [Option C: Docker Compose](#option-c-docker-compose)
- [CLI Tools & Scripts](#-cli-tools--scripts)
- [API Documentation](#-api-documentation)
- [Dataset Details](#-dataset-details)
- [Security Notice](#-security-notice)

---

## 🔍 Overview & Architecture

Modern open-source supply chains suffer from malicious package injection, typosquatting, dependency confusion, and account takeovers. Single-version analysis frequently misses stealthy version transitions or erratic releases.

This project implements:
1. **Multi-Version Tracking**: Ingests multiple versions of a package from registries (npm registry & PyPI) or uploaded source tarballs/zips.
2. **Safe Decompression & Sandbox Extraction**: Tarballs (`.tgz`, `.tar.gz`) and zip archives are safely analyzed with quota-limited extraction, path traversal protections, and zip-bomb mitigation.
3. **AST & Metadata Feature Extraction**: Derives 60 normalized metrics covering sensitive API calls, dynamic code execution (`eval`, `exec`), base64 entropy, network socket creation, obfuscation patterns, install scripts, and metadata anomalies.
4. **Statistical Profile Aggregation**: Consolidates version sequences into a 240-dimensional feature profile using `[mean, max, median, std]`.
5. **Heterogeneous Ensemble Classifier**: Combines Random Forest and XGBoost probabilities for calibrated, robust threat verdicts (`Clean-Risk` vs. `Malicious-Risk`).
6. **Full-Featured Modern Web UI**: Responsive React + Vite dashboard for live registry lookups, manual uploads, model performance auditing, fold-by-fold inspections, and scan logs.

---

## 📁 Repository Structure

```text
├── data/                                # Curated datasets for research & modeling
│   ├── features/                        # Extracted feature CSVs (v4 balanced, v6 clean, etc.)
│   │   ├── primary_size_matched_dataset.csv
│   │   ├── features_v6_clean.csv
│   │   ├── features_v6_controls.csv
│   │   └── ...
│   └── raw/                             # Raw consolidated metadata & registries
│       └── merged_dataset_usable.csv
│
├── new demo/
│   ├── package-risk-system/             # ⭐ Complete production-ready scanner system
│   │   ├── backend/                     # FastAPI REST API & ML orchestration
│   │   │   ├── app/
│   │   │   │   ├── api/                 # Endpoints (scan_npm, scan_pypi, uploads, train, etc.)
│   │   │   │   ├── db/                  # SQLite persistence & audit log
│   │   │   │   ├── ml/                  # Feature extractors, aggregation, model management
│   │   │   │   ├── registry/            # npm & PyPI live API clients
│   │   │   │   ├── schemas/             # Pydantic models for validation
│   │   │   │   └── security/            # Safe archive unpacking & sanitization
│   │   │   ├── requirements.txt         # Core dependencies
│   │   │   ├── requirements-lock.txt    # Pinned dependency lockfile
│   │   │   └── run.py                   # Backend entrypoint
│   │   │
│   │   ├── frontend/                    # Vite + React + TypeScript + Tailwind UI
│   │   │   ├── src/
│   │   │   │   ├── components/          # UI widgets, badges, navigation
│   │   │   │   ├── pages/               # Scanner, Batch, Training, Performance views
│   │   │   │   └── services/            # Axios API client bindings
│   │   │   ├── package.json
│   │   │   └── vite.config.ts
│   │   │
│   │   ├── dataset/                     # Training reference dataset
│   │   ├── examples/                    # Sample packages & feature JSON/CSVs for testing
│   │   ├── models/                      # Pre-trained joblib weights and fold metadata
│   │   │   ├── package_risk_random_forest.joblib
│   │   │   ├── package_risk_xgboost.joblib
│   │   │   └── package_risk_metadata.json
│   │   ├── scripts/                     # Standalone CLI tools (train, evaluate, scan)
│   │   ├── tests/                       # Pytest test suite
│   │   ├── docker-compose.yml           # Container configuration
│   │   └── start-local.ps1              # One-click Windows starter
│   │
│   └── research-reference/              # Research notes, baseline references, and docs
│
└── .gitignore                           # Git ignore rules
```

---

## ✨ Key Features

- **Live Registry Scans**: Provide any npm (`express`, `lodash`, etc.) or PyPI (`requests`, `flask`, etc.) package name. The system queries registry metadata, fetches version releases, extracts features across versions, and renders an instant risk report.
- **Archive Uploads**: Upload package archives (`.tgz`, `.tar.gz`, `.zip`) directly for air-gapped or pre-release scanning.
- **Model Explainability & Transparency**: Displays exact feature contributions, dynamic execution metrics, network indicators, entropy scores, and per-version progressions.
- **In-Browser Retraining & Evaluation**: Upload a custom CSV dataset, validate schema conformity, and launch background training with real-time fold progression and metric logs.
- **Durable Local Storage**: Audit trail of every scan saved in SQLite (`scans/research.sqlite3`) with reproducible feature signatures.

---

## 🧠 Machine Learning Pipeline

### Feature Extraction (60 Features)
The system uses the verified feature extractor targeting key indicators of malicious code:
- **Code Execution & Spawning**: Occurrences of `eval()`, `exec()`, `Function()`, `child_process.exec`, `subprocess.Popen`, `os.system`.
- **Network & Exfiltration**: Sockets, HTTP/HTTPS client invocations, DNS lookups, raw IP address patterns, exfiltration endpoints.
- **Obfuscation & Packing**: String entropy, hex literals, character code sequences (`String.fromCharCode`), base64 decoding blocks.
- **Install & Lifecycle Hooks**: `preinstall`, `postinstall`, `setup.py` custom execution commands.
- **Filesystem & Environment Manipulation**: Access to sensitive directories (`/etc/passwd`, Windows registry, `process.env`, `os.environ`).

### Statistical Aggregation (60 → 240 Dimensions)
To capture how a package evolves over time and isolate version spikes, features are grouped across all releases of a package and aggregated via `backend/app/ml/aggregation.py`:

$$\text{Profile} = [\text{Mean}_{1..60},\; \text{Max}_{1..60},\; \text{Median}_{1..60},\; \text{Std}_{1..60}]$$

- Sample standard deviation uses Bessel's correction ($ddof=1$); single-version packages have standard deviation 0.

### Heterogeneous Ensemble
- **Random Forest**: 300 estimators, balanced class weights, `sqrt` feature max, min samples leaf 1.
- **XGBoost**: 250 estimators, learning rate 0.04, max depth 3, min child weight 3, subsample 0.90, colsample 0.80, L2 lambda 2.0, L1 alpha 0.10.
- **Ensemble Decision**:
  $$\text{Risk Score} = 0.5 \times P_{\text{RF}}(\text{Malicious}) + 0.5 \times P_{\text{XGBoost}}(\text{Malicious})$$
  - $\text{Risk Score} \ge 0.50 \implies \mathbf{Malicious\text{-}Risk}$
  - $\text{Risk Score} < 0.50 \implies \mathbf{Clean\text{-}Risk}$

### Validation Metrics
Evaluated with 5 independent stratified 5-fold cross-validations (25 total fold evaluations):
- **Accuracy**: ~90.8%
- **Precision**: ~94.5%
- **Recall**: ~92.6%
- **F1-Score**: ~93.4%
- **ROC-AUC**: ~96.1%

---

## 🛠 Prerequisites

- **Python**: 3.10 - 3.13 (3.13 recommended)
- **Node.js**: v18+ (Node 20 or 24 recommended)
- **npm**: v9+
- **Git**

---

## 🚀 Getting Started & Running

Navigate to the scanner system directory:
```bash
cd "new demo/package-risk-system"
```

### Option A: Running Locally (PowerShell / Windows)

1. **Setup Python Virtual Environment & Dependencies**:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r backend\requirements-lock.txt
   ```

2. **Install Frontend Dependencies**:
   ```powershell
   cd frontend
   npm ci
   cd ..
   ```

3. **Start the Backend**:
   ```powershell
   # In Terminal 1:
   .\start-local.ps1
   # (Or run directly: cd backend && ..\.venv\Scripts\python.exe run.py --port 8011)
   ```

4. **Start the Frontend**:
   ```powershell
   # In Terminal 2:
   cd frontend
   npm run dev
   ```

5. **Access the Application**:
   - Web Dashboard: **http://127.0.0.1:5173**
   - Interactive Swagger API Docs: **http://127.0.0.1:8011/docs**

> **Note on Ports**: The backend runs on port `8011` by default when using `start-local.ps1` to prevent collisions. The frontend Vite server is configured via `frontend/.env.local` to proxy requests to `http://127.0.0.1:8011`.

---

### Option B: Running Locally (Linux / macOS)

1. **Setup Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r backend/requirements-lock.txt
   cd frontend && npm ci && cd ..
   ```

2. **Launch Services**:
   ```bash
   # Terminal 1: Start Backend
   cd backend
   ../.venv/bin/python run.py --port 8011

   # Terminal 2: Start Frontend
   cd frontend
   npm run dev
   ```

---

### Option C: Docker Compose

You can spin up both the FastAPI backend and Nginx-served frontend using Docker:

```bash
docker compose up --build
```
The application will be accessible at **http://localhost:8000**.

---

## 💻 CLI Tools & Scripts

Standalone scripts in `new demo/package-risk-system/scripts/` allow full automation via terminal:

- **Scan a Package by Name**:
  ```powershell
  .\.venv\Scripts\python.exe scripts\scan_package.py --npm <package-name>
  .\.venv\Scripts\python.exe scripts\scan_package.py --pypi <package-name>
  ```

- **Inspect Dataset Integrity**:
  ```powershell
  .\.venv\Scripts\python.exe scripts\inspect_dataset.py --dataset dataset\primary_size_matched_dataset.csv
  ```

- **Retrain the Ensemble Model**:
  ```powershell
  .\.venv\Scripts\python.exe scripts\train_model.py --dataset dataset\primary_size_matched_dataset.csv
  ```

- **Run Cross-Validation Evaluation**:
  ```powershell
  .\.venv\Scripts\python.exe scripts\evaluate_model.py --dataset dataset\primary_size_matched_dataset.csv --output evaluation
  ```

- **Run Pytest Suite**:
  ```powershell
  .\.venv\Scripts\pytest tests/
  ```

---

## 📡 API Documentation

FastAPI provides an automatic, interactive OpenAPI documentation interface at:
- Swagger UI: `http://127.0.0.1:8011/docs`
- ReDoc: `http://127.0.0.1:8011/redoc`

### Primary Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/scan/npm` | Scan a package from the official npm registry |
| `POST` | `/api/scan/pypi` | Scan a package from PyPI |
| `POST` | `/api/scan/upload` | Upload `.tgz`, `.tar.gz`, or `.zip` archives to scan |
| `POST` | `/api/predict` | Predict risk score directly from pre-extracted feature vectors |
| `GET` | `/api/model/info` | Inspect active model weights, generation ID, and CV scores |
| `POST` | `/api/train` | Trigger background model training on a validated dataset |
| `GET` | `/api/history` | Query database scan history and past verdicts |

---

## 📊 Dataset Details

The dataset (`data/features/primary_size_matched_dataset.csv` and `new demo/package-risk-system/dataset/primary_size_matched_dataset.csv`) contains:
- **Total Version Observations**: 615 rows (360 confirmed malicious, 255 benign)
- **Distinct Packages**: 180 packages (128 malicious, 52 clean)
- **Features**: Exact 60-feature allowlist covering syntactic and static behaviors.
- **Controls**: Matched size distributions to prevent classification bias based purely on code length.

---

## 🛡️ Security Notice

This repository contains static detection rules, datasets with historical malicious package signatures, and extractors for defensive research. 
Archive extraction uses strict protections against path traversal (`..` escapes), symlink attacks, and decompression bombs. Never execute unknown third-party package source code outside an isolated container or virtual machine.
