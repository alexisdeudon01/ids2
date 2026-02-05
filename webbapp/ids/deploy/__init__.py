"""IDS deployment package."""

# Lazy imports to avoid dependency errors
__all__ = [
    "AWSDeployer",
    "DeployConfig",
    "DeploymentOrchestrator",
    "PiDeployer",
    "SSHClient",
]


def __getattr__(name: str):
    if name == "AWSDeployer":
        from .aws_deployer import AWSDeployer
        return AWSDeployer
    elif name == "DeployConfig":
        from .config import DeployConfig
        return DeployConfig
    elif name == "DeploymentOrchestrator":
        from .orchestrator import DeploymentOrchestrator
        return DeploymentOrchestrator
    elif name == "PiDeployer":
        from .pi_deployer import PiDeployer
        return PiDeployer
    elif name == "SSHClient":
        from .ssh_client import SSHClient
        return SSHClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
