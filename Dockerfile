# Workflow API (FastAPI + uvicorn) for Railway and other container hosts.
# Builds the React app during the image build (Node) and serves web/dist from FastAPI.
# System packages: Poppler (pdf2image) + Tesseract (OCR paths in parsers).
#
# No Vite dev server in production — only static files from `npm run build`.

# --- Frontend: production bundle (runs at image build time, not container start) ---
FROM node:20-bookworm-slim AS web-builder

WORKDIR /app/web

COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
RUN npm run build

# Vite default outDir: ./dist relative to web/ → /app/web/dist

# --- API runtime ---
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

# Baked customer SPA for api.customer_web_static.mount_customer_web_dist_if_present
COPY --from=web-builder /app/web/dist /app/web/dist

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.workflow_app:app", "--host", "0.0.0.0", "--port", "8000"]
