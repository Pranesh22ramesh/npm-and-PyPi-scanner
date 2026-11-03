import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from ..ml.model_manager import manager
from ..ml.schema import FEATURES, AGG_FEATURES, AGGREGATIONS
from ..ml.base_feature_extractor import compatibility
from ..config import MAX_RECENT

router = APIRouter()

@router.get('/model/info')
def model_info():
    return {'ready':manager.metadata is not None,'error':manager.error,'metadata':manager.metadata,'extractor':compatibility(),'max_recent_versions':MAX_RECENT}

@router.get('/features/schema')
def schema():
    return {'features':FEATURES,'aggregated_features':AGG_FEATURES,'aggregation_order':AGGREGATIONS,'std_ddof':1}

@router.get('/features/template')
def template():
    return Response(','.join(['package','previous_version','current_version',*FEATURES])+'\n',media_type='text/csv',headers={'Content-Disposition':'attachment; filename=feature_template.csv'})

@router.get('/training/results')
def training_results():
    active = manager.require()
    return {'folds':pd.read_csv(active.folder/'evaluation_results.csv').to_dict('records'),'seeds':pd.read_csv(active.folder/'seed_summary.csv').to_dict('records'),'summary':active.metadata['evaluation_metrics'],'confusion_matrix':active.metadata['seed42_confusion_matrix']}

@router.get('/model/download/{name}')
def download(name: str):
    active = manager.require()
    if name not in ['package_risk_metadata.json','evaluation_results.csv','seed_summary.csv','fold_membership.json']:
        raise HTTPException(404,'Unknown artifact.')
    return FileResponse(active.folder/name,filename=name)
