FROM redis:7-alpine
COPY install.sh /install.sh
RUN chmod +x /install.sh && /install.sh
CMD ["redis-server", "--appendonly", "yes"]