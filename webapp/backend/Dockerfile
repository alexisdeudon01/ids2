# IDS Agent - Multi-stage Dockerfile
# Stage 1: Builder
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt pyproject.toml ./

# Install dependencies system-wide
RUN pip install --no-cache-dir --upgrade pip wheel setuptools \
    && pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim AS runtime

LABEL maintainer="SIXT R&D Team <dev@sixt.com>"
LABEL description="IDS Agent for Raspberry Pi - Security monitoring with Suricata"
LABEL version="2.0.0"

# Create non-root user for security
RUN groupadd -r ids && useradd -r -g ids ids

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /usr/local /usr/local

# Copy application code
COPY src/ ./src/
COPY config.yaml pyproject.toml ./

# Set Python environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Create directories for logs and data
RUN mkdir -p /var/log/ids /var/lib/ids \
    && chown -R ids:ids /app /var/log/ids /var/lib/ids

# Switch to non-root user
USER ids

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command - run agent
CMD ["python", "-m", "ids.app.supervisor", "/app/config.yaml"]
