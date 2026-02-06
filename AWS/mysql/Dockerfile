FROM mysql:8.0

# Configuration timezone
ENV TZ=Europe/Paris

# Configuration MySQL avec credentials par défaut
ENV MYSQL_ROOT_PASSWORD=admin
ENV MYSQL_DATABASE=ids_db
ENV MYSQL_USER=ids_user
ENV MYSQL_PASSWORD=admin

# Copier les scripts d'initialisation
# Les fichiers dans /docker-entrypoint-initdb.d/ sont exécutés dans l'ordre alphabétique
COPY init.sql /docker-entrypoint-initdb.d/00_init.sql
COPY ../datas/*.sql /docker-entrypoint-initdb.d/ 2>/dev/null || true

# Volume pour persistence des données
VOLUME ["/var/lib/mysql"]

EXPOSE 3306

# Healthcheck
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
  CMD mysqladmin ping -h localhost -u root -p$MYSQL_ROOT_PASSWORD || exit 1
