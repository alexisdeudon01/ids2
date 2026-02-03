#!/usr/bin/env python3
"""
Generate UML diagrams for the IDS project using pyreverse.

This script generates comprehensive UML diagrams including:
- Class diagrams for each module
- Package diagrams showing module dependencies
- Full system architecture diagram

Usage:
    python scripts/generate_uml.py [--output-dir docs/uml]
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


def run_command(cmd: List[str], cwd: Optional[Path] = None) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def generate_module_diagrams(src_dir: Path, output_dir: Path) -> dict:
    """Generate UML diagrams for each module in the project."""
    results = {}
    
    # Main modules to generate diagrams for
    modules = [
        'src/ids',  # Full package diagram
        'src/ids/domain',
        'src/ids/interfaces',
        'src/ids/composants',
        'src/ids/infrastructure',
        'src/ids/suricata',
        'src/ids/app',
        'src/ids/config',
        'src/ids/deploy',
    ]
    
    for module in modules:
        module_path = src_dir / module
        if not module_path.exists():
            print(f"⚠️  Skipping {module} (not found)")
            continue
            
        module_name = module.replace('/', '_').replace('src_', '')
        print(f"📊 Generating diagrams for {module}...")
        
        # Generate class diagram
        cmd_classes = [
            'pyreverse',
            '-o', 'png',
            '-p', module_name,
            '--output-directory', str(output_dir),
            str(module_path)
        ]
        
        returncode, stdout, stderr = run_command(cmd_classes, cwd=src_dir)
        
        if returncode == 0:
            print(f"   ✓ Class diagram: {module_name}_classes.png")
            results[module] = 'success'
        else:
            print(f"   ✗ Failed to generate class diagram")
            print(f"     Error: {stderr}")
            results[module] = 'failed'
    
    return results


def generate_package_diagram(src_dir: Path, output_dir: Path) -> bool:
    """Generate overall package dependencies diagram."""
    print("📦 Generating package diagram...")
    
    cmd = [
        'pyreverse',
        '-o', 'png',
        '-p', 'ids_packages',
        '--output-directory', str(output_dir),
        '--only-classnames',
        'src/ids'
    ]
    
    returncode, stdout, stderr = run_command(cmd, cwd=src_dir)
    
    if returncode == 0:
        print("   ✓ Package diagram: packages_ids_packages.png")
        return True
    else:
        print(f"   ✗ Failed to generate package diagram")
        print(f"     Error: {stderr}")
        return False


def generate_detailed_diagrams(src_dir: Path, output_dir: Path) -> bool:
    """Generate detailed class diagrams with all attributes and methods."""
    print("🔍 Generating detailed class diagrams...")
    
    cmd = [
        'pyreverse',
        '-o', 'png',
        '-p', 'ids_detailed',
        '--output-directory', str(output_dir),
        '-A',  # Show all attributes
        '-S',  # Show associated classes
        '--colorized',
        'src/ids'
    ]
    
    returncode, stdout, stderr = run_command(cmd, cwd=src_dir)
    
    if returncode == 0:
        print("   ✓ Detailed diagrams: classes_ids_detailed.png")
        return True
    else:
        print(f"   ✗ Failed to generate detailed diagrams")
        print(f"     Error: {stderr}")
        return False


def create_index_markdown(output_dir: Path, results: dict) -> None:
    """Create an index.md file documenting all generated diagrams."""
    index_path = output_dir / 'INDEX.md'
    
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write("# UML Diagrams - IDS Project\n\n")
        f.write("This directory contains automatically generated UML diagrams for the IDS project.\n\n")
        f.write("## Generated Diagrams\n\n")
        
        f.write("### Package Overview\n\n")
        f.write("- `packages_ids_packages.png` - Overall package structure and dependencies\n")
        f.write("- `classes_ids_detailed.png` - Detailed class diagram with all modules\n\n")
        
        f.write("### Module Diagrams\n\n")
        for module, status in sorted(results.items()):
            module_name = module.replace('/', '_').replace('src_', '')
            if status == 'success':
                f.write(f"- `classes_{module_name}.png` - {module}\n")
        
        f.write("\n## How to Regenerate\n\n")
        f.write("```bash\n")
        f.write("python scripts/generate_uml.py\n")
        f.write("```\n\n")
        f.write("## Dependencies\n\n")
        f.write("- Python 3.10+\n")
        f.write("- pylint (includes pyreverse)\n")
        f.write("- graphviz (for rendering)\n\n")
        f.write("## Notes\n\n")
        f.write("- Diagrams are automatically generated from source code\n")
        f.write("- Update this documentation when adding new modules\n")
        f.write("- CI/CD pipeline regenerates diagrams on every commit\n")
    
    print(f"📝 Created index: {index_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Generate UML diagrams for IDS project')
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=Path('docs/uml'),
        help='Output directory for UML diagrams (default: docs/uml)'
    )
    
    args = parser.parse_args()
    
    # Determine project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Create output directory
    output_dir = project_root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("🎨 IDS UML Diagram Generator")
    print("=" * 60)
    print(f"Project root: {project_root}")
    print(f"Output directory: {output_dir}")
    print()
    
    # Check if source directory exists
    src_dir = project_root / 'src' / 'ids'
    if not src_dir.exists():
        print(f"❌ Error: Source directory not found: {src_dir}")
        sys.exit(1)
    
    # Generate diagrams
    results = generate_module_diagrams(project_root, output_dir)
    
    # Generate package diagram
    generate_package_diagram(project_root, output_dir)
    
    # Generate detailed diagrams
    generate_detailed_diagrams(project_root, output_dir)
    
    # Create index
    create_index_markdown(output_dir, results)
    
    # Summary
    print()
    print("=" * 60)
    print("📊 Summary")
    print("=" * 60)
    success_count = sum(1 for status in results.values() if status == 'success')
    total_count = len(results)
    print(f"✓ Successfully generated: {success_count}/{total_count} modules")
    
    # List generated files
    generated_files = sorted(output_dir.glob('*.png'))
    print(f"✓ Total PNG files: {len(generated_files)}")
    print()
    print("Generated files:")
    for f in generated_files:
        print(f"  - {f.name}")
    
    print()
    print("✅ UML generation complete!")
    print(f"📁 View diagrams in: {output_dir}")
    
    return 0 if success_count == total_count else 1


if __name__ == '__main__':
    sys.exit(main())
