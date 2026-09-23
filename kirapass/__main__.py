"""Allow `python -m kirapass ...` as an alternative to `python KiraPass.py`."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
