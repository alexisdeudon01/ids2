#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Building base Python image..."
docker build -t ids2-python-base:latest docker/base/

echo "Building runtime image..."
docker build -t ids2-runtime:latest docker/runtime/

echo "Building API image..."
docker build -t ids2-api:latest docker/api/

echo "Building test image..."
docker build -t ids2-test:latest docker/test/

echo "All images built successfully!"
docker images | grep ids2