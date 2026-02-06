FROM mysql:8.0

ENV TZ=Europe/Paris
ENV MYSQL_ROOT_PASSWORD=root
ENV MYSQL_DATABASE=ids_db
ENV MYSQL_USER=ids_user
ENV MYSQL_PASSWORD=admin

COPY init.sql /docker-entrypoint-initdb.d/

EXPOSE 3306
