FROM python:3.12-slim-bookworm AS builder
WORKDIR /app
RUN if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|URIs: http://deb.debian.org|URIs: https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources; \
    fi \
    && apt-get update -o Acquire::Retries=3 -o Acquire::http::Timeout=20 -o Acquire::https::Timeout=20 -o Acquire::ForceIPv4=true \
    && apt-get install -y --no-install-recommends gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim-bookworm AS runtime
LABEL maintainer="SIXT R&D Team <dev@sixt.com>" \
      description="IDS Agent for Raspberry Pi" \
      version="2.0.0"

RUN groupadd -r ids && useradd -r -g ids ids && mkdir -p /var/log/ids /var/lib/ids
WORKDIR /app
COPY --from=builder /usr/local /usr/local
COPY --chown=ids:ids src/ ./src/
COPY --chown=ids:ids config.yaml ./

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

RUN chown -R ids:ids /var/log/ids /var/lib/ids
USER ids

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

CMD ["python", "-m", "ids.app.supervisor", "/app/config.yaml"]
