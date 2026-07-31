# Backend image. Build: docker compose up --build, or Render picks this up directly.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# deps first so code edits reuse this cached layer
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

# bake the embedding model into the image; without this the first ticket
# after every cold start downloads ~100MB before it can be classified
RUN uv run python -c "from fastembed import TextEmbedding; TextEmbedding()"

ENV PORT=8000
# one worker, pinned on purpose: the rate limiter and cancel set are in-process
CMD uv run uvicorn api:app --host 0.0.0.0 --port ${PORT} --workers 1
