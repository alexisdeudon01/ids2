# UML Architecture Documentation

This directory contains automatically generated UML diagrams that visualize the structure and relationships within the IDS project.

## 📊 Overview

The UML diagrams are generated using **pyreverse** (part of pylint) and provide comprehensive views of:

- **Class hierarchies** - Shows inheritance, composition, and associations
- **Package dependencies** - Visualizes module interconnections
- **Interface implementations** - Documents protocol/ABC implementations
- **System architecture** - High-level system structure

## 🎯 Available Diagrams

### 📦 Package-Level Diagrams

| Diagram | Description |
|---------|-------------|
| `packages_ids_packages.png` | **Main Overview** - Complete package structure and dependencies |
| `packages_ids_detailed.png` | Detailed package diagram with all relationships |

### 🏗️ Module-Specific Class Diagrams

| Module | Class Diagram | Package Diagram | Description |
|--------|--------------|-----------------|-------------|
| **Overall** | `classes_ids_detailed.png` | `packages_ids.png` | Complete system with all classes |
| **Domain** | `classes_ids_domain.png` | `packages_ids_domain.png` | Data models and entities |
| **Interfaces** | `classes_ids_interfaces.png` | `packages_ids_interfaces.png` | Protocols and abstractions |
| **Composants** | `classes_ids_composants.png` | `packages_ids_composants.png` | System components |
| **Infrastructure** | `classes_ids_infrastructure.png` | `packages_ids_infrastructure.png` | External integrations |
| **Suricata** | `classes_ids_suricata.png` | `packages_ids_suricata.png` | IDS-specific logic |
| **App** | `classes_ids_app.png` | `packages_ids_app.png` | Application orchestration |
| **Config** | `classes_ids_config.png` | `packages_ids_config.png` | Configuration management |
| **Deploy** | `classes_ids_deploy.png` | `packages_ids_deploy.png` | Deployment utilities |

## 🔄 Regenerating Diagrams

### Manual Generation

```bash
# Install dependencies
pip install pylint>=3.0.0
sudo apt-get install graphviz  # or brew install graphviz on macOS

# Generate diagrams
python scripts/generate_uml.py

# Generate to custom directory
python scripts/generate_uml.py --output-dir custom/path
```

### Automation (optional)

If you want automation, you can run `python scripts/generate_uml.py` from your own pipeline when Python sources change.

## 📖 Reading the Diagrams

### Class Diagrams

- **Boxes** represent classes
- **Arrows** show relationships:
  - **Solid arrow (→)** = Inheritance (is-a)
  - **Dashed arrow (⇢)** = Implementation/Protocol
  - **Diamond arrow (◆→)** = Composition (has-a)
  - **Empty diamond (◇→)** = Aggregation (uses)

### Package Diagrams

- **Boxes** represent modules/packages
- **Arrows** show import dependencies
- **Thickness** indicates coupling strength

## 🎨 Diagram Colors

Pyreverse uses colors to indicate:

- **Blue** = Classes
- **Green** = Methods
- **Red** = Attributes
- **Yellow** = Abstract classes

## 🔍 Use Cases

### For Developers

- **Onboarding** - Understand system architecture quickly
- **Refactoring** - Identify coupling and dependencies
- **Code Review** - Verify design patterns
- **Documentation** - Visual reference for technical docs

### For Architects

- **System Design** - Validate SOLID principles
- **Dependency Management** - Detect circular dependencies
- **Interface Design** - Review protocol/ABC usage
- **Module Boundaries** - Ensure proper separation of concerns

## 🛠️ Troubleshooting

### Common Issues

1. **Diagrams not generating**
   ```bash
   # Check dependencies
   pyreverse --version
   dot -V
   ```

2. **Large diagrams are unreadable**
   - Use module-specific diagrams instead of the overall diagram
   - Zoom in or use a larger monitor
   - Consider refactoring to reduce complexity

3. **Missing dependencies in package diagram**
   - Ensure all `__init__.py` files exist
   - Check that imports are at module level

## 📚 Additional Resources

- [Pyreverse Documentation](https://pylint.readthedocs.io/en/latest/pyreverse.html)
- [UML Class Diagram Guide](https://www.uml-diagrams.org/class-diagrams-overview.html)
- [SOLID Principles](https://en.wikipedia.org/wiki/SOLID)

## 🚀 Automation ideas (optional)

If you want automation, you can:

- ✅ **Regenerate diagrams** on code changes
- ✅ **Track quality metrics** (e.g., pylint score)
- ✅ **Store outputs** as build artifacts

## 📝 Notes

- Diagrams reflect the **current state** of the codebase
- Generated files can be stored alongside the code for easy access
- Large refactorings will significantly change diagrams
- Consider reviewing diagrams after major changes

## 🤝 Contributing

When adding new modules:

1. Ensure proper Python package structure (`__init__.py`)
2. Run UML generation locally to verify
3. Update this README if needed
4. If you use automation, regenerate diagrams when changes are merged

---

**Last Updated:** Regenerated when the generator runs  
**Generator:** pyreverse (pylint)  
**Format:** PNG (rendered via Graphviz)
