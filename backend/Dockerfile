# =============================================================================
# Cisco Security Platform — Multi-stage Backend Dockerfile
# Stage 1: builder (installs deps)
# Stage 2: development (hot-reload)
# Stage 3: production (hardened, minimal image)
# =============================================================================

# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.12-bookworm AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libssl-dev \
    libffi-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install --no-compile -r requirements.txt


# ── Stage 2: development ──────────────────────────────────────────────────────
FROM python:3.12-bookworm AS development

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    ENVIRONMENT=development

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY . .

RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]


# ── Stage 3: production ───────────────────────────────────────────────────────
FROM python:3.12-bookworm AS production

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    ENVIRONMENT=production

# Security: minimal runtime deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

COPY --from=builder /install /usr/local
COPY --chown=appuser:appgroup . .

# Create non-root user with no shell
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --no-create-home --shell /bin/false appuser && \
    chown -R appuser:appgroup /app && \
    chmod -R 750 /app

USER appuser

# Healthcheck for Docker orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

EXPOSE 8000

# Production: gunicorn with uvicorn workers for process management
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "120", \
     "--keep-alive", "5", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]

LABEL \
    maintainer="Platform Security Team" \
    org.opencontainers.image.title="Cisco Security Platform API" \
    org.opencontainers.image.version="2.0.0" \
    org.opencontainers.image.description="Enterprise cybersecurity compliance platform" \
    org.opencontainers.image.vendor="Cisco Security Platform"
