import json
from .common import download, package_name

def fetch_metadata(package):
    name = package_name(package, 'npm')
    metadata = json.loads(download(f'https://registry.npmjs.org/{name}', {'registry.npmjs.org'}))
    times = metadata.get('time', {})
    releases = [{'version': version, 'date': times[version], 'url': info['dist']['tarball']}
                for version, info in metadata.get('versions', {}).items()
                if version in times and info.get('dist', {}).get('tarball')]
    return sorted(releases, key=lambda r: (r['date'], r['version']))

def fetch_archive(release):
    return download(release['url'], {'registry.npmjs.org'})
