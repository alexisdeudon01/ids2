FROM timberio/vector:0.34.0-alpine
COPY vector.toml /etc/vector/vector.toml
COPY install.sh /install.sh
RUN chmod +x /install.sh
CMD ["vector", "--config", "/etc/vector/vector.toml"]