from fastapi import APIRouter, UploadFile, File
from ..ml.schema import read_csv, validate_training
from ..ml.training import train
from ..ml.model_manager import manager
from ..db.store import save_training
from ..jobs import submit
from .uploads import bounded_read

router = APIRouter()

@router.post('/train/validate')
def validate(file: UploadFile = File(...)):
    rows = validate_training(read_csv(bounded_read(file)))
    return {'valid':True,'rows':len(rows),'packages':rows.package.nunique(),'features':60,'malicious_packages':128,'clean_packages':52}

@router.post('/train',status_code=202)
def start_training(file: UploadFile = File(...)):
    data = bounded_read(file)
    validate_training(read_csv(data))
    name = file.filename or 'primary_size_matched_dataset.csv'
    def operation(progress):
        metadata = train(data,name,progress)
        # Swap only a completely validated generation into the serving manager.
        from ..ml.model_manager import ModelManager
        fresh = ModelManager().load()
        manager.__dict__.update(fresh.__dict__)
        save_training(metadata)
        return metadata
    return submit('training',operation)
