# Utiliser une image de base Debian compatible Raspberry Pi (aarch64)
FROM debian:trixie-slim


# Définir les variables d'environnement
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Mettre à jour le système et installer les dépendances de base
RUN apt update && apt upgrade -y && \
    apt install -y --no-install-recommends \
    python3 python3-pip curl wget gnupg2 \
    lsb-release ca-certificates software-properties-common \
    # Dépendances pour Suricata
    libpcap-dev libnet1-dev libyaml-0-2 libjansson4 libcap-ng0 libmagic1 \
    libnfnetlink0 libmnl0 liblua5.3-0 libhiredis0.14 \
    # Dépendances pour Vector (si non incluses dans l'image Vector)
    # Dépendances pour Redis (si non incluses dans l'image Redis)
    # Dépendances pour Prometheus/Grafana (si non incluses dans leurs images)
    && \
    rm -rf /var/lib/apt/lists/*

# --- Installation de Suricata ---
# Suricata sera installé directement dans le conteneur
# Utiliser le dépôt OISF pour la dernière version stable
RUN wget -qO - https://oisf.net/downloads/oisf-release.gpg | apt-key add - && \
    echo "deb http://deb.suricata.io/trixie trixie main" > /etc/apt/sources.list.d/suricata.list && \
    apt update && apt install -y suricata && \
    # Créer le répertoire pour les logs RAM
    mkdir -p /mnt/ram_logs && \
    chmod 777 /mnt/ram_logs # Permettre à Suricata d'écrire

# --- Installation de Vector ---
# Télécharger et installer Vector
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.vector.dev | bash -s -- -y && \
    # Déplacer l'exécutable Vector vers un chemin accessible
    mv /root/.vector/bin/vector /usr/local/bin/vector && \
    # Créer les répertoires pour les buffers de Vector
    mkdir -p /var/lib/vector/buffer /var/lib/vector/redis_buffer /var/lib/vector/opensearch_buffer && \
    chmod -R 777 /var/lib/vector # Permettre à Vector d'écrire

# --- Installation de Redis (client léger ou serveur embarqué) ---
# Pour un conteneur monolithique, nous allons installer un client Redis et l'agent Python
# gérera une instance Redis locale ou se connectera à un service Redis externe si nécessaire.
# Pour simplifier, nous allons installer le serveur Redis directement dans ce conteneur.
RUN apt install -y redis-server && \
    # Configurer Redis pour qu'il ne s'exécute pas en tant que daemon par défaut
    sed -i "s/^daemonize yes/daemonize no/" /etc/redis/redis.conf && \
    # Créer un répertoire pour les données Redis
    mkdir -p /var/lib/redis && \
    chown redis:redis /var/lib/redis && \
    chmod 777 /var/lib/redis # Permettre à Redis d'écrire

# --- Configuration de l'environnement Python ---
WORKDIR /app
COPY webapp/backend/requirements.txt ./requirements.txt
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# Copier le code de l'agent Python et les configurations
COPY webapp/backend/src/ ./src/
COPY webapp/backend/config.yaml ./config.yaml
RUN mkdir -p suricata vector docker/
COPY webapp/db/config/suricata.yaml ./suricata/suricata.yaml
COPY webapp/db/config/vector.toml ./vector/vector.toml
COPY docker/prometheus.yml ./docker/

# Rendre les scripts exécutables (si nécessaire, pour les scripts shell)
# chmod +x deploy/*.sh # Les scripts de déploiement ne seront pas utilisés de la même manière

# Exposer les ports pour Prometheus et Grafana (si ces services sont exécutés localement)
# Dans cette architecture monolithique, l'agent Python exposera les métriques Prometheus
# et Grafana ne sera probablement pas dans le même conteneur.
# Cependant, si nous voulons que l'agent Python expose les métriques pour un Prometheus externe,
# le port 9100 est pertinent.
EXPOSE 9100

# Commande par défaut pour exécuter l'agent Python
# L'agent Python sera le point d'entrée principal et orchestrera Suricata, Vector et Redis.
# Note: Suricata doit être exécuté en systemd sur le host, pas dans Docker
CMD ["python3", "-m", "ids.app.supervisor"]
