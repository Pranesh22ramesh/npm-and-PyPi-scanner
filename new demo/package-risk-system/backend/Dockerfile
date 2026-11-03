FROM python:3.13-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY backend/requirements-lock.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY backend /app/backend
COPY scripts /app/scripts
COPY dataset /app/dataset
COPY models /app/models
RUN useradd --create-home appuser && mkdir -p /app/scans && chown -R appuser:appuser /app
USER appuser
WORKDIR /app/backend
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
