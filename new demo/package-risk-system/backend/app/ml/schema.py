import csv
import io
import numpy as np
import pandas as pd

SIGNALS = ['net_http', 'subprocess_exec', 'env_cred_access', 'filesystem', 'encoded_blob', 'install_hook', 'obfuscation']
FEATURES = [f'{prefix}_{signal}' for signal in SIGNALS for prefix in ('add', 'rem', 'net')]
FEATURES += [f'addrate_{signal}' for signal in SIGNALS]
FEATURES += ['added_lines', 'removed_lines', 'files_touched', 'files_new', 'files_total', 'churn_ratio', 'touched_frac',
             'tb_blocks', 'tb_src_blocks', 'tb_sink_blocks', 'tb_both_blocks', 'tb_chain_blocks', 'tb_encoded_flow', 'tb_both_rate', 'tb_chain_rate',
             'sc_added_entropy', 'sc_long_strings', 'sc_hex_escapes', 'sc_max_line_len', 'sc_mean_line_len', 'sc_toplevel_stmts', 'sc_toplevel_rate', 'sc_ident_entropy', 'sc_mean_ident_len', 'sc_nonascii_rate',
             'ih_manifest_changed', 'ih_scripts_added', 'ih_install_hook_added', 'ih_deps_added', 'ih_setup_changed', 'ih_hook_has_network', 'ih_hook_has_exec']
AGGREGATIONS = ['mean', 'max', 'median', 'std']
AGG_FEATURES = [f'{f}__{agg}' for agg in AGGREGATIONS for f in FEATURES]
assert len(FEATURES) == 60 and len(AGG_FEATURES) == 240

def read_csv(data: bytes) -> pd.DataFrame:
    try:
        text = data.decode('utf-8-sig')
        header = next(csv.reader(io.StringIO(text)))
        if len(header) != len(set(header)):
            raise ValueError('Duplicate CSV column names are not allowed.')
        return pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
    except (UnicodeError, StopIteration, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        raise ValueError('Upload a nonempty UTF-8 CSV with a header.') from exc

def validate_features(df: pd.DataFrame, versions=False) -> pd.DataFrame:
    required = ['package', *FEATURES] + (['previous_version', 'current_version'] if versions else [])
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError('Missing columns: ' + ', '.join(missing))
    if df.empty or len(df) > 10000:
        raise ValueError('Expected 1–10,000 version-pair rows.')
    if df.columns.duplicated().any():
        raise ValueError('Duplicate columns are not allowed.')
    out = df.copy()
    for c in ['package'] + (['previous_version', 'current_version'] if versions else []):
        if out[c].isna().any() or out[c].astype(str).str.strip().eq('').any():
            raise ValueError(f'{c} must contain nonempty strings.')
        out[c] = out[c].astype(str)
    try:
        out[FEATURES] = out[FEATURES].apply(pd.to_numeric, errors='raise').astype(float)
    except (ValueError, TypeError) as exc:
        raise ValueError('All 60 features must be numeric.') from exc
    if not np.isfinite(out[FEATURES].to_numpy()).all():
        raise ValueError('All 60 features must be finite; NaN and infinity are not allowed.')
    return out

def validate_training(df: pd.DataFrame) -> pd.DataFrame:
    out = validate_features(df)
    if 'label' not in out:
        raise ValueError('Missing target column: label.')
    try:
        labels = pd.to_numeric(out.label, errors='raise')
    except ValueError as exc:
        raise ValueError('Labels must be 0 (clean) or 1 (malicious).') from exc
    if not labels.isin([0, 1]).all():
        raise ValueError('Labels must be 0 (clean) or 1 (malicious).')
    out['label'] = labels.astype(int)
    if out.groupby('package').label.nunique().ne(1).any():
        raise ValueError('Each package must have exactly one consistent label.')
    actual = (len(out), int((labels == 1).sum()), int((labels == 0).sum()), out.package.nunique())
    if actual != (615, 360, 255, 180):
        raise ValueError(f'Expected rows/malicious/benign/packages = 615/360/255/180; received {actual}.')
    counts = out.groupby('package').label.first().value_counts().to_dict()
    if counts != {1: 128, 0: 52}:
        raise ValueError(f'Expected 128 malicious and 52 clean packages; received {counts}.')
    return out
