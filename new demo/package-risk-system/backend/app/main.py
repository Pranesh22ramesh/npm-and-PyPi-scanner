import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .api import train, predict, uploads, scan_npm, scan_pypi, history, model_info
from .db.store import init_db, connect
from .ml.model_manager import manager
from .config import APP_VERSION

@asynccontextmanager
async def lifespan(app):
    init_db()
    with connect() as db:
        db.execute("UPDATE jobs SET status='failed',message='Backend restarted before job completion.' WHERE status IN ('queued','running')")
    try: manager.load()
    except ValueError: pass  # Management remains available; predictions fail closed.
    yield

app = FastAPI(title='Multi-Version Package Risk Analysis',version=APP_VERSION,lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CORS_ORIGINS','http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080').split(','),allow_methods=['GET','POST'],allow_headers=['Content-Type'])
app.add_middleware(TrustedHostMiddleware,allowed_hosts=os.getenv('ALLOWED_HOSTS','localhost,127.0.0.1,backend,testserver').split(','))

@app.exception_handler(ValueError)
async def invalid(request: Request,exc: ValueError):
    return JSONResponse(status_code=422,content={'detail':str(exc)})

@app.get('/api/health')
def health():
    return {'status':'ok','version':APP_VERSION,'prediction_ready':manager.metadata is not None,'model_error':manager.error}

for routes in [train,predict,uploads,scan_npm,scan_pypi,history,model_info]:
    app.include_router(routes.router,prefix='/api')
