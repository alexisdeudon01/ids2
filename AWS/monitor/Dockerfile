FROM python:3.11-slim

# Configuration timezone
ENV TZ=Europe/Paris

# Répertoire de travail
WORKDIR /app

# Installer dépendances système
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    jq \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copier requirements
COPY requirements.txt /app/

# Installer dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le script de monitoring
COPY monitor_db_coherence.py /app/
COPY config.json /app/config.json

# Créer un wrapper pour logs continus
RUN echo '#!/bin/sh' > /app/run_monitor.sh && \
    echo 'set -e' >> /app/run_monitor.sh && \
    echo 'echo "🚀 Starting DB Coherence Monitor"' >> /app/run_monitor.sh && \
    echo 'echo "Check interval: ${CHECK_INTERVAL:-10} seconds"' >> /app/run_monitor.sh && \
    echo 'echo "================================"' >> /app/run_monitor.sh && \
    echo 'exec python3 /app/monitor_db_coherence.py --interval ${CHECK_INTERVAL:-10} --config /app/config.json' >> /app/run_monitor.sh && \
    chmod +x /app/run_monitor.sh

# Healthcheck : vérifie que le process tourne
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD pgrep -f monitor_db_coherence.py || exit 1

# Lancer le monitor
CMD ["/app/run_monitor.sh"]
