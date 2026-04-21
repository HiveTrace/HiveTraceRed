#!/usr/bin/env python3
"""
HiveTraceRed CLI entry point.

Usage::

    hivetracered --config config.yaml
    python -m hivetracered --config config.yaml
"""

import argparse
import asyncio
import logging

from hivetracered.config import load_config
from hivetracered.log import setup_logging
from hivetracered.runner import run_pipeline

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="HiveTraceRed - LLM Red Teaming Framework")
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to YAML configuration file",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="count",
        default=1,
        help="Increase verbosity (-v for INFO (default), -vv for DEBUG)",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Only show warnings and errors",
    )
    args = parser.parse_args()

    verbosity = 0 if args.quiet else args.verbose
    setup_logging(verbosity)

    try:
        config = load_config(args.config)
        asyncio.run(run_pipeline(config))
    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user")
    except (FileNotFoundError, ValueError) as e:
        logger.error("%s", e)
        raise SystemExit(1)
    except Exception:
        logger.exception("Pipeline failed")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
