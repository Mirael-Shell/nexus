FROM python:3.12-slim

WORKDIR /app

# System deps for asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# CPU-only PyTorch index (avoids 2GB+ of CUDA packages)
ENV UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/
COPY data/ ./data/
COPY README.md ./

# Install dependencies (CPU-only torch)
RUN uv pip install --system torch --index-url https://download.pytorch.org/whl/cpu && \
    uv pip install --system -e . --index-strategy unsafe-best-match

EXPOSE 8000

CMD ["sh", "-c", "python -m nexus.db.init_db && uvicorn nexus.main:app --host 0.0.0.0 --port 8000"]
