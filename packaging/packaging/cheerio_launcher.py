"""Frozen entry point: package imports must remain absolute."""
import sys
from pathlib import Path

# Source-tree launch includes the repository root; frozen builds collect cheerio.
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cheerio.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
