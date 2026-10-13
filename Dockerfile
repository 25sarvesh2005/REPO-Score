# Multi-stage production build for RepoScore API and Worker
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./

# Install python dependencies into a virtual environment
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip setuptools wheel && \
    /opt/venv/bin/pip install .

# -----------------------------------------------------------------------------
# Runtime stage
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runner

WORKDIR /app

# Install runtime utilities: git (for ingestion), curl (for healthchecks), docker.io (CLI for container dispatch)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create unprivileged reposcore user (UID 10001)
RUN groupadd -g 10001 reposcore && \
    useradd -u 10001 -g reposcore -s /bin/bash -m reposcore && \
    mkdir -p /app/repo_snapshots && \
    chown -R reposcore:reposcore /app

# Copy application source code
COPY backend ./backend
COPY frontend ./frontend
COPY reports ./reports
COPY pyproject.toml ./

EXPOSE 8000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/liveness || exit 1

# Default command: start FastAPI API gateway
CMD ["uvicorn", "backend.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
