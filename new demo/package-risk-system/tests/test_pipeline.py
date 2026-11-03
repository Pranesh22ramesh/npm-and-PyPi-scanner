import io
import json
import shutil
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from app.ml.schema import FEATURES, AGG_FEATURES, read_csv, validate_training, validate_features
from app.ml.aggregation import aggregate_packages
from app.ml.evaluation import fuse, make_models
from app.ml.model_manager import ModelManager, MISMATCH
from app.ml.inference import predict_rows
from app.api.predict import request_rows
from app.schemas.requests import PredictionRequest

ROOT=Path(__file__).resolve().parents[1]

def test_real_dataset_schema_and_metadata_exclusion(dataset):
    assert dataset.shape==(615,69)
    assert len(FEATURES)==60 and len(AGG_FEATURES)==240
    assert dataset.columns[:60].tolist()==FEATURES
    assert not set(['package','ecosystem','label','origin','gap','consecutive','size_ok','version_before','version_after']) & set(FEATURES)
    altered=dataset.copy()
    for name in ['ecosystem','origin','gap','consecutive','size_ok']:
        altered[name]='ignored-metadata'
    pd.testing.assert_frame_equal(aggregate_packages(dataset),aggregate_packages(altered))

@pytest.mark.parametrize('change',['missing','nan','inf','text','label','count','conflicting'])
def test_invalid_training(dataset,change):
    data=dataset.copy()
    if change=='missing': data=data.drop(columns=FEATURES[-1])
    elif change=='count': data=data.iloc[:-1]
    elif change=='label': data.loc[0,'label']=2
    elif change=='conflicting':
        idx=data.groupby('package').filter(lambda g:len(g)>1).index[0]
        data.loc[idx,'label']=1-data.loc[idx,'label']
    elif change=='text':
        data[FEATURES[0]]=data[FEATURES[0]].astype(object)
        data.loc[0,FEATURES[0]]='bad'
    else: data.loc[0,FEATURES[0]]=np.nan if change=='nan' else np.inf
    with pytest.raises(ValueError): validate_training(data)

def test_duplicate_csv_columns():
    with pytest.raises(ValueError,match='Duplicate'):read_csv(b'package,package\na,b\n')

def test_aggregation_order_statistics_and_single_row():
    rows=pd.DataFrame([{'package':p,**{f:value+i for i,f in enumerate(FEATURES)}} for p,value in [('a',1),('a',3),('b',8)]])
    profiles=aggregate_packages(rows)
    assert profiles.shape==(2,240)
    assert profiles.columns.tolist()==AGG_FEATURES
    assert profiles.loc['a','add_net_http__mean']==2
    assert profiles.loc['a','add_net_http__max']==3
    assert profiles.loc['a','add_net_http__median']==2
    assert profiles.loc['a','add_net_http__std']==pytest.approx(np.sqrt(2))
    assert np.all(profiles.loc['b'].iloc[180:].to_numpy()==0)
    assert profiles.loc['b','add_net_http__mean']==8

def test_mandatory_real_dataset_training_web_aggregation_identical(dataset):
    training=aggregate_packages(dataset)
    # Check every package, retaining string version identifiers.
    for name,rows in dataset.groupby('package'):
        request=PredictionRequest(package=name,version_pairs=[{'previous_version':row.version_before,'current_version':row.version_after,'features':{f:float(row[f]) for f in FEATURES}} for _,row in rows.iterrows()])
        inference=aggregate_packages(request_rows(request))
        np.testing.assert_array_equal(training.loc[[name]].to_numpy(),inference.to_numpy())

def test_parameters_and_fusion():
    rf,xgb=make_models(77)
    assert rf.n_estimators==300 and rf.class_weight=='balanced' and rf.random_state==77
    assert xgb.n_estimators==250 and xgb.max_depth==3 and xgb.min_child_weight==3
    np.testing.assert_allclose(fuse([.8,.2],[.4,.6]),[.6,.4])

def test_artifact_loading_and_evaluation_disjointness():
    manager=ModelManager().load().require()
    assert manager.rf.n_features_in_==manager.xgb.n_features_in_==240
    folds=pd.read_csv(manager.folder/'evaluation_results.csv')
    assert len(folds)==25 and set(folds.seed)=={7,42,77,123,2026}
    memberships=json.loads((manager.folder/'fold_membership.json').read_text())
    for seed in [7,42,77,123,2026]:
        test=[]
        for fold in [v for v in memberships if v['seed']==seed]:
            assert not set(fold['train']) & set(fold['test'])
            test.extend(fold['test'])
        assert len(test)==len(set(test))==180
    for metric in ['accuracy','precision','recall','f1','roc_auc']:
        assert folds[metric].mean()==pytest.approx(manager.metadata['evaluation_metrics'][metric]['mean'])
    assert sum(map(sum,manager.metadata['seed42_confusion_matrix']))==180

def test_mismatch_blocks_model(tmp_path):
    model=ModelManager().load().require()
    meta=dict(model.metadata);meta['aggregated_feature_names']=list(reversed(AGG_FEATURES))
    (tmp_path/'package_risk_metadata.json').write_text(json.dumps(meta))
    broken=ModelManager(tmp_path)
    with pytest.raises(ValueError,match='Model/schema mismatch'): broken.load()
    with pytest.raises(ValueError,match='Model/schema mismatch'): broken.require()

def test_artifact_tampering_blocks_load(tmp_path):
    model=ModelManager().load().require()
    for name in ['package_risk_metadata.json','package_risk_random_forest.joblib','package_risk_xgboost.joblib']:
        shutil.copy2(model.folder/name,tmp_path/name)
    with (tmp_path/'package_risk_xgboost.joblib').open('ab') as f:f.write(b'tamper')
    with pytest.raises(ValueError,match='Model/schema mismatch'):ModelManager(tmp_path).load()

@pytest.mark.parametrize('score,prediction',[(.4999,'clean-risk'),(.5,'malicious-risk'),(.8,'malicious-risk')])
def test_fixed_threshold(dataset,score,prediction):
    manager=ModelManager().load().require()
    class Constant:
        def predict_proba(self,x):return np.array([[1-score,score]]*len(x))
    manager.rf=manager.xgb=Constant()
    rows=dataset.iloc[:1].rename(columns={'version_before':'previous_version','version_after':'current_version'})
    assert predict_rows(rows,model=manager,persist=False)[0]['prediction']==prediction

def test_api_prediction_and_history(client,dataset):
    row=dataset.iloc[0]
    body={'package':'api-regression-fixture','version_pairs':[{'previous_version':row.version_before,'current_version':row.version_after,'features':{f:float(row[f]) for f in FEATURES}}]}
    response=client.post('/api/predict/features',json=body)
    assert response.status_code==200,response.text
    result=response.json()
    assert result['model_score']==pytest.approx((result['random_forest_score']+result['xgboost_score'])/2)
    assert result['version_pairs_used']==1
    assert client.get('/api/scans/'+result['id']).json()==result
    assert client.get('/api/dashboard').json()['total']==1
    body['version_pairs'][0]['features'].pop(FEATURES[0])
    assert client.post('/api/predict/features',json=body).status_code==422

def test_csv_prediction_grouping_and_no_model(client,dataset,monkeypatch):
    rows=dataset.iloc[:8].rename(columns={'version_before':'previous_version','version_after':'current_version'})
    csv=rows.to_csv(index=False).encode()
    response=client.post('/api/predict/csv',files={'file':('rows.csv',csv,'text/csv')})
    assert response.status_code==200,response.text
    assert len(response.json()['results'])==rows.package.nunique()
    from app.ml.model_manager import manager
    monkeypatch.setattr(manager,'metadata',None)
    assert client.post('/api/predict/csv',files={'file':('rows.csv',csv,'text/csv')}).status_code==422

def test_training_validation_and_endpoints(client,dataset):
    response=client.post('/api/train/validate',files={'file':('data.csv',dataset.to_csv(index=False).encode(),'text/csv')})
    assert response.status_code==200 and response.json()['packages']==180
    for path in ['/api/health','/api/model/info','/api/features/schema','/api/training/results','/api/model/download/seed_summary.csv']:
        assert client.get(path).status_code==200
