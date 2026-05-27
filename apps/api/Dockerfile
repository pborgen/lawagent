# syntax=docker/dockerfile:1.7
#
# lawagent API image
#
# Stage 1 ("builder") installs Python deps with uv into /app/.venv.
# Stage 2 ("runtime") is a slim image that only carries the venv,
# the app source, and the config — no uv, no build toolchain.
#
# Build for local dev (host-native arch):
#   docker build -t lawagent-api -f apps/api/Dockerfile .
#
# Build for Fargate Graviton (arm64):
#   docker buildx build --platform linux/arm64 -t lawagent-api \
#     -f apps/api/Dockerfile --load .
#
# `apps/efile` is intentionally excluded from runtime behavior here:
# the Playwright Python package is installed (cheap), but the browser
# binary is NOT downloaded (`playwright install chromium` is skipped),
# so any attempt to actually drive a browser in the cloud will fail
# loudly. efile stays on the laptop.

ARG PYTHON_VERSION=3.12

# ---------- builder ----------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.5-python${PYTHON_VERSION}-bookworm-slim AS builder

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Resolve and install dependencies first — this layer is cached as long
# as pyproject.toml and uv.lock are unchanged.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev --no-group local

# Now install the project itself (editable). Workspace source is needed
# at runtime because `uv sync` writes .pth files pointing back into
# /app/apps and /app/packages.
COPY apps/ ./apps/
COPY packages/ ./packages/
COPY config/ ./config/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-group local

# ---------- runtime ----------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

# ca-certificates is required for outbound TLS to Bedrock / S3.
# psycopg[binary] bundles libpq, so we do not need libpq5 from apt.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app
COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    HOME=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

USER app
EXPOSE 8000

# Liveness probe; matches the /health route in api.main. Kept inside the
# image so docker-compose, ECS, and bare `docker run` all use it.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys;\
sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health',timeout=3).status==200 else 1)" \
    || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
