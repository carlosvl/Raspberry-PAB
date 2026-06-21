"""Command-line interface."""

from __future__ import annotations

import argparse
import logging
import sys

from raspberry_pab import __version__
from raspberry_pab.app import Application
from raspberry_pab.config import Settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="raspberry-pab",
        description="Raspberry Pi OS kiosk application",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (overrides PAB_LOG_LEVEL)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    settings = Settings.from_env()
    log_level = args.log_level or settings.log_level
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    return Application(settings).run()


if __name__ == "__main__":
    sys.exit(main())
