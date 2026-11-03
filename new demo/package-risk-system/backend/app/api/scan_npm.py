from fastapi import APIRouter
from ..schemas.requests import ScanRequest
from ..ml.model_manager import manager
from ..ml.feature_extraction import registry_rows
from ..ml.inference import predict_rows
from ..registry.npm_client import fetch_metadata
from ..jobs import submit

router = APIRouter()

@router.get('/registry/npm/versions')
def versions(package: str):
    return fetch_metadata(package)

@router.post('/scan/npm',status_code=202)
def scan(request: ScanRequest):
    manager.require()
    return submit('scan',lambda progress:predict_rows(registry_rows(request.package,'npm',request.count,request.versions,progress),'npm',progress=progress))
