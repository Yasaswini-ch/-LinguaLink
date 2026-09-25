# Backend-only image for demo/backend (FastAPI + NER/linking pipeline).
# Portable across container platforms (Render, Fly.io, Google Cloud Run, a
# plain VM, ...) — see README.md's Deployment section for why this runs here
# and not on Vercel (which hosts demo/frontend instead).
FROM python:3.11-slim

WORKDIR /app

# CPU-only torch wheel — the default PyPI wheel bundles CUDA and is far
# larger than this CPU-only deployment needs.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements-backend.txt .
RUN pip install --no-cache-dir -r requirements-backend.txt

COPY src/ ./src/
COPY configs/ ./configs/
COPY demo/backend/ ./demo/backend/

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

# Most platforms (Cloud Run, Render, Railway, Fly.io) inject a $PORT env var
# the container must listen on; 8080 is only the fallback for a plain
# `docker run` with no PORT set.
CMD ["sh", "-c", "uvicorn demo.backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
