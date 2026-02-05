#!/bin/bash
set -e

echo "🚀 Starting IDS Backend2..."

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Initialize database
echo "🗄️  Initializing database..."
python3 -c "from db import db; print('Database initialized')"

# Start server
echo "✅ Starting FastAPI server on http://localhost:8000"
echo "📖 API docs: http://localhost:8000/docs"
uvicorn main:app --reload --host 0.0.0.0 --port 8000
