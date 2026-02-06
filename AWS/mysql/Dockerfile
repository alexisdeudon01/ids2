FROM mysql:8.0
ENV TZ=Europe/Paris
COPY init.sql /docker-entrypoint-initdb.d/
EXPOSE 3306
