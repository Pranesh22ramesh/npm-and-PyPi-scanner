import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv('DATA_DIR', str(ROOT / 'scans')))
MODEL_DIR = Path(os.getenv('MODEL_DIR', str(ROOT / 'models')))
MAX_UPLOAD = int(os.getenv('MAX_UPLOAD_BYTES', 25_000_000))
MAX_EXTRACTED = int(os.getenv('MAX_EXTRACTED_BYTES', 80_000_000))
MAX_FILES = int(os.getenv('MAX_ARCHIVE_FILES', 10000))
MAX_FILE = int(os.getenv('MAX_FILE_BYTES', 8_000_000))
EXTRACT_TIMEOUT = int(os.getenv('EXTRACT_TIMEOUT_SECONDS', 60))
MAX_RECENT = int(os.getenv('MAX_RECENT_VERSIONS', 10))
APP_VERSION = '1.0.0'
