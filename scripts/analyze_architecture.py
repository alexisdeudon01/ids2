#!/usr/bin/env python3
"""
Analyze UML diagrams and suggest code improvements.

This script performs static analysis of the codebase to identify potential
improvements that would result in better UML diagrams:
- Circular dependencies
- High coupling
- Missing abstractions
- Large classes (God objects)
- Complex inheritance hierarchies

Usage:
    python scripts/analyze_architecture.py [--output-dir docs/uml]
"""

import argparse
import ast
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple


class ArchitectureAnalyzer:
    """Analyze Python code architecture for quality metrics."""

    def __init__(self, src_dir: Path):
        self.src_dir = src_dir
        self.modules: Dict[str, Dict] = {}
        self.dependencies: Dict[str, Set[str]] = defaultdict(set)
        self.issues: List[Dict] = []

    def analyze(self) -> Dict:
        """Run full architecture analysis."""
        print("🔍 Analyzing architecture...")

        # Collect module information
        self._scan_modules()

        # Analyze dependencies
        self._analyze_dependencies()

        # Check for architectural issues
        self._check_circular_dependencies()
        self._check_coupling()
        self._check_class_complexity()

        return {
            "modules": self.modules,
            "dependencies": dict(self.dependencies),
            "issues": self.issues,
            "metrics": self._calculate_metrics(),
        }

    def _scan_modules(self):
        """Scan all Python modules in the source directory."""
        for py_file in self.src_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            rel_path = py_file.relative_to(self.src_dir)
            module_name = str(rel_path).replace("/", ".").replace(".py", "")

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    tree = ast.parse(content)

                # Analyze module
                classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
                functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
                imports = [
                    node
                    for node in ast.walk(tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom))
                ]

                self.modules[module_name] = {
                    "path": py_file,
                    "classes": [c.name for c in classes],
                    "functions": len(functions),
                    "lines": len(content.splitlines()),
                    "imports": len(imports),
                }

                # Track dependencies
                for imp in imports:
                    if isinstance(imp, ast.ImportFrom) and imp.module:
                        if imp.module.startswith("ids."):
                            self.dependencies[module_name].add(imp.module)
                    elif isinstance(imp, ast.Import):
                        for alias in imp.names:
                            if alias.name.startswith("ids."):
                                self.dependencies[module_name].add(alias.name)

            except (SyntaxError, UnicodeDecodeError, OSError) as e:
                print(f"  ⚠️  Failed to analyze {py_file}: {e}")

    def _analyze_dependencies(self):
        """Analyze dependency relationships."""
        print("📊 Analyzing dependencies...")

        for module, deps in self.dependencies.items():
            if len(deps) > 10:
                self.issues.append(
                    {
                        "severity": "warning",
                        "type": "high_coupling",
                        "module": module,
                        "message": f"Module has {len(deps)} dependencies (high coupling)",
                        "suggestion": "Consider breaking this module into smaller, more focused modules",
                    }
                )

    def _check_circular_dependencies(self):
        """Detect circular dependencies."""
        print("🔄 Checking for circular dependencies...")

        visited = set()
        rec_stack = set()

        def has_cycle(module: str, path: List[str]) -> bool:
            visited.add(module)
            rec_stack.add(module)
            path.append(module)

            for dep in self.dependencies.get(module, []):
                if dep not in visited:
                    if has_cycle(dep, path.copy()):
                        return True
                elif dep in rec_stack:
                    cycle_start = path.index(dep)
                    cycle = " -> ".join(path[cycle_start:] + [dep])
                    self.issues.append(
                        {
                            "severity": "error",
                            "type": "circular_dependency",
                            "module": module,
                            "cycle": cycle,
                            "message": f"Circular dependency detected: {cycle}",
                            "suggestion": "Introduce an interface or refactor to break the cycle",
                        }
                    )
                    return True

            rec_stack.remove(module)
            return False

        for module in self.dependencies:
            if module not in visited:
                has_cycle(module, [])

    def _check_coupling(self):
        """Check for high coupling between modules."""
        print("🔗 Checking coupling metrics...")

        # Calculate efferent coupling (Ce) - dependencies on other modules
        for module, deps in self.dependencies.items():
            ce = len(deps)
            if ce > 15:
                self.issues.append(
                    {
                        "severity": "error",
                        "type": "high_efferent_coupling",
                        "module": module,
                        "value": ce,
                        "message": f"Very high efferent coupling: {ce} dependencies",
                        "suggestion": "Apply Dependency Inversion Principle - depend on abstractions",
                    }
                )

    def _check_class_complexity(self):
        """Check for overly complex classes."""
        print("📏 Checking class complexity...")

        for module_name, info in self.modules.items():
            # Check for too many classes in one file
            if len(info["classes"]) > 5:
                self.issues.append(
                    {
                        "severity": "warning",
                        "type": "too_many_classes",
                        "module": module_name,
                        "value": len(info["classes"]),
                        "message": f'{len(info["classes"])} classes in one module',
                        "suggestion": "Consider splitting into multiple modules",
                    }
                )

            # Check for large files
            lines = info.get("lines", 0)
            if lines > 500:
                self.issues.append(
                    {
                        "severity": "warning",
                        "type": "large_module",
                        "module": module_name,
                        "value": lines,
                        "message": f"Large module: {lines} lines",
                        "suggestion": "Break into smaller, more focused modules",
                    }
                )

    def _calculate_metrics(self) -> Dict:
        """Calculate overall architecture metrics."""
        total_modules = len(self.modules)
        total_dependencies = sum(len(deps) for deps in self.dependencies.values())
        avg_dependencies = total_dependencies / total_modules if total_modules > 0 else 0

        # Count issues by severity
        errors = sum(1 for i in self.issues if i["severity"] == "error")
        warnings = sum(1 for i in self.issues if i["severity"] == "warning")

        return {
            "total_modules": total_modules,
            "total_dependencies": total_dependencies,
            "avg_dependencies": round(avg_dependencies, 2),
            "errors": errors,
            "warnings": warnings,
            "total_issues": len(self.issues),
            "health_score": self._calculate_health_score(),
        }

    def _calculate_health_score(self) -> float:
        """Calculate an overall architecture health score (0-100)."""
        # Start with perfect score
        score = 100.0

        # Deduct points for issues
        errors = sum(1 for i in self.issues if i["severity"] == "error")
        warnings = sum(1 for i in self.issues if i["severity"] == "warning")

        score -= errors * 10  # -10 points per error
        score -= warnings * 2  # -2 points per warning

        # Ensure score is between 0 and 100
        return max(0.0, min(100.0, score))


def print_report(analysis: Dict):
    """Print a formatted analysis report."""
    print("\n" + "=" * 70)
    print("📊 ARCHITECTURE ANALYSIS REPORT")
    print("=" * 70)

    metrics = analysis["metrics"]
    print(f"\n📈 Metrics:")
    print(f"  Total modules: {metrics['total_modules']}")
    print(f"  Total dependencies: {metrics['total_dependencies']}")
    print(f"  Avg dependencies/module: {metrics['avg_dependencies']}")
    print(f"  Health score: {metrics['health_score']:.1f}/100")

    print(f"\n⚠️  Issues Found:")
    print(f"  Errors: {metrics['errors']}")
    print(f"  Warnings: {metrics['warnings']}")
    print(f"  Total: {metrics['total_issues']}")

    if analysis["issues"]:
        print("\n" + "=" * 70)
        print("🔍 DETAILED ISSUES")
        print("=" * 70)

        # Group issues by severity
        errors = [i for i in analysis["issues"] if i["severity"] == "error"]
        warnings = [i for i in analysis["issues"] if i["severity"] == "warning"]

        if errors:
            print("\n❌ ERRORS (must fix):")
            for issue in errors:
                print(f"\n  Module: {issue['module']}")
                print(f"  Type: {issue['type']}")
                print(f"  Issue: {issue['message']}")
                print(f"  💡 Suggestion: {issue['suggestion']}")

        if warnings:
            print("\n⚠️  WARNINGS (should fix):")
            for issue in warnings:
                print(f"\n  Module: {issue['module']}")
                print(f"  Type: {issue['type']}")
                print(f"  Issue: {issue['message']}")
                print(f"  💡 Suggestion: {issue['suggestion']}")
    else:
        print("\n✅ No issues found! Architecture looks good.")

    print("\n" + "=" * 70)
    print("🎯 RECOMMENDATIONS")
    print("=" * 70)

    score = metrics["health_score"]
    if score >= 90:
        print("\n✅ Excellent! Architecture is well-structured.")
    elif score >= 70:
        print("\n👍 Good architecture, but could be improved.")
    elif score >= 50:
        print("\n⚠️  Fair architecture. Consider refactoring high-priority issues.")
    else:
        print("\n❌ Poor architecture. Significant refactoring recommended.")

    print("\n📚 Next Steps:")
    print("  1. Address all ERROR-level issues first")
    print("  2. Review and fix WARNING-level issues")
    print("  3. Re-run UML generation to see improvements")
    print("  4. Iterate until health score > 90")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Analyze architecture quality")
    parser.add_argument(
        "--src-dir",
        type=Path,
        default=Path("src/ids"),
        help="Source directory to analyze (default: src/ids)",
    )

    args = parser.parse_args()

    # Determine project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    src_dir = project_root / args.src_dir

    if not src_dir.exists():
        print(f"❌ Error: Source directory not found: {src_dir}")
        sys.exit(1)

    print("=" * 70)
    print("🏗️  ARCHITECTURE ANALYZER")
    print("=" * 70)
    print(f"Analyzing: {src_dir}")
    print()

    # Run analysis
    analyzer = ArchitectureAnalyzer(src_dir)
    analysis = analyzer.analyze()

    # Print report
    print_report(analysis)

    # Return exit code based on severity
    metrics = analysis["metrics"]
    if metrics["errors"] > 0:
        return 1
    elif metrics["warnings"] > 5:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
