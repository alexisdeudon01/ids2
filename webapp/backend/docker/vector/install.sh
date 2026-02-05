#!/bin/sh
mkdir -p /var/lib/vector/{buffer,redis_buffer,opensearch_buffer}
chmod 777 /var/lib/vector/*
echo "Vector installation completed"