"""
Command-line interface for HiveTraceRed.

This module provides the main entry point for running HiveTraceRed from the command line.
It imports and delegates to the run.py script functionality.
"""

import sys
import os

# Add the project root to the path to import run.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from run import main

if __name__ == "__main__":
    main()
