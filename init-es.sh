#!/bin/sh
set -e

echo "⏳ Waiting for Elasticsearch..."
until curl -s http://elasticsearch:9200 >/dev/null 2>&1; do
  sleep 2
done

echo "📊 Creating index 'alexis' with dynamic mapping..."
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
      "message": { "type": "text" },
      "severity": { "type": "keyword" },
      "source_ip": { "type": "ip" },
      "dest_ip": { "type": "ip" },
      "source_port": { "type": "integer" },
      "dest_port": { "type": "integer" },
      "protocol": { "type": "keyword" },
      "event_type": { "type": "keyword" },
      "signature": { "type": "text" },
      "category": { "type": "keyword" },
      "action": { "type": "keyword" }
    }
  }
}'

echo ""
echo "✅ Index 'alexis' created successfully"
