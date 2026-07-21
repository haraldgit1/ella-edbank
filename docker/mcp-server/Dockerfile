FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies (separate layer for caching)
COPY mcp-server/pyproject.toml ./pyproject.toml
# Create minimal package stub so pip can resolve the package metadata
RUN mkdir -p src/edbank_mcp && touch src/edbank_mcp/__init__.py
RUN pip install --no-cache-dir .

# Replace stub with real source
COPY mcp-server/src ./src
RUN pip install --no-cache-dir --no-deps .

CMD ["python", "-m", "edbank_mcp.server"]
