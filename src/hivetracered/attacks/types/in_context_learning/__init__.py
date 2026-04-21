"""In-context learning attacks. Each attack is declared in its own *.yaml in this directory."""
from pathlib import Path

from hivetracered.attacks.yaml_loader import load_attacks_from_dir

_loaded = load_attacks_from_dir(Path(__file__).parent, category="in_context_learning")
globals().update(_loaded)
__all__ = sorted(_loaded)
