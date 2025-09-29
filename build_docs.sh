#!/bin/bash

# Build script for HiveTraceRed documentation

set -e

echo "Building HiveTraceRed Documentation"
echo "===================================="
echo ""

# Check if we're in the correct directory
if [ ! -f "docs/conf.py" ]; then
    echo "Error: docs/conf.py not found. Please run this script from the project root."
    exit 1
fi

# Check if sphinx is installed
if ! command -v sphinx-build &> /dev/null; then
    echo "Sphinx not found. Installing documentation dependencies..."
    pip install -r docs/requirements.txt
fi

# Clean previous build
echo "Cleaning previous build..."
cd docs
make clean

# Build HTML documentation
echo ""
echo "Building HTML documentation..."
make html

# Check if build was successful
if [ $? -eq 0 ]; then
    echo ""
    echo "===================================="
    echo "Documentation built successfully!"
    echo "===================================="
    echo ""
    echo "HTML documentation is available at:"
    echo "  file://$(pwd)/_build/html/index.html"
    echo ""
    echo "To view the documentation:"
    echo "  open _build/html/index.html        (macOS)"
    echo "  xdg-open _build/html/index.html    (Linux)"
    echo "  start _build/html/index.html       (Windows)"
    echo ""

    # Optionally open in browser (macOS/Linux)
    if [[ "$OSTYPE" == "darwin"* ]]; then
        read -p "Open documentation in browser? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            open _build/html/index.html
        fi
    fi
else
    echo ""
    echo "===================================="
    echo "Documentation build failed!"
    echo "===================================="
    echo "Check the error messages above for details."
    exit 1
fi