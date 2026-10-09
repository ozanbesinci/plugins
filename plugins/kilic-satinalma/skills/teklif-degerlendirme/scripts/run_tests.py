from __future__ import annotations
import os, sys, unittest
from pathlib import Path
os.environ.setdefault('TEKLIF_TEST_SQLITE','1')
root=Path(__file__).resolve().parent
suite=unittest.defaultTestLoader.discover(str(root/'tests'), pattern='test_*.py')
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
