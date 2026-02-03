# UML Diagrams - IDS Project

This directory contains automatically generated UML diagrams for the IDS project.

## Generated Diagrams

### Package Overview

- `packages_ids_packages.png` - Overall package structure and dependencies
- `classes_ids_detailed.png` - Detailed class diagram with all modules

### Module Diagrams

- `classes_ids.png` - src/ids
- `classes_ids_app.png` - src/ids/app
- `classes_ids_composants.png` - src/ids/composants
- `classes_ids_config.png` - src/ids/config
- `classes_ids_deploy.png` - src/ids/deploy
- `classes_ids_domain.png` - src/ids/domain
- `classes_ids_infrastructure.png` - src/ids/infrastructure
- `classes_ids_interfaces.png` - src/ids/interfaces
- `classes_ids_suricata.png` - src/ids/suricata

## How to Regenerate

```bash
python scripts/generate_uml.py
```

## Dependencies

- Python 3.10+
- pylint (includes pyreverse)
- graphviz (for rendering)

## Notes

- Diagrams are automatically generated from source code
- Update this documentation when adding new modules
- CI/CD pipeline regenerates diagrams on every commit
