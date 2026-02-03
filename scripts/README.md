# Scripts Directory

This directory contains automation scripts for the IDS project, including UML generation, architecture analysis, and continuous improvement pipelines.

## 📜 Available Scripts

### 🎨 UML Generation

#### `generate_uml.py`
Generates comprehensive UML diagrams using pyreverse.

```bash
# Generate all UML diagrams
python scripts/generate_uml.py

# Generate to custom directory
python scripts/generate_uml.py --output-dir custom/path
```

**Outputs:**
- Class diagrams for each module
- Package dependency diagrams
- Detailed system architecture diagrams
- INDEX.md documentation

**Requirements:**
- Python 3.10+
- pylint (includes pyreverse)
- graphviz (system package)

---

### 🔍 Architecture Analysis

#### `analyze_architecture.py`
Analyzes code architecture and identifies quality issues.

```bash
# Analyze default source directory
python scripts/analyze_architecture.py

# Analyze custom directory
python scripts/analyze_architecture.py --src-dir path/to/src
```

**What it checks:**
- ✅ Circular dependencies
- ✅ High coupling (Ce/Ca metrics)
- ✅ Large modules/classes
- ✅ Complex inheritance hierarchies
- ✅ Module organization

**Output:**
- Architecture health score (0-100)
- Detailed issue list with severity
- Actionable improvement suggestions

---

### 🚀 Continuous Improvement Pipeline

#### `improve_pipeline.py`
Runs complete improvement cycles combining UML generation and analysis.

```bash
# Run single improvement cycle
python scripts/improve_pipeline.py

# Run multiple iterations
python scripts/improve_pipeline.py --iterations 3

# Target specific health score
python scripts/improve_pipeline.py --target-score 98.0
```

**What it does:**
1. Generates UML diagrams
2. Analyzes architecture
3. Saves metrics history
4. Tracks progress over time
5. Reports improvements

**Outputs:**
- UML diagrams (docs/uml/*.png)
- Architecture reports
- Metrics history (JSON)
- Progress tracking

---

## 🔄 Workflow Integration

These scripts are integrated into the CI/CD pipeline via `.github/workflows/uml-generation.yml`:

- ✅ Automatic UML generation on code changes
- ✅ Architecture analysis on every commit
- ✅ Quality metrics tracking
- ✅ Artifacts stored for 90 days

---

## 📊 Usage Examples

### Quick Start

```bash
# 1. Install dependencies
pip install pylint>=3.0.0
sudo apt-get install graphviz

# 2. Generate UML diagrams
python scripts/generate_uml.py

# 3. Analyze architecture
python scripts/analyze_architecture.py

# 4. View results
ls -lh docs/uml/
```

### Iterative Improvement Workflow

```bash
# 1. Run initial pipeline
python scripts/improve_pipeline.py

# 2. Review analysis output
#    - Fix identified issues
#    - Refactor problematic modules
#    - Apply SOLID principles

# 3. Run pipeline again
python scripts/improve_pipeline.py

# 4. Compare metrics
#    - Check metrics_history.json
#    - Verify health score improved
```

### CI/CD Integration

The scripts run automatically on:
- Push to main/dev/develop branches
- Pull requests
- Manual workflow dispatch

View results in:
- GitHub Actions artifacts
- PR comments (future)
- Metrics dashboard (future)

---

## 🎯 Best Practices

### When to Run Scripts

| Script | When to Run | Frequency |
|--------|------------|-----------|
| `generate_uml.py` | After code changes | On commit (auto) |
| `analyze_architecture.py` | Before refactoring | Daily/Weekly |
| `improve_pipeline.py` | Major refactoring | Sprint cycles |

### Interpreting Results

**Health Score Guide:**
- 95-100: Excellent architecture
- 85-94: Good, minor improvements needed
- 70-84: Fair, plan refactoring
- <70: Poor, immediate action required

**Priority Issues:**
1. **Errors** (must fix immediately)
   - Circular dependencies
   - Critical coupling issues

2. **Warnings** (should fix soon)
   - Large modules
   - High coupling
   - Many classes per file

### Improvement Strategies

**For Circular Dependencies:**
```python
# Before: A imports B, B imports A ❌
# After: Extract interface C, both depend on C ✅
```

**For High Coupling:**
```python
# Before: Direct dependencies on 15 modules ❌
# After: Use dependency injection, depend on interfaces ✅
```

**For Large Modules:**
```python
# Before: 1000+ line file with 10 classes ❌
# After: Split into focused modules, SRP ✅
```

---

## 📚 Additional Resources

- [UML Documentation](../docs/uml/README.md)
- [Pyreverse Guide](https://pylint.readthedocs.io/en/latest/pyreverse.html)
- [SOLID Principles](https://en.wikipedia.org/wiki/SOLID)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

---

## 🐛 Troubleshooting

### Common Issues

**1. "pyreverse not found"**
```bash
pip install pylint>=3.0.0
pyreverse --version
```

**2. "Graphviz needs to be installed"**
```bash
# Ubuntu/Debian
sudo apt-get install graphviz

# macOS
brew install graphviz

# Verify
dot -V
```

**3. "No diagrams generated"**
- Check that `src/ids` exists
- Verify Python files have valid syntax
- Ensure `__init__.py` files exist in all packages

**4. "Analysis shows no modules"**
- Check file paths in error messages
- Verify source directory structure
- Ensure files are readable

---

## 🤝 Contributing

When adding new scripts:

1. Follow naming convention: `verb_noun.py`
2. Add help text and argparse
3. Update this README
4. Add to CI/CD if appropriate
5. Include example usage

---

## 📝 Notes

- Scripts are designed to be idempotent (safe to run multiple times)
- All outputs are generated in `docs/uml/`
- Metrics history is tracked in JSON for trend analysis
- Scripts use relative paths for portability

---

**Maintained by:** IDS Development Team  
**Last Updated:** 2024 (auto-updated on changes)
