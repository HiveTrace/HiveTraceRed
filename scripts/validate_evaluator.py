#!/usr/bin/env python
"""CLI wrapper to validate evaluator conformance.

Usage:
    python scripts/validate_evaluator.py --all
    python scripts/validate_evaluator.py --evaluator KeywordEvaluator
"""

import argparse
import sys

import pytest


def main():
    parser = argparse.ArgumentParser(description="Validate evaluator conformance")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--evaluator", type=str, help="Name of the evaluator to validate")
    group.add_argument("--all", action="store_true", help="Validate all registered evaluators")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    pytest_args = ["tests/test_evaluator_conformance.py"]

    if args.evaluator:
        pytest_args += ["-k", args.evaluator]

    if args.verbose:
        pytest_args.append("-v")

    sys.exit(pytest.main(pytest_args))


if __name__ == "__main__":
    main()
