"""
Logging configuration for HiveTraceRed CLI.
"""

import logging
import sys

_VERBOSITY_LEVELS = {
    0: logging.WARNING,
    1: logging.INFO,
    2: logging.DEBUG,
}


def setup_logging(verbosity: int = 1) -> None:
    """Configure root logging for the CLI.

    Args:
        verbosity: ``0`` = WARNING, ``1`` = INFO, ``2`` = DEBUG. Values above
            2 are clamped to DEBUG; negative values are clamped to WARNING.
    """
    level = _VERBOSITY_LEVELS.get(max(0, min(verbosity, 2)), logging.INFO)
    # force=True so repeated calls (e.g. embedding CLI usage) actually apply.
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )
