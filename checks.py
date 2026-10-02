"""One command for boundary, acquisition and disclosure checks."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
