#!/bin/bash

# HiveTraceRed Documentation Build Script
# Similar to LLAMATOR-Core's build_docs.sh

set -e -x

# Clean previous builds
rm -rf public/
rm -rf docs/_build

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment (.venv)..."
    source .venv/bin/activate
else
    echo "No virtual environment found, using system Python"
fi

# Generate license table
echo "Generating license information..."
pip-licenses --format=rst --output-file=docs/licenses_table.rst

# Build Sphinx documentation
echo "Building Sphinx documentation..."
sphinx-build -b html docs/ public/ -d docs/_build/doctrees

echo "Documentation build completed successfully!"
echo "Documentation is available in the 'public/' directory"
echo ""
echo "To view locally:"
echo "  - Open public/index.html in your browser"
echo "  - Or run: python -m http.server 8000 --directory public"
echo "  - Then visit: http://localhost:8000"