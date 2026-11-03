from fastapi import APIRouter, File, Form, UploadFile
from ..config import MAX_UPLOAD
from ..ml.schema import read_csv
from ..ml.inference import predict_rows
from ..ml.model_manager import manager
from ..ml.feature_extraction import archive_rows
from ..jobs import submit

router = APIRouter()

def bounded_read(file):
    data = file.file.read(MAX_UPLOAD+1)
    if len(data)>MAX_UPLOAD:
        raise ValueError('Uploaded file exceeds the configured size limit.')
    return data

@router.post('/predict/csv')
def predict_csv(file: UploadFile = File(...)):
    return {'results':predict_rows(read_csv(bounded_read(file)))}

@router.post('/scan/archive',status_code=202)
def scan_archive(package: str = Form(...), registry: str = Form(...), versions: str = Form(...), files: list[UploadFile] = File(...)):
    manager.require()
    if registry not in ('npm','pypi') or not package.strip() or len(package)>214:
        raise ValueError('Provide a package name and registry npm or pypi.')
    if not 2<=len(files)<=10:
        raise ValueError('Provide 2–10 release archives in chronological order.')
    labels = [v.strip() for v in versions.split(',')]
    if len(labels) != len(files):
        raise ValueError('Provide one comma-separated version name per archive.')
    archives = [bounded_read(file) for file in files]
    return submit('scan',lambda progress:predict_rows(archive_rows(package,registry,archives,labels,progress),registry,progress=progress))
