# HiveTraceRed Documentation

This directory contains the Sphinx documentation for HiveTraceRed.

## Building the Documentation

### Prerequisites

Install documentation dependencies:

```bash
pip install -r requirements.txt
```

### Build HTML Documentation

#### Using Make (Linux/macOS)

```bash
cd docs
make html
```

#### Using the Build Script (from project root)

```bash
./build_docs.sh
```

#### Manual Build

```bash
cd docs
sphinx-build -b html . _build/html
```

### View Documentation

After building, open `_build/html/index.html` in your browser:

- **macOS**: `open _build/html/index.html`
- **Linux**: `xdg-open _build/html/index.html`
- **Windows**: `start _build/html/index.html`

## Documentation Structure

```
docs/
├── index.rst                 # Main landing page
├── conf.py                   # Sphinx configuration
├── getting-started/          # Installation and quickstart guides
│   ├── installation.rst
│   ├── quickstart.rst
│   └── configuration.rst
├── user-guide/              # User guides
│   ├── running-pipeline.rst
│   ├── custom-attacks.rst
│   ├── model-integration.rst
│   └── evaluators.rst
├── examples/                # Complete examples
│   ├── basic-usage.rst
│   ├── full-pipeline.rst
│   └── system-prompt-extraction.rst
├── api/                     # API reference (autodoc)
│   ├── index.rst
│   ├── attacks.rst
│   ├── models.rst
│   ├── evaluators.rst
│   ├── pipeline.rst
│   └── utils.rst
├── attacks/                 # Attack documentation
│   ├── index.rst
│   ├── roleplay.rst
│   ├── persuasion.rst
│   ├── token-smuggling.rst
│   └── ...
└── license.rst             # License information
```

## Cleaning Build Files

```bash
cd docs
make clean
```

## Documentation Features

- **Sphinx + autodoc**: Auto-generated API documentation from docstrings
- **Furo theme**: Modern, responsive design
- **Type hints**: Automatic type annotation display
- **Cross-references**: Links between modules and functions
- **Search functionality**: Full-text search
- **Code highlighting**: Syntax-highlighted examples

## Updating Documentation

1. Edit `.rst` files in the appropriate directory
2. For API changes, update docstrings in Python source files
3. Rebuild documentation: `make html`
4. Check for warnings in build output

## Publishing Documentation

The built HTML can be hosted on:

- GitHub Pages
- Read the Docs
- Any static site hosting service

Simply deploy the contents of `_build/html/` directory.