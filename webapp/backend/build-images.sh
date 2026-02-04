#!/bin/bash
set -e

cd "$(dirname "$0")/docker"

echo "Building IDS2 Docker images..."

# Build base image first
echo "Building base Python image..."
docker build -t ids2-python-base:latest -f base/Dockerfile ..

# Build all service images
echo "Building service images..."
docker build -t ids2-runtime:latest -f runtime/Dockerfile ..
docker build -t ids2-fastapi:latest -f fastapi/Dockerfile ..
docker build -t ids2-vector:latest -f vector/Dockerfile .
docker build -t ids2-redis:latest -f redis/Dockerfile .
docker build -t ids2-prometheus:latest -f prometheus/Dockerfile .
docker build -t ids2-grafana:latest -f grafana/Dockerfile .
docker build -t ids2-cadvisor:latest -f cadvisor/Dockerfile .
docker build -t ids2-node-exporter:latest -f node_exporter/Dockerfile .

echo "All images built successfully!"
docker images | grep ids2