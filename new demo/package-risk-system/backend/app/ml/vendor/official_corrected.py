import re, io, tarfile, zipfile, difflib, math, json
from collections import Counter

# feature extraction identical to notebook 5 so the new rows are comparable
SUSPICIOUS = {
  "net_http":        re.compile(r"\b(https?://|requests\.(get|post)|urllib|fetch\(|XMLHttpRequest|http\.request|axios)", re.I),
  "subprocess_exec": re.compile(r"\b(subprocess|child_process|os\.system|exec\(|eval\(|spawn\(|popen)", re.I),
  "env_cred_access": re.compile(r"(process\.env|os\.environ|getenv|\.aws/credentials|id_rsa|\.npmrc|\.pypirc|SSH_|API_KEY|SECRET)", re.I),
  "filesystem":      re.compile(r"\b(fs\.(write|read|unlink)|open\([^)]*['\"]w|shutil|os\.remove|writeFile)", re.I),
  "encoded_blob":    re.compile(r"(base64|atob|btoa|fromCharCode|eval\(.*decode|exec\(.*decode)", re.I),
  "install_hook":    re.compile(r"(preinstall|postinstall|setup\.py|cmdclass|__import__)", re.I),
  "obfuscation":     re.compile(r"(_0x[0-9a-f]{4,}|[A-Za-z0-9+/]{120,})", re.I),
}
SOURCES = re.compile(r"(process\.env|os\.environ|getenv|\.aws/credentials|id_rsa|"
                     r"\.npmrc|\.pypirc|SSH_|API_KEY|SECRET|TOKEN|PASSWORD|"
                     r"expanduser|homedir|hostname|platform\(\)|userInfo)", re.I)
SINKS   = re.compile(r"(https?://|fetch\(|axios|request\(|urlopen|requests\.(get|post)|"
                     r"\.send\(|socket|exec\(|spawn\(|system\(|popen|eval\()", re.I)
ENCODE  = re.compile(r"(base64|b64encode|atob|btoa|hex|fromCharCode|encodeURI|JSON\.stringify)", re.I)
LONG_STR = re.compile(r"['\"][A-Za-z0-9+/=_\-]{80,}['\"]")
HEXESC   = re.compile(r"(\\x[0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4})")
MAX_LINES = 20000

def strip_root(n):
    p = n.split("/", 1); return p[1] if len(p) > 1 else n

def extract_map(arch, eco):
    if not arch: return {}
    exts = (".js",".ts",".json",".mjs",".cjs") if eco=="npm" else (".py",".cfg",".toml",".txt")
    out = {}
    try:
        try:
            with tarfile.open(fileobj=io.BytesIO(arch), mode="r:gz") as t:
                for m in t.getmembers():
                    if m.isfile() and m.name.endswith(exts) and m.size < 2_000_000:
                        f = t.extractfile(m)
                        if f: out[strip_root(m.name)] = f.read().decode("utf-8","ignore")
        except tarfile.ReadError:
            with zipfile.ZipFile(io.BytesIO(arch)) as z:
                for n in z.namelist():
                    if n.endswith(exts):
                        try: out[strip_root(n)] = z.read(n).decode("utf-8","ignore")
                        except Exception: pass
    except Exception: return {}
    return out

def added_lines_of(b, a):
    A = b.splitlines()[:MAX_LINES]; B = a.splitlines()[:MAX_LINES]
    if not A: return B
    out = []
    for tag,i1,i2,j1,j2 in difflib.SequenceMatcher(None, A, B, autojunk=False).get_opcodes():
        if tag in ("insert","replace"): out.extend(B[j1:j2])
    return out

def diff_of_pair(fb, fa):
    added, removed, touched, newf = [], [], 0, 0
    for path, at in fa.items():
        bt = fb.get(path)
        if bt is None:
            added.extend(at.splitlines()[:MAX_LINES]); newf += 1; touched += 1
        elif bt != at:
            added.extend(added_lines_of(bt, at)); removed.extend(added_lines_of(at, bt)); touched += 1
    return "\n".join(added), "\n".join(removed), touched, newf

def shannon(s):
    if not s: return 0.0
    n=len(s); return -sum((c/n)*math.log2(c/n) for c in Counter(s).values())

def split_blocks(text, eco):
    lines = text.splitlines(); blocks, cur, depth = [], [], 0
    if eco == "npm":
        for ln in lines:
            cur.append(ln); depth += ln.count("{") - ln.count("}")
            if depth <= 0 and len(cur) > 1: blocks.append("\n".join(cur)); cur=[]; depth=0
        if cur: blocks.append("\n".join(cur))
    else:
        for ln in lines:
            if ln and not ln[0].isspace() and cur: blocks.append("\n".join(cur)); cur=[]
            cur.append(ln)
        if cur: blocks.append("\n".join(cur))
    merged, buf = [], ""
    for b in blocks:
        buf = (buf+"\n"+b).strip() if buf else b
        if buf.count("\n") >= 3: merged.append(buf); buf=""
    if buf: merged.append(buf)
    return merged or ([text] if text else [])

def all_features(fb, fa, eco):
    added, removed, touched, newf = diff_of_pair(fb, fa)
    f = {}
    for k, rx in SUSPICIOUS.items():
        f[f"add_{k}"] = len(rx.findall(added)); f[f"rem_{k}"] = len(rx.findall(removed))
        f[f"net_{k}"] = f[f"add_{k}"] - f[f"rem_{k}"]
    n_add = max(added.count("\n")+1, 1)
    for k in SUSPICIOUS: f[f"addrate_{k}"] = round(f[f"add_{k}"]/n_add, 5)
    f["added_lines"] = added.count("\n")+1 if added else 0
    f["removed_lines"] = removed.count("\n")+1 if removed else 0
    f["files_touched"] = touched; f["files_new"] = newf; f["files_total"] = len(fa)
    f["churn_ratio"] = round(f["added_lines"]/max(f["removed_lines"],1),4)
    f["touched_frac"] = round(touched/max(len(fa),1),4)
    blocks = split_blocks(added, eco)
    n_src=n_snk=n_both=n_chain=n_enc=0
    for b in blocks:
        s=bool(SOURCES.search(b)); k=bool(SINKS.search(b)); n_src+=s; n_snk+=k
        if s and k:
            n_both+=1
            if ENCODE.search(b): n_enc+=1
            tainted={m_.group(1) for m_ in re.finditer(
                r"(?:const|let|var)?\s*([A-Za-z_$][\w$]{0,30})\s*=\s*([^;\n]{0,200})", b)
                if SOURCES.search(m_.group(2))}
            for sm in SINKS.finditer(b):
                seg=b[sm.start():min(len(b),sm.end()+300)]
                if any(re.search(r"\b"+re.escape(v)+r"\b", seg) for v in tainted):
                    n_chain+=1; break
    nb=max(len(blocks),1)
    f.update(tb_blocks=len(blocks), tb_src_blocks=n_src, tb_sink_blocks=n_snk,
             tb_both_blocks=n_both, tb_chain_blocks=n_chain, tb_encoded_flow=n_enc,
             tb_both_rate=round(n_both/nb,4), tb_chain_rate=round(n_chain/nb,4))
    lines=[l for l in added.splitlines() if l.strip()]; n=max(len(lines),1)
    idents=re.findall(r"[A-Za-z_$][\w$]{2,}", added); top=0
    for l in lines:
        if eco=="npm":
            if l and not l[0].isspace() and not l.lstrip().startswith(("//","/*","*","import","export")): top+=1
        else:
            if l and not l[0].isspace() and not l.lstrip().startswith(("#","import","from","def ","class ")): top+=1
    f.update(sc_added_entropy=round(shannon(added[:50000]),4),
             sc_long_strings=len(LONG_STR.findall(added)),
             sc_hex_escapes=len(HEXESC.findall(added)),
             sc_max_line_len=max((len(l) for l in lines), default=0),
             sc_mean_line_len=round(sum(len(l) for l in lines)/n,2),
             sc_toplevel_stmts=top, sc_toplevel_rate=round(top/n,4),
             sc_ident_entropy=round(shannon("".join(idents[:4000])),4),
             sc_mean_ident_len=round(sum(map(len,idents))/max(len(idents),1),2),
             sc_nonascii_rate=round(sum(ord(c)>127 for c in added[:50000])/max(min(len(added),50000),1),5))
    ih = {"ih_manifest_changed":0,"ih_scripts_added":0,"ih_install_hook_added":0,
          "ih_deps_added":0,"ih_setup_changed":0,"ih_hook_has_network":0,"ih_hook_has_exec":0}
    if eco=="npm":
        pb,pa = fb.get("package.json",""), fa.get("package.json","")
        if pb!=pa: ih["ih_manifest_changed"]=1
        try: jb=json.loads(pb) if pb else {}; ja=json.loads(pa) if pa else {}
        except Exception: jb,ja={},{}
        sb,sa=(jb.get("scripts") or {}),(ja.get("scripts") or {})
        ih["ih_scripts_added"]=max(len(sa)-len(sb),0)
        for hook in ("preinstall","install","postinstall","prepare"):
            if sa.get(hook) and sa.get(hook)!=sb.get(hook):
                ih["ih_install_hook_added"]=1; body=str(sa.get(hook))
                if SINKS.search(body): ih["ih_hook_has_network"]=1
                if re.search(r"(node |curl|wget|sh -c|bash|python)", body, re.I): ih["ih_hook_has_exec"]=1
        ih["ih_deps_added"]=len(set(ja.get("dependencies") or {})-set(jb.get("dependencies") or {}))
    else:
        sb="\n".join(v for k,v in fb.items() if k.endswith(("setup.py","setup.cfg","pyproject.toml")))
        sa="\n".join(v for k,v in fa.items() if k.endswith(("setup.py","setup.cfg","pyproject.toml")))
        if sb!=sa: ih["ih_setup_changed"]=ih["ih_manifest_changed"]=1
        add="\n".join(added_lines_of(sb,sa))
        if re.search(r"(cmdclass|install_requires|setup_requires|__import__|os\.system|subprocess)", add, re.I):
            ih["ih_install_hook_added"]=1
        if SINKS.search(add): ih["ih_hook_has_network"]=1
        if re.search(r"(exec\(|eval\(|os\.system|subprocess)", add, re.I): ih["ih_hook_has_exec"]=1
        ih["ih_deps_added"]=len(re.findall(r"install_requires", add))
    f.update(ih)
    return f

