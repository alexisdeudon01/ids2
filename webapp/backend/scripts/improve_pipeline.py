#!/usr/bin/env python3
"""
Continuous Architecture Improvement Pipeline

This script runs a complete cycle of:
1. Generate UML diagrams
2. Analyze architecture quality
3. Suggest improvements
4. Track progress

Usage:
    python scripts/improve_pipeline.py [--iterations N]
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict


def run_command(cmd: list, cwd: Path = None) -> tuple:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def generate_uml(project_root: Path) -> bool:
    """Generate UML diagrams."""
    print("\n" + "=" * 70)
    print("🎨 STEP 1: Generating UML Diagrams")
    print("=" * 70)

    cmd = ["python", "scripts/generate_uml.py"]
    returncode, stdout, stderr = run_command(cmd, cwd=project_root)

    if returncode == 0:
        print("✅ UML diagrams generated successfully")
        return True
    else:
        print("❌ Failed to generate UML diagrams")
        print(f"Error: {stderr}")
        return False


def analyze_architecture(project_root: Path) -> Dict:
    """Analyze architecture and return metrics."""
    print("\n" + "=" * 70)
    print("🔍 STEP 2: Analyzing Architecture")
    print("=" * 70)

    cmd = ["python", "scripts/analyze_architecture.py"]
    returncode, stdout, stderr = run_command(cmd, cwd=project_root)

    # Extract metrics from stdout (basic parsing)
    metrics = {
        "health_score": 0.0,
        "errors": 0,
        "warnings": 0,
        "timestamp": datetime.now().isoformat(),
    }

    # Parse output
    for line in stdout.split("\n"):
        if "Health score:" in line:
            try:
                score = float(line.split(":")[1].split("/")[0].strip())
                metrics["health_score"] = score
            except (ValueError, IndexError):
                pass
        elif "Errors:" in line:
            try:
                errors = int(line.split(":")[1].strip())
                metrics["errors"] = errors
            except (ValueError, IndexError):
                pass
        elif "Warnings:" in line:
            try:
                warnings = int(line.split(":")[1].strip())
                metrics["warnings"] = warnings
            except (ValueError, IndexError):
                pass

    print(f"✅ Analysis complete")
    print(f"   Health Score: {metrics['health_score']:.1f}/100")
    print(f"   Errors: {metrics['errors']}")
    print(f"   Warnings: {metrics['warnings']}")

    return metrics


def save_metrics(metrics: Dict, project_root: Path):
    """Save metrics to history file."""
    metrics_file = project_root / "docs" / "uml" / "metrics_history.json"

    history = []
    if metrics_file.exists():
        try:
            with open(metrics_file, "r") as f:
                history = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    history.append(metrics)

    with open(metrics_file, "w") as f:
        json.dump(history, f, indent=2)

    print(f"✅ Metrics saved to {metrics_file}")


def check_improvement(project_root: Path) -> bool:
    """Check if there was improvement since last run."""
    metrics_file = project_root / "docs" / "uml" / "metrics_history.json"

    if not metrics_file.exists():
        print("ℹ️  No previous metrics to compare")
        return True

    try:
        with open(metrics_file, "r") as f:
            history = json.load(f)

        if len(history) < 2:
            return True

        prev = history[-2]
        curr = history[-1]

        print("\n" + "=" * 70)
        print("📊 PROGRESS COMPARISON")
        print("=" * 70)

        score_diff = curr["health_score"] - prev["health_score"]
        errors_diff = curr["errors"] - prev["errors"]
        warnings_diff = curr["warnings"] - prev["warnings"]

        print(
            f"\nHealth Score: {prev['health_score']:.1f} → {curr['health_score']:.1f} ({score_diff:+.1f})"
        )
        print(f"Errors:       {prev['errors']} → {curr['errors']} ({errors_diff:+d})")
        print(f"Warnings:     {prev['warnings']} → {curr['warnings']} ({warnings_diff:+d})")

        improved = score_diff > 0 or (score_diff == 0 and errors_diff <= 0 and warnings_diff <= 0)

        if improved:
            print("\n✅ Architecture improved!")
        elif score_diff == 0 and errors_diff == 0 and warnings_diff == 0:
            print("\n➡️  No change in architecture")
        else:
            print("\n⚠️  Architecture quality decreased")

        return improved

    except (json.JSONDecodeError, OSError, KeyError) as e:
        print(f"⚠️  Could not compare metrics: {e}")
        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run continuous architecture improvement pipeline")
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of improvement iterations to run (default: 1)",
    )
    parser.add_argument(
        "--target-score",
        type=float,
        default=95.0,
        help="Target health score to achieve (default: 95.0)",
    )

    args = parser.parse_args()

    # Determine project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    print("=" * 70)
    print("🚀 ARCHITECTURE IMPROVEMENT PIPELINE")
    print("=" * 70)
    print(f"Project: {project_root.name}")
    print(f"Iterations: {args.iterations}")
    print(f"Target score: {args.target_score}")

    success = True

    for iteration in range(1, args.iterations + 1):
        print(f"\n{'=' * 70}")
        print(f"🔄 ITERATION {iteration}/{args.iterations}")
        print(f"{'=' * 70}")

        # Step 1: Generate UML
        if not generate_uml(project_root):
            print("❌ Failed to generate UML")
            success = False
            break

        # Step 2: Analyze architecture
        metrics = analyze_architecture(project_root)

        # Step 3: Save metrics
        save_metrics(metrics, project_root)

        # Step 4: Check improvement
        if iteration > 1:
            check_improvement(project_root)

        # Check if target reached
        if metrics["health_score"] >= args.target_score:
            print(
                f"\n🎉 Target score reached! ({metrics['health_score']:.1f} >= {args.target_score})"
            )
            break

        # Wait for manual improvements between iterations
        if iteration < args.iterations:
            print(f"\n⏸️  Iteration {iteration} complete.")
            print("   Review the analysis output and make improvements to the code.")
            print(f"   Current score: {metrics['health_score']:.1f} / Target: {args.target_score}")
            print(f"   {args.iterations - iteration} iteration(s) remaining")

    # Final summary
    print("\n" + "=" * 70)
    print("📋 PIPELINE SUMMARY")
    print("=" * 70)

    if success:
        print("✅ Pipeline completed successfully")

        # Show final metrics
        metrics_file = project_root / "docs" / "uml" / "metrics_history.json"
        if metrics_file.exists():
            with open(metrics_file, "r") as f:
                history = json.load(f)

            if len(history) > 0:
                final = history[-1]
                print(f"\n📊 Final Metrics:")
                print(f"   Health Score: {final['health_score']:.1f}/100")
                print(f"   Errors: {final['errors']}")
                print(f"   Warnings: {final['warnings']}")

                if len(history) > 1:
                    first = history[0]
                    score_improvement = final["health_score"] - first["health_score"]
                    print(f"\n📈 Total Improvement:")
                    print(f"   Score: {score_improvement:+.1f} points")

        print(f"\n📁 Outputs:")
        print(f"   UML diagrams: docs/uml/*.png")
        print(f"   Metrics history: docs/uml/metrics_history.json")
        print(f"   Documentation: docs/uml/README.md")

        return 0
    else:
        print("❌ Pipeline failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
