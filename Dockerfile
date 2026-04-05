# Workflow API (FastAPI + uvicorn) for Railway and other container hosts.
# Serves /api/*; optional web/dist is omitted here when the SPA is hosted separately (e.g. Vercel).
# System packages: Poppler (pdf2image) + Tesseract (OCR paths in parsers).

FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "api.workflow_app:app", "--host", "0.0.0.0", "--port", "8000"]
