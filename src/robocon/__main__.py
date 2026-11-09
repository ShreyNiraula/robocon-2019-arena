"""Command-line entry point: ``robocon`` or ``python -m robocon``."""

from __future__ import annotations

import argparse
import logging


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="robocon",
        description="3D visualisation of the ABU Robocon 2019 arena and robots.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="log model loading")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    from robocon.app import App

    App().run()


if __name__ == "__main__":
    main()
