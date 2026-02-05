"""IDS deployment package."""

__all__ = ("AWSDeployer", "DeployConfig", "DeploymentOrchestrator", "PiDeployer", "SSHClient")

_LAZY_IMPORTS = {
    "AWSDeployer": (".aws_deployer", "AWSDeployer"),
    "DeployConfig": (".config", "DeployConfig"),
    "DeploymentOrchestrator": (".orchestrator", "DeploymentOrchestrator"),
    "PiDeployer": (".pi_deployer", "PiDeployer"),
    "SSHClient": (".ssh_client", "SSHClient"),
}

def __getattr__(name: str):
    if name in _LAZY_IMPORTS:
        module_name, attr_name = _LAZY_IMPORTS[name]
        from importlib import import_module
        module = import_module(module_name, __package__)
        return getattr(module, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
