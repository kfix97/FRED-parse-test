import sys
from pathlib import Path

# Ensure the repo root is on the import path so tests can import local modules directly.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
