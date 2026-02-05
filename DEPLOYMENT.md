# IDS2 Deployment

## Quick Start

### 1. Install Dependencies

```bash
pip install boto3 elasticsearch paramiko requests
```

### 2. Run Orchestrator GUI

```bash
python3 orchestrator.py
```

## Configuration

### Default Values
- **AWS Region**: `eu-west-1`
- **Pi Host**: `192.168.178.66`
- **Pi User**: `pi`
- **Pi Password**: `pi`
- **Sudo Password**: `pi`
- **Remote Directory**: `/opt/ids2`
- **Mirror Interface**: `eth0` (network interface for port mirroring)

### Required
- **Elastic Password**: Must be provided (no default)

## Mirror Interface

The **Mirror Interface** is the network interface on your Raspberry Pi that receives mirrored/SPAN traffic from your network switch. This is typically:
- `eth0` for wired Ethernet
- `wlan0` for WiFi (not recommended for IDS)

Configure your network switch to mirror traffic to the port where your Pi is connected.

## Architecture

```
ids/deploy/
├── config.py          # Configuration dataclass
├── ssh_client.py      # SSH/SFTP operations
├── aws_deployer.py    # AWS ELK deployment
├── pi_deployer.py     # Raspberry Pi setup
├── orchestrator.py    # Deployment orchestration
└── gui.py             # Tkinter GUI
```

## Features

- ✅ Deploy ELK stack on AWS EC2
- ✅ Configure Elasticsearch mappings & retention
- ✅ Install Suricata IDS on Raspberry Pi
- ✅ Deploy webapp & log streamer
- ✅ Docker management (install/remove)
- ✅ Full reset capability
