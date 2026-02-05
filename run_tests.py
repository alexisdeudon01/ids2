#!/usr/bin/env python3
"""Run all tests."""

import sys
import unittest
from pathlib import Path

# Add webbapp to path
sys.path.insert(0, str(Path(__file__).parent / "webbapp"))

# Discover and run tests
loader = unittest.TestLoader()
suite = loader.discover('tests', pattern='test_*.py')
runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

# Exit with error code if tests failed
sys.exit(0 if result.wasSuccessful() else 1)
