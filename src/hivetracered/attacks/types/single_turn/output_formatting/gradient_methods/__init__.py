"""Gradient-based output formatting attacks. Each attack is declared in its own *.yaml
in this directory. They are registered under the ``output_formatting`` category."""
from pathlib import Path

from hivetracered.attacks.yaml_loader import load_attacks_from_dir

_loaded = load_attacks_from_dir(Path(__file__).parent, category="output_formatting")
globals().update(_loaded)
__all__ = sorted(_loaded)
