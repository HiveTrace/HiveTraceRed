"""Tests for hivetracered.log.setup_logging.

Spec sources:
- Module docstring at src/hivetracered/log.py:1-3
- setup_logging docstring at src/hivetracered/log.py:15-21
  ("0 = WARNING, 1 = INFO, 2 = DEBUG. Values above 2 are clamped to DEBUG;
   negative values are clamped to WARNING. force=True so repeated calls
   actually apply.")
"""

from __future__ import annotations

import logging
import sys

import pytest

from hivetracered.log import setup_logging


# Named constants pulled from logging stdlib so values are not mirror-of-impl.
WARNING = logging.WARNING  # = 30 in stdlib
INFO = logging.INFO        # = 20 in stdlib
DEBUG = logging.DEBUG      # = 10 in stdlib


@pytest.fixture
def restore_root_logger():
    """Snapshot and restore root logger handlers/level so tests don't bleed."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    yield
    root.handlers = saved_handlers
    root.setLevel(saved_level)


@pytest.mark.parametrize(
    ("verbosity", "expected_level"),
    [
        (1, INFO),
        (3, DEBUG),    # spec: clamp >2 to DEBUG
        (-1, WARNING), # spec: clamp <0 to WARNING
    ],
    ids=[
        "verbosity-1-info",
        "above-max-clamped-to-debug",
        "negative-clamped-to-warning",
    ],
)
def test_setup_logging_verbosity_maps_to_level(
    restore_root_logger, verbosity, expected_level
):
    setup_logging(verbosity)

    assert logging.getLogger().level == expected_level


def test_setup_logging_attaches_stderr_stream_handler(restore_root_logger):
    setup_logging(1)

    root = logging.getLogger()
    stream_handlers = [h for h in root.handlers if isinstance(h, logging.StreamHandler)]
    assert any(h.stream is sys.stderr for h in stream_handlers)


def test_setup_logging_force_allows_reapplication(restore_root_logger):
    setup_logging(0)  # WARNING
    first_handlers = list(logging.getLogger().handlers)

    setup_logging(2)  # DEBUG — must take effect despite prior call

    root = logging.getLogger()
    assert root.level == DEBUG
    # force=True replaces handlers — the new handler list must not be the same objects.
    assert all(h not in first_handlers for h in root.handlers)
