"""
=============================================================================
 DATASET REPAIR PIPELINE  -  single-file, Drive-persisted, fully resumable
 Scientific Reports submission 35109da0  |  reviewer revision round
=============================================================================

WHAT IT DOES
  Stage 1  matched negatives   (v[i-2], v[i-1]) from the SAME package
  Stage 2  PyPI expansion      extra confirmed incidents from OpenSSF
  Stage 3  rebuild dataset     features_v2.csv
  Stage 4  evaluation          ecosystem baseline / predecessor value / transfer

HOW TO RUN ON COLAB
  1. put features.csv and merged_dataset_usable.csv in  MyDrive/paper_revision/
  2. upload this file, then in a cell:      %run dataset_repair_pipeline.py
  3. if the runtime dies, run the same line again - it resumes from Drive.

EVERYTHING is written to Drive as it goes, so a disconnect costs at most 10 rows.
=============================================================================
"""

import os, io, re, ast, sys, math, json, time, glob, shutil, tarfile, zipfile
import warnings, traceback, subprocess
from collections import Counter

warnings.filterwarnings("ignore", category=SyntaxWarning)   # noisy 3rd-party package code
warnings.filterwarnings("ignore", category=DeprecationWarning)

import requests
import numpy as np
import pandas as pd

SEED = 42

# ---------------------------------------------------------------------------
# 0. WORKING DIRECTORY  (Drive when available, local otherwise)
# ---------------------------------------------------------------------------
DRIVE_SUBDIR = "paper_revision"

def setup_workdir():
    try:
        from google.colab import drive
        if not os.path.ismount("/content/drive"):
            drive.mount("/content/drive")
        wd = f"/content/drive/MyDrive/{DRIVE_SUBDIR}"
        os.makedirs(wd, exist_ok=True)
        print(f"[workdir] Drive: {wd}")
        return wd
    except Exception as e:
        wd = os.path.abspath("./paper_revision")
        os.makedirs(wd, exist_ok=True)
        print(f"[workdir] Drive unavailable ({type(e).__name__}); using local: {wd}")
        return wd

WORK = setup_workdir()
P = lambda name: os.path.join(WORK, name)

CKPT_MATCHED = P("matched_negatives.csv")
CKPT_PYPI    = P("pypi_expansion.csv")
OUT_FEATURES = P("features_v2.csv")
OUT_RESULTS  = P("revision_results_v2.json")
LOG_PATH     = P("pipeline_log.txt")

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a") as fh: fh.write(line + "\n")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# 1. INPUT FILES
# ---------------------------------------------------------------------------
NEEDED = ["features.csv", "merged_dataset_usable.csv"]

def locate_inputs():
    for f in NEEDED:
        if os.path.exists(P(f)):
            continue
        if os.path.exists(f):                       # uploaded to session root
            shutil.copy(f, P(f)); log(f"copied {f} -> Drive"); continue
        cand = [g for g in glob.glob("*.csv") if g.startswith(f.replace(".csv", ""))]
        if cand:                                    # 'features (1).csv'
            shutil.copy(cand[0], P(f)); log(f"recovered {f} from {cand[0]}"); continue
        try:
            from google.colab import files
            log(f"missing {f} - opening upload dialog")
            files.upload()
            if os.path.exists(f): shutil.copy(f, P(f))
        except Exception:
            pass
    still = [f for f in NEEDED if not os.path.exists(P(f))]
    if still:
        raise SystemExit(f"Cannot continue - missing {still}. "
                         f"Place them in {WORK} and re-run.")

locate_inputs()
feat_old = pd.read_csv(P("features.csv"),
                      dtype={"package": str, "ecosystem": str})
usable   = pd.read_csv(P("merged_dataset_usable.csv"),
                      dtype={"package": str, "ecosystem": str,
                             "version_before": str, "version_after": str})
log(f"features.csv {feat_old.shape} | merged_dataset_usable.csv {usable.shape}")

# ---------------------------------------------------------------------------
# 2. REGISTRY ACCESS  (retry + backoff)
# ---------------------------------------------------------------------------
NPM_URL  = "https://registry.npmjs.org/{p}"
PYPI_URL = "https://pypi.org/pypi/{p}/json"
HEADERS  = {"User-Agent": "supply-chain-research/1.0 (academic)"}
DELAY    = 0.4
RETRIES  = 3

def _request(url, want_json, timeout):
    for attempt in range(RETRIES):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            time.sleep(DELAY)
            if r.status_code == 200:
                return r.json() if want_json else r.content
            if r.status_code in (429, 500, 502, 503):        # transient
                time.sleep(2 ** attempt)
                continue
            return None                                       # 404 etc - real miss
        except requests.RequestException:
            time.sleep(2 ** attempt)
        except ValueError:                                    # bad JSON
            return None
    return None

def fetch_npm_metadata(p):  return _request(NPM_URL.format(p=p),  True, 15)
def fetch_pypi_metadata(p): return _request(PYPI_URL.format(p=p), True, 15)
def download_bytes(url):    return _request(url, False, 30) if url else None

def npm_versions(m):
    t  = m.get("time", {}) or {}
    vs = [v for v in (m.get("versions", {}) or {})
          if v not in ("created", "modified") and v != "0.0.1-security"]
    pr = [(v, t.get(v)) for v in vs if t.get(v)]
    pr.sort(key=lambda x: x[1]); return pr

def pypi_versions(m):
    pr = []
    for v, files in (m.get("releases", {}) or {}).items():
        if not files: continue
        ut = files[0].get("upload_time_iso_8601") or files[0].get("upload_time")
        if ut: pr.append((v, ut))
    pr.sort(key=lambda x: x[1]); return pr

def fetch_tarball_url(package, ecosystem, version):
    if ecosystem == "npm":
        m = fetch_npm_metadata(package)
        try:    return m["versions"][version]["dist"]["tarball"]
        except (KeyError, TypeError): return None
    m = fetch_pypi_metadata(package)
    try:
        files = m["releases"].get(version, [])
        if not files: return None
        sd = [f for f in files if f["url"].endswith((".tar.gz", ".zip"))]
        return (sd[0] if sd else files[0])["url"]
    except (KeyError, TypeError): return None

# ---------------------------------------------------------------------------
# 3. FEATURE EXTRACTION
#    identical regexes to supply_chain_detector.py so new rows stay comparable,
#    plus: per-file AST parsing (the original called Python's ast.parse on a
#    concatenated JS/py/cfg/toml blob, which failed 97.4% of the time) and
#    size-normalised counts.
# ---------------------------------------------------------------------------
SUSPICIOUS = {
  "net_http":        re.compile(r"\b(https?://|requests\.(get|post)|urllib|fetch\(|XMLHttpRequest|http\.request|axios)", re.I),
  "subprocess_exec": re.compile(r"\b(subprocess|child_process|os\.system|exec\(|eval\(|spawn\(|popen)", re.I),
  "env_cred_access": re.compile(r"(process\.env|os\.environ|getenv|\.aws/credentials|id_rsa|\.npmrc|\.pypirc|SSH_|API_KEY|SECRET)", re.I),
  "filesystem":      re.compile(r"\b(fs\.(write|read|unlink)|open\([^)]*['\"]w|shutil|os\.remove|writeFile)", re.I),
  "encoded_blob":    re.compile(r"(base64|atob|btoa|fromCharCode|eval\(.*decode|exec\(.*decode)", re.I),
  "install_hook":    re.compile(r"(preinstall|postinstall|setup\.py|cmdclass|__import__)", re.I),
  "obfuscation":     re.compile(r"(_0x[0-9a-f]{4,}|[A-Za-z0-9+/]{120,})", re.I),
}

try:
    import esprima
    HAVE_ESPRIMA = True
except ImportError:
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "esprima"], check=False)
        import esprima
        HAVE_ESPRIMA = True
    except Exception:
        HAVE_ESPRIMA = False
        log("WARNING: esprima unavailable - JS AST counts fall back to a token proxy")

MAX_PARSE_CHARS = 400_000        # guard against pathological minified bundles

def entropy(s):
    if not s: return 0.0
    n = len(s)
    return -sum((c/n) * math.log2(c/n) for c in Counter(s).values())

def extract_files(archive, ecosystem):
    """[(filename, text)] - per-file, so the AST can be parsed correctly."""
    if not archive: return []
    exts = (".js", ".ts", ".json", ".mjs", ".cjs") if ecosystem == "npm" \
           else (".py", ".cfg", ".toml", ".txt")
    out = []
    try:
        try:
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as t:
                for mem in t.getmembers():
                    if mem.isfile() and mem.name.endswith(exts):
                        fo = t.extractfile(mem)
                        if fo: out.append((mem.name, fo.read().decode("utf-8", "ignore")))
        except tarfile.ReadError:
            with zipfile.ZipFile(io.BytesIO(archive)) as z:
                for nm in z.namelist():
                    if nm.endswith(exts):
                        out.append((nm, z.read(nm).decode("utf-8", "ignore")))
    except Exception:
        return []
    return out

def _count_es(node):
    if isinstance(node, dict):
        return 1 + sum(_count_es(v) for k, v in node.items() if k != "type")
    if isinstance(node, list):
        return sum(_count_es(v) for v in node)
    return 0

def ast_node_count(files, ecosystem):
    """Returns (nodes, parsed_ok, files_seen) so parse coverage is reportable."""
    total, ok, seen = 0, 0, 0
    for name, txt in files:
        if ecosystem == "npm":
            if not name.endswith((".js", ".mjs", ".cjs", ".ts")): continue
            seen += 1
            if not HAVE_ESPRIMA:
                total += len(re.findall(r"[A-Za-z_$][\w$]*|\d+|\S", txt[:MAX_PARSE_CHARS]))
                ok += 1
                continue
            body = txt[:MAX_PARSE_CHARS]
            parsed = False
            for parse in (esprima.parseScript, esprima.parseModule):
                for kw in ({"tolerant": True}, {}):        # kwarg support varies by version
                    try:
                        total += _count_es(parse(body, **kw).toDict()); ok += 1
                        parsed = True; break
                    except TypeError:
                        continue
                    except Exception:
                        break
                if parsed: break
        else:
            if not name.endswith(".py"): continue
            seen += 1
            try:
                total += sum(1 for _ in ast.walk(ast.parse(txt[:MAX_PARSE_CHARS]))); ok += 1
            except Exception:
                pass
    return total, ok, seen

def pcounts(code): return {k: len(rx.findall(code)) for k, rx in SUSPICIOUS.items()}

MIN_CODE_CHARS = 30

def features_for_pair(package, ecosystem, vbefore, vafter):
    fa = extract_files(download_bytes(fetch_tarball_url(package, ecosystem, vafter)), ecosystem)
    if sum(len(t) for _, t in fa) < MIN_CODE_CHARS: return None, "after_download_failed"
    fb = extract_files(download_bytes(fetch_tarball_url(package, ecosystem, vbefore)), ecosystem)
    if sum(len(t) for _, t in fb) < MIN_CODE_CHARS: return None, "before_download_failed"

    cb = "\n".join(t for _, t in fb)
    ca = "\n".join(t for _, t in fa)
    bc, ac = pcounts(cb), pcounts(ca)

    f = {}
    for k in SUSPICIOUS:
        f[f"delta_{k}"] = ac[k] - bc[k]
        f[f"after_{k}"] = ac[k]
    f["delta_loc"]  = ca.count("\n") - cb.count("\n")
    f["delta_char"] = len(ca) - len(cb)
    f["entropy_before"] = round(entropy(cb[:50000]), 3)
    f["entropy_after"]  = round(entropy(ca[:50000]), 3)
    f["delta_entropy"]  = round(f["entropy_after"] - f["entropy_before"], 3)
    lt = lambda c: max((len(t) for t in re.findall(r"\S+", c)), default=0)
    f["delta_longest_token"] = lt(ca) - lt(cb)

    n_a, ok_a, seen_a = ast_node_count(fa, ecosystem)
    n_b, ok_b, seen_b = ast_node_count(fb, ecosystem)
    f["ast_nodes_after"]  = n_a
    f["ast_nodes_before"] = n_b
    f["delta_ast_nodes"]  = n_a - n_b
    f["ast_parse_rate"]   = round(ok_a / seen_a, 3) if seen_a else 0.0

    kb = max(len(ca) / 1024.0, 1.0)
    f["size_kb_after"] = round(len(ca) / 1024.0, 2)
    for k in SUSPICIOUS:
        f[f"norm_after_{k}"] = round(f[f"after_{k}"] / kb, 4)
    return f, "ok"

# stable column order -> safe CSV appends across batches
META_COLS = ["package", "ecosystem", "label", "version_before", "version_after",
             "version_after_date", "origin"]
FEAT_COLS = ([f"delta_{k}" for k in SUSPICIOUS] + [f"after_{k}" for k in SUSPICIOUS] +
             ["delta_loc", "delta_char", "entropy_before", "entropy_after", "delta_entropy",
              "delta_longest_token", "ast_nodes_after", "ast_nodes_before",
              "delta_ast_nodes", "ast_parse_rate", "size_kb_after"] +
             [f"norm_after_{k}" for k in SUSPICIOUS])
ALL_COLS = FEAT_COLS + META_COLS

def flush(rows, path):
    """Append rows with a fixed column order; never lose data to a column mismatch."""
    if not rows: return
    df = pd.DataFrame(rows).reindex(columns=ALL_COLS)
    df.to_csv(path, mode="a", header=not os.path.exists(path), index=False)

# Version identifiers such as "1.9" or "2.0" are coerced to float64 by pandas when a
# column happens to hold only numeric-looking values. The resume key would then be
# (pkg, 1.9) instead of (pkg, "1.9"), never match the registry string, and the stage
# would silently redo finished work and append duplicates. Force these to str.
KEY_STR = {"package": str, "ecosystem": str, "version_before": str, "version_after": str}

def load_ckpt(path):
    if not os.path.exists(path): return pd.DataFrame(columns=ALL_COLS)
    try:
        return pd.read_csv(path, dtype=KEY_STR)
    except Exception as e:
        log(f"WARNING: {os.path.basename(path)} unreadable ({e}) - quarantining")
        shutil.move(path, path + ".corrupt")
        return pd.DataFrame(columns=ALL_COLS)

# ---------------------------------------------------------------------------
# STAGE 1 - MATCHED NEGATIVES
# ---------------------------------------------------------------------------
def stage1_matched_negatives():
    log("=" * 70); log("STAGE 1 - matched negatives")

    mal = (feat_old[feat_old.label == 1][["package", "ecosystem"]]
           .drop_duplicates()
           .merge(usable[["package", "ecosystem", "version_before"]].drop_duplicates(),
                  on=["package", "ecosystem"], how="left")
           .dropna(subset=["version_before"])
           .drop_duplicates(subset=["package", "ecosystem", "version_before"]))
    log(f"malicious pairs to walk back: {len(mal)} across {mal.package.nunique()} packages")

    prev = load_ckpt(CKPT_MATCHED)
    done = {(str(a), str(b), str(c)) for a, b, c in
            zip(prev.package, prev.ecosystem, prev.version_after)} if len(prev) else set()
    if done: log(f"resuming - {len(done)} already processed")

    rows, stats = [], Counter()
    try:
        for n, r in enumerate(mal.itertuples(index=False), 1):
            # NB: v_curr == r.version_before by construction, so this key matches the ckpt
            if (str(r.package), str(r.ecosystem), str(r.version_before)) in done:
                stats["skipped_done"] += 1; continue
            try:
                meta = fetch_npm_metadata(r.package) if r.ecosystem == "npm" \
                       else fetch_pypi_metadata(r.package)
                if not meta: stats["no_metadata"] += 1; continue
                hist = npm_versions(meta) if r.ecosystem == "npm" else pypi_versions(meta)
                vers = [v for v, _ in hist]
                if r.version_before not in vers: stats["before_not_in_history"] += 1; continue
                i = vers.index(r.version_before)
                if i < 1: stats["no_grandparent"] += 1; continue

                v_prev, v_curr = vers[i - 1], vers[i]
                f, status = features_for_pair(r.package, r.ecosystem, v_prev, v_curr)
                if f is None: stats[status] += 1; continue

                f.update(package=r.package, ecosystem=r.ecosystem, label=0,
                         version_before=v_prev, version_after=v_curr,
                         version_after_date=dict(hist)[v_curr], origin="matched_negative")
                rows.append(f); stats["ok"] += 1
            except Exception as e:
                stats[f"error:{type(e).__name__}"] += 1

            if n % 10 == 0:
                flush(rows, CKPT_MATCHED); rows = []
                log(f"  {n}/{len(mal)}  ok={stats['ok']}  {dict(stats)}")
    except KeyboardInterrupt:
        log("interrupted - saving partial progress")
    finally:
        flush(rows, CKPT_MATCHED)

    matched = load_ckpt(CKPT_MATCHED)
    if len(matched):
        matched = matched.drop_duplicates(subset=["package", "ecosystem", "version_after"])
        matched = matched[matched.label == 0]
    log(f"matched negatives built: {len(matched)}  (vs {int((feat_old.label==1).sum())} malicious rows)")
    if len(matched): log(f"  by ecosystem: {dict(matched.ecosystem.value_counts())}")
    log(f"outcome breakdown: {dict(stats)}")
    return matched

# ---------------------------------------------------------------------------
# STAGE 2 - PyPI EXPANSION
# ---------------------------------------------------------------------------
OSSF_DIR = P("malicious-packages")
MAX_NEW  = 800

def get_ossf_repo():
    if os.path.isdir(os.path.join(OSSF_DIR, "osv")):
        log("OpenSSF repo already present"); return True
    log("cloning ossf/malicious-packages ...")
    try:
        r = subprocess.run(["git", "clone", "--depth", "1", "-q",
                            "https://github.com/ossf/malicious-packages.git", OSSF_DIR],
                           capture_output=True, text=True, timeout=900)
        err = (r.stderr or "").strip()[:120]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
        err = f"{type(e).__name__}"                        # git not installed / hung
    if os.path.isdir(os.path.join(OSSF_DIR, "osv")): return True
    log(f"git clone failed ({err}) - trying zip download")
    try:
        data = _request("https://github.com/ossf/malicious-packages/archive/refs/heads/main.zip",
                        False, 600)
        if not data: return False
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(WORK)
        src = P("malicious-packages-main")
        if os.path.isdir(src):
            if os.path.isdir(OSSF_DIR): shutil.rmtree(OSSF_DIR)
            shutil.move(src, OSSF_DIR)
        return os.path.isdir(os.path.join(OSSF_DIR, "osv"))
    except Exception as e:
        log(f"zip fallback failed: {e}"); return False

def stage2_pypi_expansion():
    log("=" * 70); log("STAGE 2 - PyPI expansion")
    if not get_ossf_repo():
        log("SKIPPING stage 2 - could not obtain the OpenSSF advisory repository")
        return pd.DataFrame(columns=ALL_COLS)

    paths = glob.glob(os.path.join(OSSF_DIR, "osv", "malicious", "pypi", "**", "*.json"),
                      recursive=True)
    log(f"PyPI advisory files found: {len(paths)}")
    if not paths:
        log("SKIPPING stage 2 - no advisories matched the expected layout")
        return pd.DataFrame(columns=ALL_COLS)

    adv = []
    for p in paths:
        try:
            d = json.load(open(p))
        except Exception:
            continue
        for a in d.get("affected", []) or []:
            nm = (a.get("package", {}) or {}).get("name")
            if nm:
                adv.append({"package": nm, "versions": a.get("versions") or []})
    adv = pd.DataFrame(adv)
    if adv.empty:
        log("SKIPPING stage 2 - no package names parsed"); return pd.DataFrame(columns=ALL_COLS)
    adv = adv.drop_duplicates(subset=["package"])

    known    = set(feat_old[feat_old.ecosystem == "pypi"].package)
    new_pkgs = adv[~adv.package.isin(known)].head(MAX_NEW)
    log(f"already in dataset: {len(known)} | NEW candidates: {len(new_pkgs)}")

    prev = load_ckpt(CKPT_PYPI)
    done = {str(p) for p in prev.package} if len(prev) else set()
    if done: log(f"resuming - {len(done)} already processed")

    rows, stats = [], Counter()
    try:
        for n, r in enumerate(new_pkgs.itertuples(index=False), 1):
            if str(r.package) in done: stats["skipped_done"] += 1; continue
            try:
                meta = fetch_pypi_metadata(r.package)
                if not meta: stats["removed_from_registry"] += 1; continue
                hist = pypi_versions(meta)
                vers = [v for v, _ in hist]
                flagged = [v for v in (r.versions or []) if v in vers]
                if not flagged: stats["flagged_version_gone"] += 1; continue

                v_mal = flagged[0]
                i = vers.index(v_mal)
                if i < 1:
                    # first release already malicious -> NOT an update compromise.
                    # This count is exactly what Reviewer 1 comment 2 asks to document.
                    stats["first_release_malware_excluded"] += 1; continue

                f, status = features_for_pair(r.package, "pypi", vers[i - 1], v_mal)
                if f is None: stats[status] += 1; continue

                f.update(package=r.package, ecosystem="pypi", label=1,
                         version_before=vers[i - 1], version_after=v_mal,
                         version_after_date=dict(hist)[v_mal], origin="pypi_expansion")
                rows.append(f); stats["ok"] += 1
            except Exception as e:
                stats[f"error:{type(e).__name__}"] += 1

            if n % 10 == 0:
                flush(rows, CKPT_PYPI); rows = []
                log(f"  {n}/{len(new_pkgs)}  ok={stats['ok']}  {dict(stats)}")
    except KeyboardInterrupt:
        log("interrupted - saving partial progress")
    finally:
        flush(rows, CKPT_PYPI)

    pypi_new = load_ckpt(CKPT_PYPI)
    if len(pypi_new):
        pypi_new = pypi_new.drop_duplicates(subset=["package", "version_after"])
        pypi_new = pypi_new[pypi_new.label == 1]
    log(f"new malicious PyPI pairs: {len(pypi_new)}")
    log(f"outcome breakdown: {dict(stats)}")
    log(f">>> first-release malware excluded: {stats.get('first_release_malware_excluded', 0)}")
    return pypi_new

# ---------------------------------------------------------------------------
# STAGE 3 - REBUILD
# ---------------------------------------------------------------------------
def stage3_rebuild(matched, pypi_new):
    log("=" * 70); log("STAGE 3 - rebuild dataset")
    base = feat_old.copy(); base["origin"] = "original"
    parts = [base] + [d for d in (matched, pypi_new) if d is not None and len(d)]
    new = pd.concat(parts, ignore_index=True, sort=False)

    log("BEFORE:\n" + str(base.groupby(["ecosystem", "label"]).size()))
    log("AFTER:\n"  + str(new.groupby(["ecosystem", "label"]).size()))
    for eco in ["npm", "pypi"]:
        b = base[base.ecosystem == eco]; a = new[new.ecosystem == eco]
        if len(a):
            log(f"P(malicious|{eco}): {b.label.mean():.3f} -> {a.label.mean():.3f}")

    if "ast_parse_rate" in new.columns and new.ast_parse_rate.notna().any():
        cov = new[new.ast_parse_rate.notna()].groupby("ecosystem").ast_parse_rate.mean().round(3)
        log(f"AST parse coverage on NEW rows (old sentinel rate was 0.974 failure):\n{cov}")

    new.to_csv(OUT_FEATURES, index=False)
    log(f"saved {OUT_FEATURES}  {new.shape}")
    return new

# ---------------------------------------------------------------------------
# STAGE 4 - EVALUATION
# ---------------------------------------------------------------------------
def stage4_evaluate(df):
    log("=" * 70); log("STAGE 4 - evaluation")
    from sklearn.model_selection import StratifiedGroupKFold, cross_val_predict
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import (f1_score, precision_score, recall_score, confusion_matrix,
                                 average_precision_score, roc_auc_score)

    R = {}
    df = df.copy()
    df["eco_npm"] = (df.ecosystem == "npm").astype(int)

    CAND = [c for c in df.columns if c.startswith("after_")] + ["entropy_after"]
    PRED = [c for c in df.columns if c.startswith("delta_")] + ["entropy_before"]
    CAND = [c for c in CAND if c in df.columns and df[c].notna().all()]
    PRED = [c for c in PRED if c in df.columns and df[c].notna().all()]
    # size-normalised counts exist only on rows built by this script, so they can only be
    # evaluated on that subset - reported separately as the size-proxy control the
    # reviewers asked for, never mixed into the headline model.
    NORM = [c for c in df.columns if c.startswith("norm_after_")]
    log(f"candidate-only features: {len(CAND)} | predecessor features: {len(PRED)} "
        f"| normalised (subset only): {len(NORM)}")
    if not CAND or not PRED:
        log("ERROR: not enough complete feature columns"); return R

    y, groups = df.label.values, df.package.values
    cv  = StratifiedGroupKFold(5, shuffle=True, random_state=SEED)
    clf = lambda: HistGradientBoostingClassifier(max_iter=300, random_state=SEED)

    def M(yy, pred, proba=None):
        tn, fp, fn, tp = confusion_matrix(yy, pred, labels=[0, 1]).ravel()
        o = dict(f1=f1_score(yy, pred, zero_division=0),
                 precision=precision_score(yy, pred, zero_division=0),
                 recall=recall_score(yy, pred, zero_division=0),
                 fpr=fp/(fp+tn) if fp+tn else 0.0,
                 tn=int(tn), fp=int(fp), fn=int(fn), tp=int(tp))
        if proba is not None and len(set(yy)) > 1:
            o["pr_auc"]  = average_precision_score(yy, proba)
            o["roc_auc"] = roc_auc_score(yy, proba)
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in o.items()}

    def run(X, name, store):
        pr = cross_val_predict(clf(), X, y, cv=cv, groups=groups, method="predict_proba")[:, 1]
        m = M(y, (pr >= .5).astype(int), pr)
        log(f"  {name:34s} F1={m['f1']:.3f} Rec={m['recall']:.3f} "
            f"Prec={m['precision']:.3f} FPR={m['fpr']:.3f} PR-AUC={m.get('pr_auc', 0):.3f}")
        R.setdefault(store, {})[name] = m
        return m

    # Q1 - does the trivial ecosystem baseline still beat the model?
    log("Q1 - ecosystem confound")
    m_eco = M(y, df.eco_npm.values)
    log(f"  {'ECOSYSTEM-ONLY baseline':34s} F1={m_eco['f1']:.3f} "
        f"Prec={m_eco['precision']:.3f} FPR={m_eco['fpr']:.3f}   (notebook 1: 0.718, it WON)")
    m_full = run(df[CAND + PRED], "full model (no eco flag)", "Q1")
    R["Q1"]["ecosystem_only_baseline"] = m_eco
    log(f"  >>> model - baseline = {m_full['f1'] - m_eco['f1']:+.4f} F1")

    # Q2 - is the predecessor still worth a second download?
    log("Q2 - value of version context")
    rng = np.random.RandomState(SEED)
    X_full = df[CAND + PRED]
    X_shuf = X_full.copy()
    perm = rng.permutation(len(df))
    for c in PRED: X_shuf[c] = X_shuf[c].values[perm]
    m_c = run(df[CAND], "candidate-only",           "Q2")
    m_f = run(X_full,   "full (cand + predecessor)", "Q2")
    m_s = run(X_shuf,   "full w/ SHUFFLED pred",     "Q2")
    log(f"  >>> correct predecessor = {m_f['f1'] - m_s['f1']:+.4f} F1 "
        f"(notebook 1 gave +0.0256 on confounded data)")

    # Q3 - transfer
    log("Q3 - cross-ecosystem transfer")
    FE = CAND + PRED
    for src, tgt in [("npm", "pypi"), ("pypi", "npm")]:
        tr, te = df[df.ecosystem == src], df[df.ecosystem == tgt]
        if tr.label.nunique() < 2 or te.label.nunique() < 2 or len(te) < 20:
            log(f"  train {src} -> test {tgt}: insufficient data, skipped"); continue
        mdl = clf().fit(tr[FE], tr.label)
        pr = mdl.predict_proba(te[FE])[:, 1]
        m = M(te.label.values, (pr >= .5).astype(int), pr)
        log(f"  train {src:5s} -> test {tgt:5s} F1={m['f1']:.3f} ROC-AUC={m.get('roc_auc', 0):.3f}")
        R.setdefault("Q3", {})[f"{src}_to_{tgt}"] = m

    # per-ecosystem, from ONE unified model (reconciles the FPR mismatch)
    pr = cross_val_predict(clf(), df[FE + ["eco_npm"]], y, cv=cv, groups=groups,
                           method="predict_proba")[:, 1]
    pred = (pr >= .5).astype(int)
    R["per_ecosystem"] = {}
    for eco in ["npm", "pypi"]:
        msk = (df.ecosystem == eco).values
        if msk.sum() and len(set(y[msk])) > 1:
            m = M(y[msk], pred[msk], pr[msk])
            log(f"  {eco:5s} F1={m['f1']:.3f} Rec={m['recall']:.3f} FPR={m['fpr']:.3f}")
            R["per_ecosystem"][eco] = m

    # size-proxy control: do the raw counts merely measure package size?
    if NORM and "size_kb_after" in df.columns:
        sub = df[df[NORM + ["size_kb_after"]].notna().all(axis=1)]
        if len(sub) > 100 and sub.label.nunique() > 1 and sub.package.nunique() > 10:
            try:
                cvs = StratifiedGroupKFold(min(5, sub.label.value_counts().min()),
                                           shuffle=True, random_state=SEED)
                for nm, cols in [("size-only baseline", ["size_kb_after"]),
                                 ("normalised counts", NORM)]:
                    p = cross_val_predict(clf(), sub[cols], sub.label, cv=cvs,
                                          groups=sub.package, method="predict_proba")[:, 1]
                    m = M(sub.label.values, (p >= .5).astype(int), p)
                    log(f"  [subset n={len(sub)}] {nm:24s} F1={m['f1']:.3f} "
                        f"PR-AUC={m.get('pr_auc', 0):.3f}")
                    R.setdefault("size_control", {})[nm] = m
            except Exception as e:
                log(f"  size control skipped: {type(e).__name__}")

    R["dataset"] = {
        "n": int(len(df)),
        "by_eco_label": {f"{a}_{b}": int(c)
                         for (a, b), c in df.groupby(["ecosystem", "label"]).size().items()},
        "by_origin": {k: int(v) for k, v in df.origin.value_counts().items()},
        "prior_npm":  round(float(df[df.ecosystem == "npm"].label.mean()), 4),
        "prior_pypi": round(float(df[df.ecosystem == "pypi"].label.mean()), 4),
    }
    return R

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    t0 = time.time()
    try:
        matched  = stage1_matched_negatives()
        pypi_new = stage2_pypi_expansion()
        df       = stage3_rebuild(matched, pypi_new)
        results  = stage4_evaluate(df)
        with open(OUT_RESULTS, "w") as fh:
            json.dump(results, fh, indent=2, default=str)
        log("=" * 70)
        log(f"DONE in {(time.time()-t0)/60:.1f} min")
        log(f"  {OUT_FEATURES}")
        log(f"  {OUT_RESULTS}")
        log("Send me those two files.")
    except SystemExit as e:
        log(f"STOPPED: {e}")
    except Exception:
        log("UNHANDLED ERROR - progress is saved, re-run to resume:\n" + traceback.format_exc())

if __name__ == "__main__":
    main()
