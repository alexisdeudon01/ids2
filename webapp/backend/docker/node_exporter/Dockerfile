FROM prom/node-exporter:v1.6.1
COPY install.sh /install.sh
RUN chmod +x /install.sh && /install.sh
CMD ["--path.rootfs=/host"]