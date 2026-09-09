import sys
from pathlib import Path

# Ensure the repository root (and ta_plugins) is importable regardless of
# how the editable install resolved packages.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
