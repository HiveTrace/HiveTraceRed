HiveTraceRed Documentation
==========================

**HiveTraceRed** is a comprehensive security framework for testing Large Language Model (LLM) vulnerabilities through systematic attack methodologies and evaluation pipelines.

This framework is designed for security researchers, AI safety engineers, and red teamers who need to assess the robustness of LLM systems against adversarial attacks.

Key Features
------------

* **80+ Attack Types**: Comprehensive library across 10 attack categories including roleplay, persuasion, token smuggling, context switching, and more
* **Multiple LLM Providers**: Built-in support for OpenAI, GigaChat, YandexGPT, Google Gemini, OpenRouter, and extensible architecture for custom providers
* **Advanced Evaluation**: WildGuard evaluators and systematic safety assessment tools
* **Async Pipeline**: Efficient streaming architecture optimized for large-scale testing
* **Multi-Language Support**: Testing capabilities across multiple languages including Russian
* **Modular Architecture**: Easy to extend with custom attacks, models, and evaluators

Quick Links
-----------

* :doc:`getting-started/installation` - Get started quickly
* :doc:`getting-started/quickstart-api` - Your first test (cloud APIs)
* :doc:`getting-started/quickstart-local` - Your first test (on-premise)
* :doc:`attacks/index` - Explore attack types
* :doc:`api/attacks` - API reference

Table of Contents
-----------------

.. toctree::
   :maxdepth: 2
   :caption: Getting Started

   getting-started/installation
   getting-started/quickstart-api
   getting-started/quickstart-local
   getting-started/configuration

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   user-guide/running-pipeline
   user-guide/custom-attacks
   user-guide/model-integration
   user-guide/evaluators

.. toctree::
   :maxdepth: 2
   :caption: Examples

.. toctree::
   :maxdepth: 2
   :caption: Attacks Reference

   attacks/index

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/attacks
   api/models
   api/evaluators
   api/pipeline

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`