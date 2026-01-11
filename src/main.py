#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
