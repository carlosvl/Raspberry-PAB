"""Allow running as `python -m raspberry_pab`."""

from raspberry_pab.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
