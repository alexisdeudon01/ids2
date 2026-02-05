FROM prom/prometheus:v2.47.0
COPY prometheus.yml /etc/prometheus/prometheus.yml
COPY install.sh /install.sh
RUN chmod +x /install.sh && /install.sh
CMD ["--config.file=/etc/prometheus/prometheus.yml", "--storage.tsdb.path=/prometheus", "--web.enable-lifecycle"]