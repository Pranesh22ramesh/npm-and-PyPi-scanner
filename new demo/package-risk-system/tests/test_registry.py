import json
import pytest
from app.registry import npm_client,pypi_client
from app.registry.common import download,select_versions,package_name

def test_npm_metadata(monkeypatch):
    data={'time':{'1.0':'2025-01-01','2.0':'2025-02-01'},'versions':{'2.0':{'dist':{'tarball':'https://registry.npmjs.org/p/2.tgz'}},'1.0':{'dist':{'tarball':'https://registry.npmjs.org/p/1.tgz'}}}}
    monkeypatch.setattr(npm_client,'download',lambda url,hosts:json.dumps(data).encode())
    rows=npm_client.fetch_metadata('@scope/test')
    assert [r['version'] for r in rows]==['1.0','2.0']

def test_pypi_sdist_selection(monkeypatch):
    source={'filename':'demo.tar.gz','packagetype':'sdist','url':'https://files.pythonhosted.org/demo.tar.gz','upload_time_iso_8601':'2025-01-01'}
    data={'releases':{'1.0':[source,{'packagetype':'bdist_wheel'}],'2.0':[dict(source,yanked=True)],'3.0':[{'packagetype':'bdist_wheel'}]}}
    monkeypatch.setattr(pypi_client,'download',lambda url,hosts:json.dumps(data).encode())
    assert [r['version'] for r in pypi_client.fetch_metadata('demo')]==['1.0']

@pytest.mark.parametrize('url',['http://registry.npmjs.org/pkg','https://localhost/pkg','https://registry.npmjs.org.evil.test/pkg','https://registry.npmjs.org:8443/pkg','https://user:pass@registry.npmjs.org/pkg'])
def test_ssrf_blocked(url):
    with pytest.raises(ValueError):download(url,{'registry.npmjs.org'})

def test_name_validation_and_recent_selection():
    assert package_name('@scope/name','npm')=='%40scope%2Fname'
    with pytest.raises(ValueError):package_name('../bad','npm')
    rows=[{'version':str(i)} for i in range(15)]
    assert len(select_versions(rows,3))==3
    assert len(select_versions(rows,'all'))==10
