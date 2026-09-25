# Backend-only image for demo/backend (FastAPI + NER/linking pipeline).
# Built for Hugging Face Spaces (Docker SDK), which expects the app to
# listen on port 7860. See README.md's Deployment section for why this
# runs here and not on Vercel (which hosts demo/frontend instead).
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
EXPOSE 7860

CMD ["uvicorn", "demo.backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
