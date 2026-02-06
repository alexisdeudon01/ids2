# AWS Module - Refactored

## 📋 Overview

Refactored AWS module with SSH deployment and MySQL service.

## 🏗️ Architecture

```
AWS/
├── app/
│   ├── ssh_manager.py       # SSH connection & file transfer
│   ├── pi_deployment.py     # Pi deployment service
│   └── mysql_service.py     # MySQL wrapper
├── deploy_to_pi.py          # Deployment script
├── example_usage.py         # Usage examples
└── requirements.txt         # Dependencies
```

## 🚀 Features

### 1. SSH Manager
- ✅ Verbose logging
- ✅ File upload (single/directory)
- ✅ Remote command execution
- ✅ Context manager support

### 2. Pi Deployment Service
- ✅ Deploy Dockerfile to Pi
- ✅ Build Docker image remotely
- ✅ Upload directories
- ✅ Verbose deployment logs

### 3. MySQL Service
- ✅ Query execution
- ✅ Update/Insert operations
- ✅ Context manager support
- ✅ Error handling

## 📦 Installation

```bash
cd AWS
pip install -r requirements.txt
```

## 🔧 Usage

### Deploy to Pi

```python
from app.ssh_manager import SSHManager
from app.pi_deployment import PiDeploymentService

ssh = SSHManager("192.168.1.100", "pi", "/path/to/key")
deployer = PiDeploymentService(ssh)

# Deploy Dockerfile
deployer.deploy_dockerfile("./Dockerfile", "/opt/ids2")
```

### MySQL Queries

```python
from app.mysql_service import MySQLService

with MySQLService("localhost", "user", "pass", "db") as db:
    # SELECT
    results = db.execute_query("SELECT * FROM alerts")
    
    # INSERT
    db.execute_update(
        "INSERT INTO alerts (severity) VALUES (%s)", 
        (1,)
    )
```

## 🎯 Deployment Script

```bash
# Edit configuration in deploy_to_pi.py
python deploy_to_pi.py
```

## 📊 Verbose Logging

All operations log verbosely:
```
2024-01-01 12:00:00 - INFO - Connecting to pi@192.168.1.100:22...
2024-01-01 12:00:01 - INFO - SSH connection established
2024-01-01 12:00:01 - INFO - Executing: mkdir -p /opt/ids2
2024-01-01 12:00:02 - INFO - Uploading Dockerfile -> /opt/ids2/Dockerfile
2024-01-01 12:00:03 - INFO - Building Docker image...
```

## 🔐 Configuration

Edit these variables:
- `PI_HOST` - Raspberry Pi IP
- `PI_USER` - SSH user
- `PI_KEY` - SSH key path
- MySQL credentials

## ✅ Benefits

- **Verbose Logging** - Track every operation
- **Context Managers** - Auto cleanup
- **Error Handling** - Proper exception management
- **Reusable** - Modular services
