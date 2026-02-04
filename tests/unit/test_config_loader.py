from pathlib import Path

import pytest
import yaml

from ids.config.loader import ConfigManager
from ids.domain.exceptions import ErreurConfiguration


def _write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data))


def test_secret_merge_includes_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    secret_path = tmp_path / "secret.json"

    _write_yaml(
        config_path,
        {
            "aws": {"opensearch_endpoint": "https://search.example.com"},
        },
    )
    secret_path.write_text('{"aws": {"access_key_id": "abc", "secret_access_key": "xyz"}}')

    manager = ConfigManager(str(config_path), secret_path=str(secret_path))
    assert manager.obtenir("aws.access_key_id") == "abc"
    assert manager.obtenir("aws.secret_access_key") == "xyz"


def test_missing_secret_raises_with_endpoint(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    _write_yaml(
        config_path,
        {
            "aws": {"opensearch_endpoint": "https://search.example.com"},
        },
    )

    with pytest.raises(ErreurConfiguration):
        ConfigManager(str(config_path), secret_path=str(tmp_path / "absent.json"))


def test_missing_secret_ok_without_endpoint(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    _write_yaml(config_path, {"aws": {"opensearch_endpoint": ""}})

    manager = ConfigManager(str(config_path), secret_path=str(tmp_path / "absent.json"))
    assert manager.obtenir("aws.opensearch_endpoint") == ""


def test_instance_profile_skips_secret_requirement(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    _write_yaml(
        config_path,
        {
            "aws": {
                "opensearch_endpoint": "https://search.example.com",
                "credentials": {"use_instance_profile": True},
            }
        },
    )

    manager = ConfigManager(str(config_path), secret_path=str(tmp_path / "absent.json"))
    assert manager.obtenir("aws.credentials.use_instance_profile") is True
