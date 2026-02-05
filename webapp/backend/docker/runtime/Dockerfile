FROM ids2-python-base:latest
LABEL maintainer="SIXT R&D Team <dev@sixt.com>" \
      description="IDS Agent for Raspberry Pi" \
      version="2.0.0"

RUN groupadd -r ids && useradd -r -g ids ids && mkdir -p /var/log/ids /var/lib/ids
COPY --chown=ids:ids src/ ./src/
COPY --chown=ids:ids config.yaml ./

RUN chown -R ids:ids /var/log/ids /var/lib/ids
USER ids

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

CMD ["python", "-m", "ids.app.supervisor", "/app/config.yaml"]