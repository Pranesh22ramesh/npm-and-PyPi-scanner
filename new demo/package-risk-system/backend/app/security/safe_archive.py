"""Bounded, in-memory static archive reading. Never writes archive paths."""
import io
import stat
import tarfile
import zipfile
from pathlib import PurePosixPath
from ..config import MAX_UPLOAD, MAX_EXTRACTED, MAX_FILES, MAX_FILE

def safe_map(data: bytes, ecosystem: str):
    if ecosystem not in ('npm', 'pypi'):
        raise ValueError('Registry must be npm or pypi.')
    if not data or len(data) > MAX_UPLOAD:
        raise ValueError('Archive is empty or exceeds compressed-size limit.')
    extensions = ('.js','.ts','.json','.mjs','.cjs') if ecosystem == 'npm' else ('.py','.cfg','.toml','.txt')
    result, names, normalized = {}, set(), set()
    total = count = 0

    def check(name, size, regular, directory, link):
        nonlocal total, count
        count += 1
        path = PurePosixPath(name)
        if not name or '\\' in name or ':' in name or '\x00' in name or path.is_absolute() or '..' in path.parts:
            raise ValueError('Unsafe archive path rejected.')
        if link or not (regular or directory):
            raise ValueError('Archive links and special files are forbidden.')
        if name in names:
            raise ValueError('Duplicate archive entry rejected.')
        names.add(name)
        total += size
        if size < 0 or size > MAX_FILE or total > MAX_EXTRACTED or count > MAX_FILES:
            raise ValueError('Archive exceeds file-count or extraction-size limits.')

    def add(name, payload):
        # Official extractor removes precisely the first path component.
        key = name.split('/', 1)[1] if '/' in name else name
        if key in normalized:
            raise ValueError('Archive contains colliding source paths after root removal.')
        normalized.add(key)
        result[key] = payload.decode('utf-8', 'ignore')

    try:
        if zipfile.is_zipfile(io.BytesIO(data)):
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                for item in archive.infolist():
                    if item.orig_filename != item.filename:
                        raise ValueError('Unsafe archive path normalization rejected.')
                    mode = item.external_attr >> 16
                    filetype = stat.S_IFMT(mode)
                    directory = item.is_dir()
                    link = stat.S_ISLNK(mode)
                    check(item.filename, item.file_size, filetype in (0, stat.S_IFREG) and not directory, directory, link)
                    if item.flag_bits & 1:
                        raise ValueError('Encrypted archives are unsupported.')
                    if not directory and item.filename.endswith(extensions):
                        with archive.open(item) as stream:
                            payload = stream.read(MAX_FILE + 1)
                        if len(payload) != item.file_size or len(payload) > MAX_FILE:
                            raise ValueError('Archive entry size mismatch.')
                        add(item.filename, payload)
        else:
            with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
                for item in archive:
                    check(item.name, item.size, item.isfile(), item.isdir(), item.issym() or item.islnk())
                    # Preserve the official tar-only strict 2 MB source filter.
                    if item.isfile() and item.name.endswith(extensions) and item.size < 2_000_000:
                        stream = archive.extractfile(item)
                        if stream is None:
                            raise ValueError('Unreadable archive entry.')
                        payload = stream.read(MAX_FILE + 1)
                        if len(payload) != item.size:
                            raise ValueError('Archive entry size mismatch.')
                        add(item.name, payload)
    except (tarfile.TarError, zipfile.BadZipFile, OSError, EOFError, RuntimeError) as exc:
        raise ValueError('Invalid or unsupported archive; provide tar.gz or ZIP.') from exc
    if not result:
        raise ValueError('No compatible source files found; prediction blocked.')
    return result
