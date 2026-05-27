# Dockerfile for the lawagent FastAPI service (apps/api).
#
# Stage 1 installs deps with uv into a venv inside /app/.venv.
# Stage 2 is a slim runtime that only carries the venv + source.
#
# Local build/run:
#   docker build -t lawagent-api .
#   docker run --rm -p 8000:8000 --env-file .env lawagent-api

# ---- builder -----------------------------------------------------------
FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install runtime deps first so the layer caches across source changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# Now install the project itself.
COPY apps ./apps
COPY packages ./packages
COPY config ./config
RUN uv sync --frozen --no-dev

# ---- runtime -----------------------------------------------------------
FROM python:3.11-slim AS runtime

RUN groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app

COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app
EXPOSE 8000

# App Runner / ECS health check hits /health on this port.
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
