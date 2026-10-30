FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy FASTEMBED_CACHE_PATH=/app/.fastembed_cache PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 app
WORKDIR /app/api

COPY api/pyproject.toml api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY api/ ./
COPY data/ /app/data/
COPY evals/ /app/evals/
# Bake the embedding model into the image so a cold start never downloads it.
RUN uv sync --frozen --no-dev \
 && DATABASE_URL=postgresql://unused uv run --no-sync python -c \
    "from clearline.rag import embedder; embedder()" \
 && chown -R app:app /app

USER app
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "clearline.main:app", "--host", "0.0.0.0", "--port", "8000"]
