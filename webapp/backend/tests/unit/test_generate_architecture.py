"""Tests for the architecture generation script."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


def test_generate_architecture_script_runs():
    """Test that the architecture generation script runs without errors."""
    script_path = Path(__file__).parent.parent.parent / "scripts" / "generate_architecture.py"
    assert script_path.exists(), f"Script not found: {script_path}"

    # Run the script
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
    )

    # Check that it succeeded
    assert result.returncode == 0, f"Script failed with:\n{result.stderr}"
    assert "Architecture documentation generated successfully!" in result.stdout


def test_architecture_json_structure():
    """Test that the generated architecture.json has the expected structure."""
    json_path = Path(__file__).parent.parent.parent / "architecture_docs" / "architecture.json"

    # Generate if it doesn't exist
    if not json_path.exists():
        script_path = Path(__file__).parent.parent.parent / "scripts" / "generate_architecture.py"
        subprocess.run([sys.executable, str(script_path)], check=True)

    assert json_path.exists(), f"JSON file not found: {json_path}"

    # Load and validate structure
    with open(json_path) as f:
        data = json.load(f)

    # Check top-level keys
    assert "modules" in data
    assert "classes" in data
    assert "summary" in data

    # Check summary structure
    summary = data["summary"]
    assert "total_modules" in summary
    assert "total_classes" in summary
    assert "total_methods" in summary
    assert "total_functions" in summary

    # Check that we have some data
    assert summary["total_modules"] > 0, "Expected at least one module"
    assert summary["total_classes"] > 0, "Expected at least one class"

    # Check module structure (sample first module)
    if data["modules"]:
        first_module = next(iter(data["modules"].values()))
        assert "file_path" in first_module
        assert "classes" in first_module
        assert "functions" in first_module
        assert "imports" in first_module

    # Check class structure (sample first class)
    if data["classes"]:
        first_class = next(iter(data["classes"].values()))
        assert "name" in first_class
        assert "full_name" in first_class
        assert "module" in first_class
        assert "bases" in first_class
        assert "methods" in first_class


def test_uml_diagrams_generated():
    """Test that UML diagrams are generated."""
    output_dir = Path(__file__).parent.parent.parent / "architecture_docs"

    # Generate if diagrams don't exist
    expected_files = ["classes_ids.png", "packages_ids_packages.png"]
    if not all((output_dir / f).exists() for f in expected_files):
        script_path = Path(__file__).parent.parent.parent / "scripts" / "generate_architecture.py"
        subprocess.run([sys.executable, str(script_path)], check=True)

    # Check that PNG files exist
    for filename in expected_files:
        file_path = output_dir / filename
        assert file_path.exists(), f"UML diagram not found: {file_path}"
        assert file_path.stat().st_size > 0, f"UML diagram is empty: {file_path}"
