"""
=============================================================================
 REMAINING REVIEWER REQUESTS - standalone, self-contained
 Scientific Reports 35109da0

   PART C  runtime measurements        (R2-8)   ~20 min, unattended
   PART B  manual verification sheet   (R1-2, R3-1)  ~15 min to build

 Paste into ONE Colab cell and run:   %run remaining_requests.py
 Everything is written to MyDrive/paper_revision/.
=============================================================================
"""
import os, io, re, sys, json, time, math, difflib, tarfile, zipfile, warnings
warnings.filterwarnings("ignore")
import requests, numpy as np, pandas as pd

# ---------------------------------------------------------------- workdir
try:
    from google.colab import drive
    if not os.path.ismount("/content/drive"):
        drive.mount("/content/drive")
    WORK = "/content/drive/MyDrive/paper_revision"
except Exception:
    WORK = os.path.abspath("./paper_revision")
os.makedirs(WORK, exist_ok=True)
P = lambda n: os.path.join(WORK, n)

def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    try:
        open(P("pipeline_log.txt"), "a").write(line + "\n")
    except Exception:
        pass

KEY = {"package": str, "ecosystem": str, "version_before": str, "version_after": str}
clean = pd.read_csv(P("features_v6_clean.csv"), dtype=KEY)
clean["label"] = clean.label.astype(int)
mal = clean[clean.label == 1].copy()
log(f"loaded features_v6_clean.csv: {clean.shape} | malicious {len(mal)}")

# ---------------------------------------------------------------- registry
HEADERS = {"User-Agent": "supply-chain-research/1.0 (academic)"}
DELAY, RETRIES = 0.35, 3

def _req(url, want_json, timeout):
    for a in range(RETRIES):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            time.sleep(DELAY)
            if r.status_code == 200:
                return r.json() if want_json else r.content
            if r.status_code in (429, 500, 502, 503):
                time.sleep(2 ** a); continue
            return None
        except requests.RequestException:
            time.sleep(2 ** a)
        except ValueError:
            return None
    return None

def tarball_url(pkg, eco, v):
    if eco == "npm":
        m = _req(f"https://registry.npmjs.org/{pkg}", True, 15)
        try:
            return m["versions"][v]["dist"]["tarball"]
        except (KeyError, TypeError):
            return None
    m = _req(f"https://pypi.org/pypi/{pkg}/json", True, 15)
    try:
        fs = m["releases"].get(v, [])
        if not fs:
            return None
        sd = [f for f in fs if f["url"].endswith((".tar.gz", ".zip"))]
        return (sd[0] if sd else fs[0])["url"]
    except (KeyError, TypeError):
        return None

def strip_root(n):
    p = n.split("/", 1)
    return p[1] if len(p) > 1 else n

def extract_map(arch, eco):
    if not arch:
        return {}
    exts = (".js", ".ts", ".json", ".mjs", ".cjs") if eco == "npm" \
           else (".py", ".cfg", ".toml", ".txt")
    out = {}
    try:
        try:
            with tarfile.open(fileobj=io.BytesIO(arch), mode="r:gz") as t:
                for m in t.getmembers():
                    if m.isfile() and m.name.endswith(exts) and m.size < 2_000_000:
                        f = t.extractfile(m)
                        if f:
                            out[strip_root(m.name)] = f.read().decode("utf-8", "ignore")
        except tarfile.ReadError:
            with zipfile.ZipFile(io.BytesIO(arch)) as z:
                for n in z.namelist():
                    if n.endswith(exts):
                        try:
                            out[strip_root(n)] = z.read(n).decode("utf-8", "ignore")
                        except Exception:
                            pass
    except Exception:
        return {}
    return out

def unified_diff(fb, fa, max_lines=300):
    chunks = []
    for path in sorted(set(fa) | set(fb)):
        b, a = fb.get(path, ""), fa.get(path, "")
        if b == a:
            continue
        d = list(difflib.unified_diff(b.splitlines(), a.splitlines(),
                                      fromfile=f"a/{path}", tofile=f"b/{path}", n=2))
        if d:
            chunks.append("\n".join(d[:max_lines]))
    return "\n\n".join(chunks)[:40000]

# =============================================================================
# PART C - runtime measurements  (R2-8)
# =============================================================================
def part_c(n_sample=40):
    log("=" * 70)
    log("PART C - end-to-end runtime measurements")
    import tracemalloc
    sample = clean.sample(min(n_sample, len(clean)), random_state=42)
    recs = []
    tracemalloc.start()
    for n, r in enumerate(sample.itertuples(index=False), 1):
        t0 = time.perf_counter()
        u = tarball_url(r.package, r.ecosystem, str(r.version_after))
        t1 = time.perf_counter()
        arch = _req(u, False, 30) if u else None
        t2 = time.perf_counter()
        files = extract_map(arch, r.ecosystem) if arch else {}
        t3 = time.perf_counter()
        recs.append({"ecosystem": r.ecosystem,
                     "metadata_s": t1 - t0, "download_s": t2 - t1, "extract_s": t3 - t2,
                     "archive_kb": (len(arch) / 1024 if arch else 0),
                     "n_files": len(files), "ok": int(bool(files))})
        if n % 10 == 0:
            log(f"  {n}/{len(sample)}")
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    t = pd.DataFrame(recs)
    ok = t[t.ok == 1]
    if not len(ok):
        log("no successful downloads - skipping"); return
    tot = ok.metadata_s + ok.download_s + ok.extract_s

    log(f"peak memory: {peak/1e6:.1f} MB")
    log(f"failure rate: {1 - t.ok.mean():.3f}")
    summ = ok.groupby("ecosystem")[["metadata_s", "download_s", "extract_s",
                                    "archive_kb", "n_files"]].agg(["median", "mean"])
    log("per-stage timings by ecosystem:")
    print(summ.round(3).to_string())
    log(f"end-to-end per candidate: median {tot.median():.2f}s  mean {tot.mean():.2f}s")
    net_share = 100 * (ok.metadata_s + ok.download_s).sum() / max(tot.sum(), 1e-9)
    log(f"network share of runtime: {net_share:.1f}%")
    log(f"throughput: {3600/max(tot.mean(),1e-9):.0f} candidates/hour, single-threaded")

    # inference cost, measured separately
    from sklearn.ensemble import HistGradientBoostingClassifier
    F = [c for c in clean.columns
         if c.startswith(("add_", "rem_", "net_", "addrate_", "tb_", "sc_", "ih_"))]
    X = clean[F].fillna(0).values
    m = HistGradientBoostingClassifier(max_iter=300, random_state=42).fit(X, clean.label)
    t0 = time.perf_counter()
    for _ in range(20):
        m.predict_proba(X)
    inf = (time.perf_counter() - t0) / (20 * len(X))
    log(f"inference: {inf*1e6:.1f} microseconds per candidate")

    json.dump({
        "n_sampled": int(len(t)),
        "peak_memory_mb": round(peak / 1e6, 1),
        "failure_rate": round(float(1 - t.ok.mean()), 4),
        "median_end_to_end_s": round(float(tot.median()), 3),
        "mean_end_to_end_s": round(float(tot.mean()), 3),
        "network_share_pct": round(float(net_share), 1),
        "throughput_per_hour": int(3600 / max(tot.mean(), 1e-9)),
        "inference_us": round(inf * 1e6, 2),
        "by_ecosystem": json.loads(summ.round(4).to_json()),
    }, open(P("runtime_measurements.json"), "w"), indent=2)
    log("saved runtime_measurements.json")

# =============================================================================
# PART B - manual verification  (R1-2, R3-1)
# =============================================================================
POPULAR = {
 "npm": ["lodash","react","express","axios","chalk","commander","debug","moment","request",
         "async","underscore","jquery","webpack","babel","eslint","typescript","dotenv",
         "colors","uuid","yargs","semver","glob","minimist","mkdirp","rimraf","cross-env"],
 "pypi": ["requests","urllib3","numpy","pandas","flask","django","setuptools","six","click",
          "jinja2","pyyaml","boto3","pytest","scipy","pillow","cryptography","certifi",
          "colorama","python-dateutil","beautifulsoup4","matplotlib","tqdm"],
}

def lev(a, b):
    if abs(len(a) - len(b)) > 2:
        return 9
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j-1] + 1, prev[j-1] + (ca != cb)))
        prev = cur
    return prev[-1]

def version_index(pkg, eco, v):
    if eco == "npm":
        m = _req(f"https://registry.npmjs.org/{pkg}", True, 15)
        if not m: return None, None
        t = m.get("time", {}) or {}
        vs = sorted([x for x in (m.get("versions") or {}) if t.get(x)], key=lambda x: t[x])
    else:
        m = _req(f"https://pypi.org/pypi/{pkg}/json", True, 15)
        if not m: return None, None
        rel = m.get("releases", {}) or {}
        vs = sorted([k for k, f in rel.items() if f],
                    key=lambda k: rel[k][0].get("upload_time_iso_8601", ""))
    return (vs.index(v) if v in vs else None), len(vs)

def exclusion_rules():
    """Automatic rules first, so only genuinely ambiguous pairs need human review."""
    CK = P("exclusion_rules.csv")
    m2 = mal.copy()
    flagged = set(zip(m2.package, m2.ecosystem, m2.version_after.astype(str)))
    # the reviewer's concern is a predecessor that is itself flagged
    m2["predecessor_flagged"] = [int((p, e, str(v)) in flagged)
                                 for p, e, v in zip(m2.package, m2.ecosystem, m2.version_before)]
    m2["n_flagged_in_pkg"] = m2.groupby(["package", "ecosystem"]).package.transform("size")

    done = set()
    if os.path.exists(CK):
        prev = pd.read_csv(CK, dtype=KEY)
        done = set(zip(prev.package.astype(str), prev.version_after.astype(str)))
        log(f"resuming exclusion rules - {len(done)} done")

    rows = []
    for n, r in enumerate(m2.itertuples(index=False), 1):
        if (str(r.package), str(r.version_after)) in done:
            continue
        idx, total = version_index(r.package, r.ecosystem, str(r.version_after))
        name = r.package.lower().split("/")[-1]
        ts = min((lev(name, p) for p in POPULAR.get(r.ecosystem, [])), default=9)
        rows.append({"package": r.package, "ecosystem": r.ecosystem,
                     "version_before": r.version_before, "version_after": r.version_after,
                     "version_index": -1 if idx is None else idx,
                     "n_versions": total or -1,
                     "first_release": int(idx == 0) if idx is not None else 0,
                     "repeated_malicious": int(r.predecessor_flagged),
                     "typosquat_suspect": int(0 < ts <= 2),
                     "empty_diff": int(r.added_lines == 0)})
        if n % 25 == 0:
            pd.DataFrame(rows).to_csv(CK, mode="a", header=not os.path.exists(CK), index=False)
            rows = []
            log(f"  {n}/{len(m2)} rules applied")
    if rows:
        pd.DataFrame(rows).to_csv(CK, mode="a", header=not os.path.exists(CK), index=False)

    rules = pd.read_csv(CK, dtype=KEY).drop_duplicates(subset=["package", "version_after"])
    cols = ["first_release", "repeated_malicious", "typosquat_suspect", "empty_diff"]
    rules["excluded"] = (rules[cols].sum(axis=1) > 0).astype(int)
    log("automatic exclusions (funnel counts for the paper):")
    print(rules[cols].sum().to_string())
    log(f"excluded: {int(rules.excluded.sum())} of {len(rules)}   "
        f"remaining for review: {int((~rules.excluded.astype(bool)).sum())}")
    log(f"(reported, not excluded: {int((m2.n_flagged_in_pkg > 3).sum())} pairs sit in "
        f"packages with >3 separate flagged versions)")
    json.dump({"counts": {c: int(rules[c].sum()) for c in cols},
               "excluded": int(rules.excluded.sum()), "total": int(len(rules)),
               "remaining": int((~rules.excluded.astype(bool)).sum())},
              open(P("exclusion_summary.json"), "w"), indent=2)
    return rules

HTML_TMPL = """<!doctype html><html><head><meta charset="utf-8"><title>Pair verification</title>
<style>
body{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f6f7f9;color:#111}
header{position:sticky;top:0;background:#fff;border-bottom:1px solid #ddd;padding:10px 18px;
 display:flex;gap:14px;align-items:center;flex-wrap:wrap;z-index:9}
h1{font-size:15px;margin:0;font-weight:600}
.meta{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:#444}
.wrap{padding:14px 18px;max-width:1150px;margin:0 auto}
pre{background:#fff;border:1px solid #ddd;border-radius:6px;padding:12px;overflow:auto;
 max-height:62vh;font-family:ui-monospace,Menlo,monospace;font-size:12px;white-space:pre-wrap}
.add{background:#e6ffed}.del{background:#ffeef0}.hdr{color:#666;font-weight:600}
button{font:14px inherit;padding:9px 13px;border-radius:6px;border:1px solid #ccc;
 background:#fff;cursor:pointer}
button:hover{background:#eee}
.b1{border-color:#c00;color:#c00}.b2{border-color:#06c;color:#06c}
.b3{border-color:#a60;color:#a60}.b4{border-color:#666;color:#666}
#bar{height:4px;background:#06c;width:0;transition:width .2s}
.hint{font-size:12px;color:#666;margin:6px 0 10px}
</style></head><body>
<div id="bar"></div>
<header>
  <h1>Update-compromise verification</h1>
  <span class="meta" id="pos"></span>
  <span class="meta" id="pkg"></span>
  <span style="flex:1"></span>
  <button onclick="back()">&larr; back</button>
  <button onclick="exportCsv()">export CSV</button>
</header>
<div class="wrap">
  <div style="display:flex;gap:8px;flex-wrap:wrap">
    <button class="b1" onclick="mark('update_compromise')">1&nbsp; update compromise</button>
    <button class="b2" onclick="mark('malware_from_origin')">2&nbsp; malware from origin</button>
    <button class="b3" onclick="mark('typosquat')">3&nbsp; typosquat / confusion</button>
    <button class="b4" onclick="mark('unclear')">4&nbsp; unclear</button>
  </div>
  <div class="hint">Keys 1-4 to classify, Backspace to undo. Progress saves automatically.
   Judge whether a <b>previously benign</b> package was compromised <b>in this update</b>.</div>
  <pre id="diff"></pre>
</div>
<script>
const ITEMS = __ITEMS__;
let i = 0, ans = JSON.parse(localStorage.getItem('verif')||'{}');
function key(it){return it.package+'|'+it.version_before+'|'+it.version_after}
function render(){
  while(i<ITEMS.length && ans[key(ITEMS[i])]) i++;
  const done=Object.keys(ans).length;
  document.getElementById('bar').style.width=(100*done/ITEMS.length)+'%';
  if(i>=ITEMS.length){
    document.getElementById('diff').textContent='All '+done+' done. Click "export CSV".';
    document.getElementById('pos').textContent=done+' / '+ITEMS.length;
    document.getElementById('pkg').textContent='';return;}
  const it=ITEMS[i];
  document.getElementById('pos').textContent=(i+1)+' / '+ITEMS.length+'  ('+done+' done)';
  document.getElementById('pkg').textContent=it.package+' ['+it.ecosystem+']  '+
    it.version_before+' \\u2192 '+it.version_after;
  const pre=document.getElementById('diff');pre.innerHTML='';
  it.diff.split('\\n').forEach(function(l){
    const s=document.createElement('span'); s.textContent=l+'\\n';
    if(l.startsWith('+')&&!l.startsWith('+++'))s.className='add';
    else if(l.startsWith('-')&&!l.startsWith('---'))s.className='del';
    else if(l.startsWith('@@')||l.startsWith('---')||l.startsWith('+++'))s.className='hdr';
    pre.appendChild(s);});
  pre.scrollTop=0;
}
function mark(v){ans[key(ITEMS[i])]=v;localStorage.setItem('verif',JSON.stringify(ans));i++;render()}
function back(){if(i>0){i--;delete ans[key(ITEMS[i])];
  localStorage.setItem('verif',JSON.stringify(ans));render()}}
function exportCsv(){
  let out='package,ecosystem,version_before,version_after,verdict\\n';
  ITEMS.forEach(function(it){const v=ans[key(it)];
    if(v)out+=[it.package,it.ecosystem,it.version_before,it.version_after,v].join(',')+'\\n';});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(new Blob([out],{type:'text/csv'}));
  a.download='manual_verification.csv';a.click();
}
document.addEventListener('keydown',function(e){
  if(['1','2','3','4'].indexOf(e.key)>=0)
    mark(['update_compromise','malware_from_origin','typosquat','unclear'][+e.key-1]);
  if(e.key==='Backspace'){e.preventDefault();back();}});
render();
</script></body></html>"""

def part_b(n_review=120):
    log("=" * 70)
    log("PART B - manual verification")
    rules = exclusion_rules()

    CK_ITEMS = P("review_items.json")
    if os.path.exists(CK_ITEMS):
        items = json.load(open(CK_ITEMS))
        log(f"reusing review_items.json ({len(items)} pairs)")
    else:
        pool = rules[rules.excluded == 0]
        review = pool.sample(min(n_review, len(pool)), random_state=42)
        log(f"fetching diffs for {len(review)} pairs (~{max(1,len(review)*3//60)} min)")
        items = []
        for n, r in enumerate(review.itertuples(index=False), 1):
            fa = extract_map(_req(tarball_url(r.package, r.ecosystem,
                                              str(r.version_after)), False, 30), r.ecosystem)
            fb = extract_map(_req(tarball_url(r.package, r.ecosystem,
                                              str(r.version_before)), False, 30), r.ecosystem)
            d = unified_diff(fb, fa) if fa else "(archive unavailable)"
            items.append({"package": r.package, "ecosystem": r.ecosystem,
                          "version_before": str(r.version_before),
                          "version_after": str(r.version_after),
                          "diff": d or "(no textual change detected)"})
            if n % 20 == 0:
                json.dump(items, open(CK_ITEMS, "w"))
                log(f"  {n}/{len(review)}")
        json.dump(items, open(CK_ITEMS, "w"))

    html = HTML_TMPL.replace("__ITEMS__", json.dumps(items))
    open(P("verification_sheet.html"), "w", encoding="utf-8").write(html)
    log(f"saved verification_sheet.html ({len(html)//1024} KB, {len(items)} pairs)")
    log("Download it, open in a browser, press 1-4 per pair.")
    try:
        from google.colab import files
        files.download(P("verification_sheet.html"))
    except Exception:
        pass

def summarise_verification():
    """Run after manual_verification.csv is back in the Drive folder."""
    MV = P("manual_verification.csv")
    if not os.path.exists(MV):
        log("manual_verification.csv not found yet - export it from the HTML sheet, "
            "put it in the Drive folder, then call summarise_verification()")
        return
    mv = pd.read_csv(MV)
    vc = mv.verdict.value_counts()
    n = len(mv); k = int(vc.get("update_compromise", 0))
    p = k / n
    se = math.sqrt(p * (1 - p) / n)
    log(f"reviewed: {n}")
    print(vc.to_string())
    log(f"update-compromise rate: {p:.3f}  95% CI "
        f"[{max(0,p-1.96*se):.3f}, {min(1,p+1.96*se):.3f}]")
    json.dump({"n_reviewed": n, "counts": {k_: int(v) for k_, v in vc.items()},
               "rate": round(p, 4),
               "ci95": [round(max(0, p-1.96*se), 4), round(min(1, p+1.96*se), 4)]},
              open(P("manual_verification_summary.json"), "w"), indent=2)
    log("saved manual_verification_summary.json")

# =============================================================================
if __name__ == "__main__":
    part_c()
    part_b()
    summarise_verification()
    log("=" * 70)
    log("DONE. Send back: runtime_measurements.json, exclusion_summary.json,")
    log("and manual_verification_summary.json once the sheet is completed.")
