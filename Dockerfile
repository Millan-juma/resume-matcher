FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=200 PIP_RETRIES=10 PIP_NO_CACHE_DIR=1

# Tesseract for OCR. For more languages add packages here, e.g. tesseract-ocr-swa tesseract-ocr-fra
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr \
 && rm -rf /var/lib/apt/lists/*

RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

COPY . .
RUN useradd -m appuser && chown -R appuser /app
USER appuser

# Download the embedding model at build time so startup is fast and works offline
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
