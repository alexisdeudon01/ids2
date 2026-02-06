#!/bin/sh
set -e

echo "⏳ Waiting for Kibana..."
until curl -s http://kibana:5601/api/status >/dev/null 2>&1; do
  sleep 5
done

echo "📊 Creating index pattern for 'alexis'..."
curl -X POST "http://kibana:5601/api/saved_objects/index-pattern/alexis" \
  -H 'kbn-xsrf: true' \
  -H 'Content-Type: application/json' \
  -d '{
    "attributes": {
      "title": "alexis*",
      "timeFieldName": "@timestamp"
    }
  }'

echo ""
echo "✅ Kibana dashboard configured successfully"
