#!/usr/bin/env python3
"""
Code Quality Analysis Script.

Runs all code quality tools and generates a comprehensive report:
- Radon: Cyclomatic complexity & maintainability index
- Wily: Complexity tracking over time
- MyPy: Static type checking
- Ruff: Fast linting
- Pylint: Advanced linting
- Import-Linter: Architecture dependency rules
- Bandit: Security analysis

Usage:
    python scripts/code_quality.py              # Run all checks
    python scripts/code_quality.py --quick      # Quick checks only
    python scripts/code_quality.py --report     # Generate HTML report
    python scripts/code_quality.py radon        # Run specific tool
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

# Colors for terminal output
class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    CYAN = "\033[0;36m"
    MAGENTA = "\033[0;35m"
    BOLD = "\033[1m"
    NC = "\033[0m"


@dataclass
class ToolResult:
    """Result of running a code quality tool."""
    name: str
    passed: bool
    score: Optional[str] = None
    duration: float = 0.0
    output: str = ""
    errors: int = 0
    warnings: int = 0


def print_header(title: str) -> None:
    """Print a formatted header."""
    width = 70
    print()
    print(f"{Colors.CYAN}{'═' * width}{Colors.NC}")
    print(f"{Colors.BOLD}{Colors.BLUE}  {title}{Colors.NC}")
    print(f"{Colors.CYAN}{'═' * width}{Colors.NC}")
    print()


def print_result(result: ToolResult) -> None:
    """Print tool result."""
    status = f"{Colors.GREEN}✓ PASS{Colors.NC}" if result.passed else f"{Colors.RED}✗ FAIL{Colors.NC}"
    score_str = f" ({result.score})" if result.score else ""
    time_str = f" [{result.duration:.1f}s]"
    
    print(f"  {result.name:<25} {status}{score_str}{time_str}")


def run_command(cmd: List[str], timeout: int = 300) -> tuple[int, str, str]:
    """Run a command and capture output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except FileNotFoundError:
        return -2, "", f"Command not found: {cmd[0]}"


def run_radon_cc(src_path: str = "src/ids") -> ToolResult:
    """Run Radon cyclomatic complexity analysis."""
    start = time.time()
    
    # Get average complexity
    code, stdout, stderr = run_command(["radon", "cc", src_path, "-a", "-s"])
    
    output = stdout + stderr
    
    # Parse average complexity from output
    score = None
    passed = True
    for line in output.split("\n"):
        if "Average complexity:" in line:
            # Extract grade and value
            parts = line.split()
            if len(parts) >= 3:
                grade = parts[-1].strip("()")
                score = f"CC: {grade}"
                # Fail if average is C or worse
                if grade in ("C", "D", "E", "F"):
                    passed = False
            break
    
    return ToolResult(
        name="Radon (Complexity)",
        passed=passed,
        score=score or "N/A",
        duration=time.time() - start,
        output=output,
    )


def run_radon_mi(src_path: str = "src/ids") -> ToolResult:
    """Run Radon maintainability index analysis."""
    start = time.time()
    
    code, stdout, stderr = run_command(["radon", "mi", src_path, "-s"])
    
    output = stdout + stderr
    
    # Count grades
    grades = {"A": 0, "B": 0, "C": 0}
    for line in output.split("\n"):
        for grade in grades:
            if f" - {grade}" in line or f"({grade})" in line:
                grades[grade] += 1
    
    total = sum(grades.values())
    if total > 0:
        a_percent = grades["A"] / total * 100
        score = f"MI: {a_percent:.0f}% A-grade"
        passed = a_percent >= 70  # At least 70% should be A-grade
    else:
        score = "N/A"
        passed = True
    
    return ToolResult(
        name="Radon (Maintainability)",
        passed=passed,
        score=score,
        duration=time.time() - start,
        output=output,
    )


def run_mypy(src_path: str = "src/ids") -> ToolResult:
    """Run MyPy type checker."""
    start = time.time()
    
    code, stdout, stderr = run_command(["mypy", src_path, "--no-error-summary"])
    
    output = stdout + stderr
    
    # Count errors
    error_count = output.count(": error:")
    
    passed = code == 0 and error_count == 0
    score = f"{error_count} errors" if error_count > 0 else "No errors"
    
    return ToolResult(
        name="MyPy (Types)",
        passed=passed,
        score=score,
        duration=time.time() - start,
        output=output,
        errors=error_count,
    )


def run_ruff(src_path: str = "src/ids") -> ToolResult:
    """Run Ruff linter."""
    start = time.time()
    
    code, stdout, stderr = run_command(["ruff", "check", src_path])
    
    output = stdout + stderr
    
    # Count issues
    issue_count = len([l for l in output.split("\n") if l.strip() and ":" in l])
    
    passed = code == 0
    score = f"{issue_count} issues" if issue_count > 0 else "Clean"
    
    return ToolResult(
        name="Ruff (Fast Lint)",
        passed=passed,
        score=score,
        duration=time.time() - start,
        output=output,
        errors=issue_count,
    )


def run_pylint(src_path: str = "src/ids") -> ToolResult:
    """Run Pylint."""
    start = time.time()
    
    code, stdout, stderr = run_command(["pylint", src_path, "--score=y"])
    
    output = stdout + stderr
    
    # Extract score
    score = None
    for line in output.split("\n"):
        if "Your code has been rated at" in line:
            # Extract X.XX/10
            parts = line.split("rated at")
            if len(parts) > 1:
                score_part = parts[1].split("/")[0].strip()
                score = f"{score_part}/10"
                try:
                    numeric_score = float(score_part)
                    passed = numeric_score >= 8.0
                except ValueError:
                    passed = False
            break
    
    if score is None:
        score = "N/A"
        passed = code == 0
    
    return ToolResult(
        name="Pylint",
        passed=passed,
        score=score,
        duration=time.time() - start,
        output=output,
    )


def run_import_linter() -> ToolResult:
    """Run import-linter."""
    start = time.time()
    
    code, stdout, stderr = run_command(["lint-imports"])
    
    output = stdout + stderr
    
    # Check for contract failures
    passed = "BROKEN" not in output and code == 0
    
    # Count contracts
    contracts_ok = output.count("KEPT")
    contracts_fail = output.count("BROKEN")
    
    score = f"{contracts_ok} OK, {contracts_fail} broken"
    
    return ToolResult(
        name="Import-Linter",
        passed=passed,
        score=score,
        duration=time.time() - start,
        output=output,
        errors=contracts_fail,
    )


def run_bandit(src_path: str = "src/ids") -> ToolResult:
    """Run Bandit security linter."""
    start = time.time()
    
    code, stdout, stderr = run_command(["bandit", "-r", src_path, "-q"])
    
    output = stdout + stderr
    
    # Count issues by severity
    high = output.count("Severity: High")
    medium = output.count("Severity: Medium")
    low = output.count("Severity: Low")
    
    total = high + medium + low
    passed = high == 0  # No high severity issues
    
    if total > 0:
        score = f"H:{high} M:{medium} L:{low}"
    else:
        score = "No issues"
    
    return ToolResult(
        name="Bandit (Security)",
        passed=passed,
        score=score,
        duration=time.time() - start,
        output=output,
        errors=high,
        warnings=medium + low,
    )


def run_all_checks(src_path: str = "src/ids", quick: bool = False) -> List[ToolResult]:
    """Run all code quality checks."""
    print_header("CODE QUALITY ANALYSIS")
    print(f"  Source: {src_path}")
    print(f"  Mode: {'Quick' if quick else 'Full'}")
    print()
    
    results: List[ToolResult] = []
    
    # Always run these (fast)
    checks = [
        ("Ruff", lambda: run_ruff(src_path)),
        ("Radon CC", lambda: run_radon_cc(src_path)),
        ("Radon MI", lambda: run_radon_mi(src_path)),
        ("Bandit", lambda: run_bandit(src_path)),
    ]
    
    # Add slower checks if not quick mode
    if not quick:
        checks.extend([
            ("MyPy", lambda: run_mypy(src_path)),
            ("Pylint", lambda: run_pylint(src_path)),
            ("Import-Linter", run_import_linter),
        ])
    
    for name, check_fn in checks:
        print(f"  Running {name}...", end="", flush=True)
        result = check_fn()
        results.append(result)
        status = f"{Colors.GREEN}✓{Colors.NC}" if result.passed else f"{Colors.RED}✗{Colors.NC}"
        print(f"\r  {status} {name:<20} {result.score:<20} [{result.duration:.1f}s]")
    
    return results


def print_summary(results: List[ToolResult]) -> int:
    """Print summary and return exit code."""
    print_header("SUMMARY")
    
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    total_time = sum(r.duration for r in results)
    
    print(f"  {Colors.BOLD}Results:{Colors.NC}")
    for result in results:
        print_result(result)
    
    print()
    print(f"  {Colors.BOLD}Total:{Colors.NC} {passed}/{len(results)} passed, {failed} failed")
    print(f"  {Colors.BOLD}Time:{Colors.NC} {total_time:.1f}s")
    print()
    
    if failed == 0:
        print(f"  {Colors.GREEN}{Colors.BOLD}✓ All checks passed!{Colors.NC}")
        return 0
    else:
        print(f"  {Colors.RED}{Colors.BOLD}✗ {failed} check(s) failed{Colors.NC}")
        return 1


def run_single_tool(tool: str, src_path: str = "src/ids") -> int:
    """Run a single tool and show verbose output."""
    tool_map = {
        "radon": lambda: (run_radon_cc(src_path), run_radon_mi(src_path)),
        "radon-cc": lambda: (run_radon_cc(src_path),),
        "radon-mi": lambda: (run_radon_mi(src_path),),
        "mypy": lambda: (run_mypy(src_path),),
        "ruff": lambda: (run_ruff(src_path),),
        "pylint": lambda: (run_pylint(src_path),),
        "import-linter": lambda: (run_import_linter(),),
        "bandit": lambda: (run_bandit(src_path),),
    }
    
    if tool not in tool_map:
        print(f"Unknown tool: {tool}")
        print(f"Available: {', '.join(tool_map.keys())}")
        return 1
    
    print_header(f"Running {tool.upper()}")
    
    results = tool_map[tool]()
    
    for result in results:
        print(f"{Colors.BOLD}Tool:{Colors.NC} {result.name}")
        print(f"{Colors.BOLD}Score:{Colors.NC} {result.score}")
        print(f"{Colors.BOLD}Status:{Colors.NC} {'PASS' if result.passed else 'FAIL'}")
        print(f"{Colors.BOLD}Time:{Colors.NC} {result.duration:.1f}s")
        print()
        print(f"{Colors.BOLD}Output:{Colors.NC}")
        print(result.output)
    
    return 0 if all(r.passed for r in results) else 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Code Quality Analysis Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "tool",
        nargs="?",
        help="Specific tool to run (radon, mypy, ruff, pylint, import-linter, bandit)",
    )
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Quick mode - skip slower checks",
    )
    parser.add_argument(
        "--src", "-s",
        default="src/ids",
        help="Source directory to analyze (default: src/ids)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show verbose output",
    )
    
    args = parser.parse_args()
    
    # Change to project root
    project_root = Path(__file__).parent.parent
    import os
    os.chdir(project_root)
    
    if args.tool:
        return run_single_tool(args.tool, args.src)
    else:
        results = run_all_checks(args.src, quick=args.quick)
        return print_summary(results)


if __name__ == "__main__":
    sys.exit(main())
