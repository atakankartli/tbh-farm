"""PyInstaller runtime hook: make the exe's folder importable so the
user-editable config.py sitting next to the exe is picked up (the `config`
module is deliberately excluded from the frozen bundle)."""

import os
import sys

if getattr(sys, "frozen", False):
  sys.path.insert(0, os.path.dirname(sys.executable))
