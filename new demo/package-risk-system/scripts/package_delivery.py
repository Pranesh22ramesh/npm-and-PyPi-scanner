"""Create a portable source + data + trained-artifact ZIP, without dependencies."""
from pathlib import Path
import zipfile

if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    destination=root.parent/'package-risk-system.zip'
    excluded={'.venv','node_modules','__pycache__','.pytest_cache','.runtime','test-results','playwright-report','.git','dist'}
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in root.rglob('*'):
            relative=path.relative_to(root)
            if any(part in excluded for part in relative.parts) or not path.is_file():continue
            if path.suffix in ('.pyc','.tsbuildinfo','.log') or 'sqlite3' in path.name:continue
            archive.write(path,Path(root.name)/relative)
    print(f'{destination} ({destination.stat().st_size/1_000_000:.2f} MB)')
