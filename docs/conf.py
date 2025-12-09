# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# For local development, add src to path if package not installed
try:
    import hivetracered  # noqa: F401
except ImportError:
    sys.path.insert(0, os.path.abspath('../src'))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'HiveTraceRed'
copyright = '2025, HiveTrace'
author = 'HiveTrace'
release = '1.0.4'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'sphinx.ext.intersphinx',
    'sphinx_autodoc_typehints',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'furo'
html_static_path = ['_static']
html_title = 'HiveTraceRed Documentation'

# Furo theme options
html_theme_options = {
    "sidebar_hide_name": False,
    "light_css_variables": {
        "color-brand-primary": "#e74c3c",
        "color-brand-content": "#e74c3c",
    },
    "dark_css_variables": {
        "color-brand-primary": "#f39c12",
        "color-brand-content": "#f39c12",
    },
}

# -- Extension configuration -------------------------------------------------

# autodoc configuration
autodoc_default_options = {
    'members': True,
    'undoc-members': True,
    'show-inheritance': True,
    'special-members': '__init__',
    'imported-members': True,
}

autodoc_typehints = 'description'
autodoc_typehints_description_target = 'documented'

# Mock imports for optional dependencies
autodoc_mock_imports = [
    'cyrtranslit',
    'langchain_gigachat',
    'langchain_google_genai',
    'langchain_openai',
    'langchain_ollama',
    'langchain_community',
    'langchain',
    'dotenv',
    'tqdm',
    'langchain_core',
    'yandex_cloud_ml_sdk',
    'yandexcloud',
    'aiohttp',
    'requests',
    'google',
    'google.genai',
    'tenacity',
    'pandas',
    'pyarrow',
]

# autosummary configuration
autosummary_generate = True

# Napoleon settings for Google/NumPy style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True

# Intersphinx mapping
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'pandas': ('https://pandas.pydata.org/docs/', None),
    'numpy': ('https://numpy.org/doc/stable/', None),
}