# Backend2 - Minimal API for Frontend

## 📋 Overview

Minimal FastAPI backend matching **only** the endpoints used by the frontend (`App.tsx`).

## 🎯 Implemented Endpoints

| Endpoint | Method | Description | Frontend Usage |
|----------|--------|-------------|----------------|
| `/api/system/health` | GET | CPU, RAM, Disk metrics | Stats card "Pi CPU Load" |
| `/api/db/health` | GET | Database status | Pipeline Health section |

## 📁 Structure

```
backend2/
├── main.py                 # FastAPI app
├── requirements.txt        # Dependencies
├── MAPPING.md             # Architecture diagrams
├── models/
│   └── schemas.py         # Data models
└── api/
    ├── system_health.py   # System metrics
    └── db_health.py       # DB health
```

## 🚀 Quick Start

```bash
cd backend2

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 🔗 API Documentation

Once running, visit:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## 📊 Response Examples

### System Health
```json
{
  "cpu_percent": 45.2,
  "memory_percent": 62.8,
  "disk_percent": 38.5,
  "temperature": 52.3
}
```

### Database Health
```json
{
  "status": "ok"
}
```

## ⚠️ Limitations

- **No WebSocket:** Real-time alerts not implemented
- **No AI Healing:** Diagnostic endpoints missing
- **No Configuration:** Config pages not needed
- **Hardcoded Frontend Data:** Traffic and alerts are static in frontend

## 🔄 Differences from Full Backend

| Feature | Full Backend | Backend2 |
|---------|--------------|----------|
| Endpoints | 30+ | 2 |
| WebSocket | ✅ | ❌ |
| AI Healing | ✅ | ❌ |
| Configuration | ✅ | ❌ |
| Database | SQLAlchemy | Mock |
| Size | ~5000 lines | ~100 lines |

## 📖 See Also

- `MAPPING.md` - Architecture diagrams and data flow
- Frontend: `../frontend/src/App.tsx`
