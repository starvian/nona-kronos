# Multi-stage Dockerfile for Kronos FastAPI Service
# Optimized for production deployment with minimal image size

# ============================================================================
# Stage 1: Builder - Install dependencies and prepare environment
# ============================================================================
FROM python:3.10-slim as builder

# Set environment variables for build
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies required for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements files
WORKDIR /tmp
COPY services/kronos_fastapi/requirements.txt ./
COPY gitSource/requirements.txt ./core-requirements.txt

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r core-requirements.txt && \
    pip install -r requirements.txt

# ============================================================================
# Stage 2: Runtime - Minimal production image
# ============================================================================
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    KRONOS_MODEL_PATH=/models \
    KRONOS_LOG_LEVEL=INFO

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r kronos && \
    useradd -r -g kronos -u 1000 -m -s /bin/bash kronos

# Create necessary directories
RUN mkdir -p /app /models /logs && \
    chown -R kronos:kronos /app /models /logs

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy application code
# Note: We copy from gitSource root to maintain import structure
COPY --chown=kronos:kronos gitSource/model ./model
COPY --chown=kronos:kronos services/kronos_fastapi ./services/kronos_fastapi

# Switch to non-root user
USER kronos

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/v1/healthz || exit 1

# Default command
CMD ["uvicorn", "services.kronos_fastapi.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
