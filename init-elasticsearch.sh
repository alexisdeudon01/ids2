#!/bin/bash
set -e

echo "Waiting for Elasticsearch..."
until curl -s http://elasticsearch:9200 >/dev/null; do
  sleep 2
done

echo "Creating index 'alexis' with dynamic mapping..."
curl -X PUT "http://elasticsearch:9200/alexis" -H 'Content-Type: application/json' -d'
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0
  },
  "mappings": {
    "dynamic": true,
    "properties": {
      "@timestamp": { "type": "date" },
      "message": { "type": "text" }
    }
  }
}'

echo -e "\n✅ Index 'alexis' created"
