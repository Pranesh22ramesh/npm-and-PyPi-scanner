from fastapi import APIRouter, HTTPException, Query
from ..db import store
from ..jobs import get_job

router = APIRouter()

@router.get('/scans')
def scans(limit: int = Query(100,ge=1,le=500), offset: int = Query(0,ge=0)):
    return store.scans(limit,offset)

@router.get('/scans/{identifier}')
def scan(identifier: str):
    result = store.scan(identifier)
    if result is None: raise HTTPException(404,'Scan not found.')
    return result

@router.get('/dashboard')
def dashboard():
    return store.dashboard()

@router.get('/jobs/{identifier}')
def job(identifier: str):
    result = get_job(identifier)
    if result is None: raise HTTPException(404,'Job not found.')
    return result
