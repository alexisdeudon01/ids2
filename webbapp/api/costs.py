"""AWS cost estimates API."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from ids.deploy.aws_deployer import AWSDeployer
from ids.deploy.config import DeployConfig

router = APIRouter(prefix="/api/aws", tags=["aws"])


def _load_config() -> dict:
    config_path = Path(__file__).resolve().parents[2] / "config.json"
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


@router.get("/costs")
def get_costs():
    config_data = _load_config()
    config = DeployConfig(
        elastic_password=config_data.get("elastic_password", ""),
        aws_region=config_data.get("aws_region", "eu-west-1"),
        aws_access_key_id=config_data.get("aws_access_key_id", ""),
        aws_secret_access_key=config_data.get("aws_secret_access_key", ""),
        aws_ami_id=config_data.get("aws_ami_id", ""),
    )

    aws = AWSDeployer(
        config.aws_region,
        config.elastic_password,
        log_callback=lambda _msg: None,
        aws_access_key_id=config.aws_access_key_id,
        aws_secret_access_key=config.aws_secret_access_key,
        ami_id=config.aws_ami_id,
    )

    try:
        instances = aws.list_tagged_instances_all_regions()
    except Exception as exc:
        return {"error": str(exc), "instances": []}

    results = []
    total_hourly = 0.0
    total_monthly = 0.0
    for inst in instances:
        costs = aws.estimate_costs(inst.get("instance_type"), inst.get("region"))
        total_hourly += costs["total_hourly_usd"]
        total_monthly += costs["total_monthly_usd"]
        results.append({**inst, **costs})

    return {
        "instances": results,
        "total_hourly_usd": total_hourly,
        "total_monthly_usd": total_monthly,
    }
