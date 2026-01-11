import sys
from pathlib import Path

# Mirror the runtime import hack in src/main.py so `from core.payload import ...`
# resolves the same way under pytest as it does when the app is run.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
