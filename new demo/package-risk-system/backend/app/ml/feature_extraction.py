import json
import subprocess
import sys
import tempfile
from pathlib import Path
import pandas as pd
from ..config import EXTRACT_TIMEOUT
from ..registry import npm_client, pypi_client
from ..registry.common import select_versions
from .base_feature_extractor import compatibility, BLOCKED

def archive_rows(package, ecosystem, archives, versions, progress=lambda text: None):
    status = compatibility()
    from .model_manager import manager
    if not status['enabled']:
        raise ValueError(BLOCKED)
    if manager.metadata and manager.metadata['extractor_provenance']['extractor_sha256'] != status['provenance']['extractor_sha256']:
        raise ValueError(BLOCKED)
    if len(archives) < 2 or len(archives) != len(versions) or len(archives) > 10:
        raise ValueError('Provide 2–10 archives and one ordered version name per archive.')
    if len(set(versions)) != len(versions) or any(not v.strip() for v in versions):
        raise ValueError('Version names must be nonempty and distinct.')
    progress('Building consecutive version pairs...')
    with tempfile.TemporaryDirectory(prefix='package-risk-') as tmp:
        folder = Path(tmp)
        paths = []
        for i,data in enumerate(archives):
            path = folder / f'{i}.archive'
            path.write_bytes(data)
            paths.append(str(path))
        request, output = folder/'input.json', folder/'output.json'
        request.write_text(json.dumps({'archives':paths,'ecosystem':ecosystem}), encoding='utf-8')
        progress('Extracting security features...')
        try:
            subprocess.run([sys.executable,'-m','app.ml.extract_worker',str(request),str(output)], cwd=Path(__file__).resolve().parents[2], timeout=EXTRACT_TIMEOUT, capture_output=True, check=False)
        except subprocess.TimeoutExpired as exc:
            raise ValueError('Static extraction time limit exceeded; prediction blocked.') from exc
        if not output.exists():
            raise ValueError('Static extraction worker failed; prediction blocked.')
        result = json.loads(output.read_text(encoding='utf-8'))
        if 'error' in result:
            raise ValueError(result['error'])
    return pd.DataFrame([{'package':package, 'previous_version':versions[i], 'current_version':versions[i+1], **features} for i,features in enumerate(result['features'])])

def registry_rows(package, ecosystem, count=3, selected=None, progress=lambda text:None):
    if not compatibility()['enabled']:
        raise ValueError(BLOCKED)
    client = npm_client if ecosystem == 'npm' else pypi_client
    progress('Fetching version history...')
    releases = client.fetch_metadata(package)
    if selected:
        indices = [i for i,r in enumerate(releases) if r['version'] in selected]
        if len(indices) != len(selected) or len(indices) < 2 or len(indices)>10 or indices != list(range(indices[0],indices[-1]+1)):
            raise ValueError('Select 2–10 consecutive compatible releases from the registry history.')
        releases = [releases[i] for i in indices]
    else:
        releases = select_versions(releases, count)
    progress('Downloading source archives...')
    archives = [client.fetch_archive(release) for release in releases]
    return archive_rows(package, ecosystem, archives, [r['version'] for r in releases], progress)
