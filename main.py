"""Entry point: parse CLI arguments and start uvicorn.

This is what the container runs (``CMD ["python3", "main.py"]``). Host, port and
the application import string come from ``settings.uvicorn``; the only thing the
command line can override is the cache freshness.
"""

import argparse
import os
from typing import List, Optional

import uvicorn

from mipserver.config import settings

# also sets loguru.logger defaults...

from loguru import logger


def _non_negative_float(raw: str) -> float:
    """Parse an argparse value as a float that must not be negative.

    Args:
        raw: The raw command line token.

    Returns:
        The parsed value.

    Raises:
        argparse.ArgumentTypeError: If the token is not a number or is negative.
    """
    try:
        value: float = float(raw)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {raw!r}")

    if value < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {value}")

    return value


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Build the argument parser and parse the command line.

    Args:
        argv: Arguments to parse; ``None`` reads :data:`sys.argv`.

    Returns:
        The parsed arguments. ``cache_freshness_minutes`` is ``None`` when the flag
        was not given, which means "leave the configured value alone".
    """
    parser = argparse.ArgumentParser(prog="mipserver", description="mip package index server")
    parser.add_argument(
        "--cache-freshness-minutes",
        type=_non_negative_float,
        default=None,
        metavar="MINUTES",
        help=(
            "how long a generated package.json is served without re-checking git "
            "(0 = always re-check). Overrides CACHE__FRESHNESS_MINUTES / config.yaml. "
            f"Currently: {settings.cache.freshness_minutes}"
        ),
    )
    return parser.parse_args(argv)


def main() -> None:
    """Apply command line overrides and hand over to uvicorn.

    A ``--cache-freshness-minutes`` override is written to the environment *and* to
    the settings singleton: with ``reload`` enabled the serving process is a child
    that re-imports the configuration, so an in-process mutation alone would be lost.
    """
    logger.info(f"{__file__}::MAIN")

    args: argparse.Namespace = parse_args()

    if args.cache_freshness_minutes is not None:
        # Set the env var so uvicorn reload subprocesses (which re-import config) inherit the value;
        # additionally patch the singleton for the case where we serve in-process.
        os.environ["CACHE__FRESHNESS_MINUTES"] = str(args.cache_freshness_minutes)
        settings.cache.freshness_minutes = args.cache_freshness_minutes
        logger.info(f"cache freshness overridden via CLI: {settings.cache.freshness_minutes} minutes")

    logger.info(f"package.json cache freshness: {settings.cache.freshness_minutes} minutes")

    uvicorn.run(
        app=settings.uvicorn.app,
        host=settings.uvicorn.host,
        port=settings.uvicorn.port,
        log_level=settings.uvicorn.log_level,
        reload=settings.uvicorn.reload,
    )


if __name__ == "__main__":
    main()


# https://plainenglish.io/blog/unit-testing-in-python-structure-57acd51da923#directory-layout
# mpu <-- Root of the git repository
# ├── mpu <-- Root of the package
# │   ├── datastructures/
# │   │   ├── __init__.py
# │   │   └── trie
# │   │       ├── char_trie.py
# │   │       └── __init__.py
# │   ├── geometry.py
# │   ├── image.py
# │   ├── __init__.py
# │   ├── io.py
# │   └── _version.py
# ├── README.md
# ├── requirements-dev.in
# ├── requirements-dev.txt
# ├── tests/
# │   ├── files/
# │   ├── test_char_trie.py
# │   ├── test_datastructures.py
# │   ├── test_geometry.py
# │   ├── test_image.py
# │   ├── test_io.py
# │   └── test_main.py
# └── tox.ini
