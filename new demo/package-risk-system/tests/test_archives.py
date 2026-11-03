import io
import stat
import tarfile
import zipfile
import pytest
from app.security.safe_archive import safe_map
from app.ml.base_feature_extractor import extract_pair,compatibility
from app.ml.vendor.official_corrected import all_features,extract_map
from app.ml.schema import FEATURES

def tar(files):
    stream=io.BytesIO()
    with tarfile.open(fileobj=stream,mode='w:gz') as archive:
        for name,text in files.items():
            data=text.encode();entry=tarfile.TarInfo(name);entry.size=len(data)
            archive.addfile(entry,io.BytesIO(data))
    return stream.getvalue()

def zip_archive(files):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        for name,text in files.items():
            entry=zipfile.ZipInfo('placeholder')
            entry.filename=name  # Preserve hostile backslashes on Windows.
            archive.writestr(entry,text)
    return stream.getvalue()

@pytest.mark.parametrize('pack',[tar,zip_archive])
@pytest.mark.parametrize('ecosystem,files',[('npm',{'package/index.js':'const value = 1;\n','package/package.json':'{}','package/ignored.md':'text'}),('pypi',{'pkg/main.py':'value = 1\n','pkg/setup.cfg':'[metadata]\nname = demo','pkg/ignored.md':'text'})])
def test_official_archive_map_and_feature_consistency(pack,ecosystem,files):
    before=pack(files)
    after_files=dict(files)
    source=next(iter(files))
    after_files[source]+='\nvalue = 2\n'
    after=pack(after_files)
    assert compatibility()['enabled']
    assert safe_map(before,ecosystem)==extract_map(before,ecosystem)
    expected=all_features(extract_map(before,ecosystem),extract_map(after,ecosystem),ecosystem)
    actual=extract_pair(before,after,ecosystem)
    assert list(actual)==FEATURES and actual==expected
    assert actual['files_touched']==1 and actual['files_new']==0 and actual['added_lines']==2

@pytest.mark.parametrize('name',['../escape.js','/absolute.js','package/../../escape.js','C:/escape.js','package\\escape.js'])
@pytest.mark.parametrize('pack',[tar,zip_archive])
def test_path_traversal_blocked(name,pack):
    with pytest.raises(ValueError,match='Unsafe'):safe_map(pack({name:'x'}),'npm')

def test_tar_symlinks_and_zip_symlinks_blocked():
    data=io.BytesIO()
    with tarfile.open(fileobj=data,mode='w:gz') as archive:
        entry=tarfile.TarInfo('package/link.js');entry.type=tarfile.SYMTYPE;entry.linkname='/etc/passwd';archive.addfile(entry)
    with pytest.raises(ValueError,match='links'):safe_map(data.getvalue(),'npm')
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as archive:
        entry=zipfile.ZipInfo('package/link.js');entry.create_system=3;entry.external_attr=(stat.S_IFLNK|0o777)<<16;archive.writestr(entry,'/etc/passwd')
    with pytest.raises(ValueError,match='links'):safe_map(data.getvalue(),'npm')

def test_archive_limits_empty_collisions(monkeypatch):
    import app.security.safe_archive as archive
    monkeypatch.setattr(archive,'MAX_FILE',10)
    with pytest.raises(ValueError,match='limits'):safe_map(tar({'package/main.js':'x'*11}),'npm')
    monkeypatch.setattr(archive,'MAX_FILE',100)
    monkeypatch.setattr(archive,'MAX_FILES',1)
    with pytest.raises(ValueError,match='limits'):safe_map(tar({'p/a.js':'x','p/b.js':'x'}),'npm')
    monkeypatch.setattr(archive,'MAX_FILES',10)
    with pytest.raises(ValueError,match='colliding'):safe_map(tar({'p/a.js':'x','q/a.js':'y'}),'npm')
    with pytest.raises(ValueError,match='No compatible'):safe_map(tar({'p/README.md':'x'}),'npm')

def test_worker_same_features_and_cleanup():
    from app.ml.feature_extraction import archive_rows
    a=tar({'package/index.js':'const value=1;'}); b=tar({'package/index.js':'const value=2;'})
    rows=archive_rows('static-test','npm',[a,b],['1','2'])
    assert rows[FEATURES].iloc[0].to_dict()==extract_pair(a,b,'npm')
