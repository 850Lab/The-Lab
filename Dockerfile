# Workflow API (FastAPI + uvicorn) for Railway and other container hosts.
# Builds the React app during the image build (Node) and serves web/dist from FastAPI.
# System packages: Poppler (pdf2image) + Tesseract (OCR paths in parsers).
#
# No Vite dev server in production — only static files from `npm run build`.

# --- Frontend: production bundle (runs at image build time, not container start) ---
FROM node:20-bookworm-slim AS web-builder

WORKDIR /app/web

# Optional build-time vars for split API/static hosting (same-origin Docker deploy can omit).
ARG VITE_WORKFLOW_API_URL=
ARG VITE_PUBLIC_DEMO_SECRET=
ARG VITE_WAITLIST_MODE=
ENV VITE_WORKFLOW_API_URL=$VITE_WORKFLOW_API_URL
ENV VITE_PUBLIC_DEMO_SECRET=$VITE_PUBLIC_DEMO_SECRET
ENV VITE_WAITLIST_MODE=$VITE_WAITLIST_MODE

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

# Railway (and many hosts) inject PORT; default 8000 for local `docker run`.
EXPOSE 8000

CMD ["/bin/sh", "-c", "exec python -m uvicorn api.workflow_app:app --host 0.0.0.0 --port ${PORT:-8000}"]
