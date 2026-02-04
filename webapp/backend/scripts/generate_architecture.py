#!/usr/bin/env python3
"""
Architecture Documentation Generator

This script analyzes the Python code in src/ids and generates:
1. A JSON file (architecture_docs/architecture.json) describing classes, methods, base classes, and module organization
2. UML Class and Package diagrams (PNG format) using pyreverse
"""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


class ArchitectureAnalyzer:
    """Analyzes Python code structure using AST."""

    def __init__(self, source_dir: Path):
        self.source_dir = source_dir
        self.architecture = {
            "modules": {},
            "classes": {},
            "summary": {
                "total_modules": 0,
                "total_classes": 0,
                "total_methods": 0,
                "total_functions": 0,
            },
        }

    def analyze(self) -> Dict[str, Any]:
        """Analyze all Python files in the source directory."""
        print(f"Analyzing Python code in {self.source_dir}...")

        python_files = list(self.source_dir.rglob("*.py"))
        print(f"Found {len(python_files)} Python files")

        for file_path in python_files:
            if "__pycache__" in str(file_path):
                continue

            try:
                self._analyze_file(file_path)
            except Exception as e:
                print(f"Warning: Failed to analyze {file_path}: {e}")

        # Update summary
        self.architecture["summary"]["total_modules"] = len(self.architecture["modules"])
        self.architecture["summary"]["total_classes"] = len(self.architecture["classes"])

        return self.architecture

    def _analyze_file(self, file_path: Path) -> None:
        """Analyze a single Python file."""
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read(), filename=str(file_path))
            except SyntaxError as e:
                print(f"Syntax error in {file_path}: {e}")
                return

        # Get relative module path
        relative_path = file_path.relative_to(self.source_dir)
        module_name = str(relative_path.with_suffix("")).replace(os.sep, ".")

        module_info = {
            "file_path": str(relative_path),
            "classes": [],
            "functions": [],
            "imports": [],
            "docstring": ast.get_docstring(tree),
        }

        # Analyze top-level items only
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                class_info = self._analyze_class(node, module_name)
                module_info["classes"].append(class_info["name"])
                self.architecture["classes"][class_info["full_name"]] = class_info

            elif isinstance(node, ast.FunctionDef):
                # Top-level functions only
                func_info = self._analyze_function(node)
                module_info["functions"].append(func_info)
                self.architecture["summary"]["total_functions"] += 1

            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                import_info = self._analyze_import(node)
                if import_info:
                    module_info["imports"].extend(import_info)

        self.architecture["modules"][module_name] = module_info

    def _analyze_class(self, node: ast.ClassDef, module_name: str) -> Dict[str, Any]:
        """Analyze a class definition."""
        full_name = f"{module_name}.{node.name}"

        # Extract base classes
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(f"{self._get_attribute_name(base)}")

        # Extract methods
        methods = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_info = self._analyze_function(item)
                methods.append(method_info)
                self.architecture["summary"]["total_methods"] += 1

        return {
            "name": node.name,
            "full_name": full_name,
            "module": module_name,
            "bases": bases,
            "methods": methods,
            "docstring": ast.get_docstring(node),
            "decorators": [self._get_decorator_name(d) for d in node.decorator_list],
        }

    def _analyze_function(self, node: ast.FunctionDef) -> Dict[str, Any]:
        """Analyze a function or method definition."""
        # Extract arguments
        args = []
        if node.args.args:
            args = [arg.arg for arg in node.args.args]

        # Extract return type
        return_type = None
        if node.returns:
            return_type = ast.unparse(node.returns)

        return {
            "name": node.name,
            "args": args,
            "return_type": return_type,
            "docstring": ast.get_docstring(node),
            "decorators": [self._get_decorator_name(d) for d in node.decorator_list],
            "is_async": isinstance(node, ast.AsyncFunctionDef),
        }

    def _analyze_import(self, node: ast.Import | ast.ImportFrom) -> Optional[List[str]]:
        """Analyze import statements."""
        imports = []
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}" if module else alias.name)
        return imports

    def _get_attribute_name(self, node: ast.Attribute) -> str:
        """Get full attribute name from AST node."""
        if isinstance(node.value, ast.Name):
            return f"{node.value.id}.{node.attr}"
        elif isinstance(node.value, ast.Attribute):
            return f"{self._get_attribute_name(node.value)}.{node.attr}"
        return node.attr

    def _get_decorator_name(self, node: ast.expr) -> str:
        """Get decorator name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self._get_attribute_name(node)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return node.func.id
            elif isinstance(node.func, ast.Attribute):
                return self._get_attribute_name(node.func)
        return str(node)


def generate_uml_diagrams(source_dir: Path, output_dir: Path) -> None:
    """Generate UML diagrams using pyreverse."""
    print("Generating UML diagrams with pyreverse...")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate class diagram
    try:
        print("Generating class diagram...")
        subprocess.run(
            [
                "pyreverse",
                "-o",
                "png",
                "-p",
                "ids",
                "--output-directory",
                str(output_dir),
                str(source_dir),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        print("✓ Class diagram generated: classes_ids.png")
    except subprocess.CalledProcessError as e:
        print(f"Error generating class diagram: {e.stderr}")
        raise

    # Generate package diagram
    try:
        print("Generating package diagram...")
        subprocess.run(
            [
                "pyreverse",
                "-o",
                "png",
                "-p",
                "ids_packages",
                "--output-directory",
                str(output_dir),
                "--only-classnames",
                str(source_dir),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        print("✓ Package diagram generated: packages_ids_packages.png")
    except subprocess.CalledProcessError as e:
        print(f"Error generating package diagram: {e.stderr}")
        raise


def main() -> int:
    """Main entry point."""
    # Determine paths
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    source_dir = repo_root / "src" / "ids"
    output_dir = repo_root / "architecture_docs"

    print("=" * 70)
    print("Architecture Documentation Generator")
    print("=" * 70)
    print(f"Source directory: {source_dir}")
    print(f"Output directory: {output_dir}")
    print()

    # Check if source directory exists
    if not source_dir.exists():
        print(f"Error: Source directory not found: {source_dir}")
        return 1

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Analyze code structure
    analyzer = ArchitectureAnalyzer(source_dir)
    architecture = analyzer.analyze()

    # Save JSON output
    json_output = output_dir / "architecture.json"
    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(architecture, f, indent=2, ensure_ascii=False)

    print()
    print("=" * 70)
    print("Analysis Summary:")
    print("=" * 70)
    print(f"Total modules: {architecture['summary']['total_modules']}")
    print(f"Total classes: {architecture['summary']['total_classes']}")
    print(f"Total methods: {architecture['summary']['total_methods']}")
    print(f"Total functions: {architecture['summary']['total_functions']}")
    print(f"JSON output: {json_output}")
    print()

    # Generate UML diagrams
    try:
        generate_uml_diagrams(source_dir, output_dir)
    except Exception as e:
        print(f"Warning: UML diagram generation failed: {e}")
        print("This is expected if pylint/pyreverse is not installed.")
        print("The JSON architecture file was still generated successfully.")
        return 0

    print()
    print("=" * 70)
    print("✓ Architecture documentation generated successfully!")
    print("=" * 70)
    print(f"Output directory: {output_dir}")
    print(f"- architecture.json")
    print(f"- classes_ids.png")
    print(f"- packages_ids_packages.png")

    return 0


if __name__ == "__main__":
    sys.exit(main())
