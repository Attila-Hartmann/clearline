FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_CACHE=1 FASTEMBED_CACHE_PATH=/app/.fastembed_cache
WORKDIR /app/api
COPY api/pyproject.toml api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY api/ ./
RUN uv sync --frozen --no-dev
# Bake the embedding model into the image so a cold start never downloads it.
RUN DATABASE_URL=postgresql://unused .venv/bin/python -c "from clearline.rag import embedder; embedder()"

# Runtime: no build tools, no uv, files owned by a non-root user without a chown layer duplicating them.
FROM python:3.12-slim
ENV PATH=/app/api/.venv/bin:$PATH FASTEMBED_CACHE_PATH=/app/.fastembed_cache PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 app
WORKDIR /app/api
COPY --from=build --chown=app:app /app /app
COPY --chown=app:app data/ /app/data/
COPY --chown=app:app evals/ /app/evals/
USER app
EXPOSE 8000
CMD ["uvicorn", "clearline.main:app", "--host", "0.0.0.0", "--port", "8000"]
