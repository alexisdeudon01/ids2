# IDS Agent - Multi-stage Dockerfile
# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt pyproject.toml ./

# Create virtual environment and install dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip wheel setuptools \
    && pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim as runtime

LABEL maintainer="SIXT R&D Team <dev@sixt.com>"
LABEL description="IDS Agent for Raspberry Pi - Security monitoring with Suricata"
LABEL version="2.0.0"

# Create non-root user for security
RUN groupadd -r ids && useradd -r -g ids ids

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY src/ ./src/
COPY tests/ ./tests/
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

# Default command - run tests
CMD ["python", "-m", "pytest", "tests/", "-v", "--tb=short"]
