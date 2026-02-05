# Backend2 - Complete IDS Dashboard

## 📋 Overview

Complete minimal backend for IDS Dashboard with database, frontend, and all necessary endpoints.

## 🎯 Implemented Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/system/health` | GET | CPU, RAM, Disk, Temperature |
| `/api/db/health` | GET | Database connectivity check |
| `/api/alerts/recent` | GET | Recent security alerts |
| `/api/alerts/add` | POST | Add new alert (testing) |
| `/api/network/stats` | GET | Network interface statistics |
| `/api/pipeline/status` | GET | Pipeline components status |

## 📁 Structure

```
backend2/
├── main.py                 # FastAPI app
├── start.sh               # Startup script
├── Dockerfile             # Docker image
├── docker-compose.yml     # Docker orchestration
├── requirements.txt       # Dependencies
├── MAPPING.md            # Architecture diagrams
├── api/
│   ├── system_health.py  # System metrics
│   ├── db_health.py      # DB health
│   ├── alerts.py         # Alerts management
│   ├── network.py        # Network stats
│   └── pipeline.py       # Pipeline status
├── models/
│   └── schemas.py        # Pydantic models
├── db/
│   ├── database.py       # SQLite wrapper
│   └── ids.db           # SQLite database (auto-created)
└── frontend/
    └── (React app copied from webapp/frontend)
```

## 🚀 Quick Start

### Option 1: Direct Run
```bash
cd backend2
./start.sh
```

### Option 2: Docker
```bash
cd backend2
docker-compose up -d
```

### Option 3: Manual
```bash
cd backend2
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## 🌐 Access

- **API:** http://localhost:8000
- **Docs:** http://localhost:8000/docs
- **Frontend:** http://localhost:8000 (after building)

## 🗄️ Database

SQLite database automatically created at `db/ids.db` with tables:
- **alerts** - Security alerts
- **system_metrics** - System health history

## 📊 API Examples

### System Health
```bash
curl http://localhost:8000/api/system/health
```

### Add Test Alert
```bash
curl -X POST "http://localhost:8000/api/alerts/add?severity=1&signature=Test+Alert&src_ip=192.168.1.100"
```

### Network Stats
```bash
curl http://localhost:8000/api/network/stats?interface=eth0
```

## 🔧 Frontend Build

```bash
cd frontend
npm install
npm run build
```

Frontend will be served at http://localhost:8000

## 📦 Dependencies

- **FastAPI** - Web framework
- **Uvicorn** - ASGI server
- **psutil** - System metrics
- **SQLite** - Database (built-in Python)

## 🐳 Docker

Build and run with Docker:
```bash
docker-compose up --build
```

## 🔄 Development

Hot reload enabled by default:
```bash
uvicorn main:app --reload
```

## 📖 Documentation

- `MAPPING.md` - Architecture and data flow diagrams
- `/docs` - Interactive API documentation (Swagger)
- `/redoc` - Alternative API documentation

## ✅ Features

- ✅ Real system metrics (CPU, RAM, Disk, Temp)
- ✅ SQLite database with health checks
- ✅ Network statistics
- ✅ Pipeline status monitoring
- ✅ Alerts management
- ✅ CORS enabled
- ✅ Docker support
- ✅ Frontend serving
- ✅ Auto-reload development mode

## 🎯 Differences from Full Backend

| Feature | Full Backend | Backend2 |
|---------|--------------|----------|
| Database | PostgreSQL/SQLAlchemy | SQLite |
| Endpoints | 30+ | 6 |
| WebSocket | ✅ | ❌ |
| AI Healing | ✅ | ❌ |
| Lines of Code | ~5000 | ~300 |
