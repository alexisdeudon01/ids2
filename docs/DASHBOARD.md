# IDS Dashboard

Professional monitoring dashboard for Raspberry Pi-based Intrusion Detection System.

## Architecture

```
Router (Port 1) → TP-Link TL-SG108E → Raspberry Pi (Port 5/eth0)
                                    ↓
                            Port Mirroring Active
                                    ↓
                            Suricata (eth0 promiscuous)
                                    ↓
                            Vector → Elasticsearch
```

## Features

### Backend (FastAPI)

- **Suricata EVE Log Monitoring**: Async tailing of `/var/log/suricata/eve.json` for real-time alerts
- **Elasticsearch Cluster Health**: Monitor cluster status and daily index counts
- **Network Interface Stats**: Real-time traffic monitoring on eth0 (mirrored traffic)
- **Hardware Control**: GPIO LED (Pin 17) flashes on critical alerts (severity 1)
- **Tailscale Integration**: List authorized nodes in the tailnet
- **AI-Powered Healing**: Anthropic Claude integration for automatic error diagnosis and fixes
- **WebSocket Support**: Real-time alert streaming to frontend

### Frontend

- Modern dark theme with glassmorphism effects
- Real-time alert feed via WebSockets
- System health metrics (CPU, Memory, Disk, Temperature)
- Network traffic visualization
- Pipeline status monitoring
- Elasticsearch cluster health dashboard

## Installation

### 1. Run Setup Script

```bash
./scripts/dashboard_setup.sh
```

This will:
- Install system dependencies (Suricata, Docker, etc.)
- Update Suricata rules
- Configure network interface (promiscuous mode)
- Create Python virtual environment
- Install Python dependencies
- Create systemd service

### 2. Configure Environment

Edit `.env` file:

```bash
# Dashboard Configuration
DASHBOARD_PORT=8080
MIRROR_INTERFACE=eth0
LED_PIN=17

# Elasticsearch
ELASTICSEARCH_HOSTS=http://localhost:9200
ELASTICSEARCH_USERNAME=
ELASTICSEARCH_PASSWORD=

# Tailscale
TAILSCALE_TAILNET=your-tailnet
TAILSCALE_API_KEY=your-api-key

# Anthropic AI Healing
ANTHROPIC_API_KEY=your-anthropic-key
```

### 3. Start Dashboard

**Option A: Systemd Service**
```bash
sudo systemctl start ids-dashboard
sudo systemctl enable ids-dashboard
sudo journalctl -u ids-dashboard -f
```

**Option B: Manual**
```bash
source .venv/bin/activate
python -m ids.dashboard.main
```

### 4. Access Dashboard

Open browser: `http://raspberry-pi-ip:8080`

## API Endpoints

### REST API

- `GET /api/alerts/recent?limit=100` - Get recent Suricata alerts
- `GET /api/elasticsearch/health` - Get Elasticsearch cluster health
- `GET /api/network/stats` - Get network interface statistics
- `GET /api/system/health` - Get Raspberry Pi system metrics
- `GET /api/pipeline/status` - Get pipeline component status
- `GET /api/tailscale/nodes` - Get Tailscale tailnet nodes
- `POST /api/ai-healing/diagnose` - Diagnose error with AI

### WebSocket

- `WS /ws/alerts` - Real-time alert stream

## Configuration

### Suricata

Ensure Suricata is configured to:
- Monitor `eth0` interface
- Output EVE JSON logs to `/var/log/suricata/eve.json`
- Run in promiscuous mode

Example `/etc/suricata/suricata.yaml`:
```yaml
af-packet:
  - interface: eth0
    cluster-id: 99
    cluster-type: cluster_flow
    defrag: yes

eve-log:
  enabled: yes
  filetype: regular
  filename: /var/log/suricata/eve.json
  types:
    - alert
```

### Network Interface

The dashboard automatically enables promiscuous mode on eth0:
```bash
sudo ip link set eth0 promisc on
```

### Hardware (LED)

Connect a red LED to GPIO Pin 17:
- Anode → GPIO 17
- Cathode → Ground (via resistor)

The LED will flash when critical alerts (severity 1) are detected.

## AI Healing

The dashboard includes AI-powered error healing using Anthropic Claude. When a pipeline component fails:

1. Error is caught and logged
2. Error context is sent to Claude API
3. AI provides diagnosis and fix commands
4. Suggestions are displayed in the dashboard

Example error handling:
```python
try:
    # Start Suricata
    subprocess.run(["suricata", "-c", "/etc/suricata/suricata.yaml", "-i", "eth0"])
except Exception as e:
    # AI healing kicks in
    healing_response = await ai_healing.handle_pipeline_error("suricata", e)
    # Display healing_response.suggestion and healing_response.commands
```

## Development

### Run in Development Mode

```bash
source .venv/bin/activate
uvicorn ids.dashboard.app:app --reload --host 0.0.0.0 --port 8080
```

### Frontend Development

The dashboard includes a basic HTML/JavaScript frontend. For a full Next.js/Vue.js implementation:

1. Create frontend project in `frontend/` directory
2. Build and output to `frontend/dist/`
3. Dashboard will serve static files from `frontend/dist/`

## Troubleshooting

### Suricata not starting

Check logs:
```bash
sudo journalctl -u suricata -f
```

Common issues:
- Interface not in promiscuous mode
- Insufficient permissions
- Configuration errors

Use AI healing endpoint to get suggestions:
```bash
curl -X POST http://localhost:8080/api/ai-healing/diagnose \
  -H "Content-Type: application/json" \
  -d '{"error_type": "SuricataStartError", "error_message": "Failed to bind to eth0"}'
```

### Elasticsearch not connecting

Verify Elasticsearch is running:
```bash
curl http://localhost:9200/_cluster/health
```

Update `.env` with correct connection details.

### Network stats showing zero

Verify:
1. Port mirroring is active on switch
2. Interface is in promiscuous mode: `ip link show eth0 | grep PROMISC`
3. Traffic is actually being mirrored

## Security Notes

- Dashboard binds to `0.0.0.0` by default (accessible from network)
- In production, use reverse proxy (nginx) with SSL
- Restrict CORS origins in production
- Secure API keys in `.env` file (never store them in the repository)

## License

MIT
