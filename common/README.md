# Common Modules - Unified Codebase

## 📦 Structure

```
common/
├── ssh/
│   ├── __init__.py
│   └── unified_client.py      # Unified SSH client
├── deploy/
│   ├── __init__.py
│   └── unified_service.py     # Unified deployment
├── docker/
│   └── Dockerfile.template    # Base Dockerfile
├── MIGRATION.md               # Migration guide
└── README.md                  # This file
```

## 🎯 Purpose

Eliminate code duplication across the project by providing unified modules for:
- SSH operations
- Deployment services
- Docker configurations

## 🚀 Quick Start

```python
from common.ssh import UnifiedSSHClient
from common.deploy import UnifiedDeploymentService

# SSH client
ssh = UnifiedSSHClient("192.168.1.100", "pi", key_path="/path/to/key")

# Deployment
deployer = UnifiedDeploymentService(ssh)
deployer.deploy_dockerfile("./Dockerfile", "/opt/ids2")
```

## 📊 Benefits

- **57% code reduction**
- **Single source of truth**
- **Consistent API**
- **Easier maintenance**

## 📖 Documentation

See `MIGRATION.md` for detailed migration guide.
