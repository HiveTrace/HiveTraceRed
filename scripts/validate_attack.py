#!/usr/bin/env python
"""CLI wrapper to validate attack conformance.

Usage:
    python scripts/validate_attack.py --all
    python scripts/validate_attack.py --attack StorytellingAttack
"""

import argparse
import sys

import pytest


def main():
    parser = argparse.ArgumentParser(description="Validate attack conformance")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--attack", type=str, help="Name of the attack to validate")
    group.add_argument("--all", action="store_true", help="Validate all registered attacks")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    pytest_args = ["tests/test_attack_conformance.py"]

    if args.attack:
        pytest_args += ["-k", args.attack]

    if args.verbose:
        pytest_args.append("-v")
    else:
        pytest_args.append("-v")

    sys.exit(pytest.main(pytest_args))


if __name__ == "__main__":
    main()
