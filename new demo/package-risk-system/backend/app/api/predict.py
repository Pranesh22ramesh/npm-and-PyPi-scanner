import pandas as pd
from fastapi import APIRouter
from ..schemas.requests import PredictionRequest
from ..ml.inference import predict_rows

router = APIRouter()

def request_rows(request: PredictionRequest):
    return pd.DataFrame([{'package':request.package,'previous_version':pair.previous_version,'current_version':pair.current_version,**pair.features} for pair in request.version_pairs])

@router.post('/predict/features')
def predict(request: PredictionRequest):
    return predict_rows(request_rows(request))[0]
