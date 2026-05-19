"""Tests for HtmlEntityAttack — per-encoder branches.

The golden `<` → `&#60;` row lives in test_attacks_token_smuggling_golden_transforms.py.
This file pins the inverse property: html.unescape recovers the original.
"""

from __future__ import annotations

import html

from hivetracered.attacks.types.single_turn.token_smuggling.html_entity_attack import HtmlEntityAttack


def test_transform_round_trip_via_html_unescape_recovers_original():
    attack = HtmlEntityAttack(raw=True)
    original = "<div>Hi & Привет!</div>"

    encoded = attack.transform(original)
    decoded = html.unescape(encoded)

    assert decoded == original
