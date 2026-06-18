#!/usr/bin/env python3
"""Back-compat shim — run the SLAC linter with zero install:

    python3 linter/slac_lint.py FILE...

Once installed (`pip install .` or `pipx install slac-lang`), prefer the CLI:

    slac lint FILE...

The real implementation lives in the importable package at src/slac/linter.py.
"""

import os
import sys

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

from slac.linter import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
