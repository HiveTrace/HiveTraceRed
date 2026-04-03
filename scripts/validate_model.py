#!/usr/bin/env python
"""CLI wrapper to validate model conformance.

Usage:
    python scripts/validate_model.py --all              # Free, no tokens
    python scripts/validate_model.py --model OpenAIModel  # Uses tokens
"""

import argparse
import sys

import pytest


def main():
    parser = argparse.ArgumentParser(description="Validate model conformance")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--model", type=str, help="Model class to validate with real API calls (uses tokens)")
    group.add_argument("--all", action="store_true", help="Validate all models without API calls (free)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    pytest_args = ["tests/test_model_conformance.py", "-v"]

    if args.all:
        pytest_args += ["-m", "not real_model"]
    else:
        pytest_args += ["-k", args.model]

    sys.exit(pytest.main(pytest_args))


if __name__ == "__main__":
    main()
