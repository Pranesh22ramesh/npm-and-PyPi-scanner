import json
from .common import download, package_name

def fetch_metadata(package):
    name = package_name(package, 'pypi')
    metadata = json.loads(download(f'https://pypi.org/pypi/{name}/json', {'pypi.org'}))
    releases = []
    for version, files in metadata.get('releases', {}).items():
        sources = [f for f in files if f.get('packagetype') == 'sdist' and not f.get('yanked') and f.get('url','').endswith(('.tar.gz','.zip'))]
        if sources:
            item = sorted(sources, key=lambda f:f['filename'])[0]
            releases.append({'version':version, 'date':item.get('upload_time_iso_8601',item.get('upload_time','')), 'url':item['url']})
    return sorted(releases, key=lambda r: (r['date'],r['version']))

def fetch_archive(release):
    return download(release['url'], {'files.pythonhosted.org'})
