FROM python:3.12-slim

WORKDIR /app

# System dependencies for psycopg and sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (separate layer for caching)
COPY app/pyproject.toml ./pyproject.toml
# Create minimal package stub so pip can resolve the package metadata
RUN mkdir -p src/edbank && touch src/edbank/__init__.py
RUN pip install --no-cache-dir .

# Pre-download embedding model into the image (avoids runtime download)
# Model is cached at SENTENCE_TRANSFORMERS_HOME
ENV SENTENCE_TRANSFORMERS_HOME=/app/.model_cache
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-small')"

# Replace stub with real source
COPY app/src ./src
RUN pip install --no-cache-dir --no-deps .

CMD ["uvicorn", "edbank.main:app", "--host", "0.0.0.0", "--port", "8000"]
