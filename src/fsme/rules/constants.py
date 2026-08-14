# src/fsme/rules/constants.py

"""
Rule parameters for Four Souls Multiverse Engine.

These are the official numbers. They live in one place so that a custom
ruleset can change them without editing rule logic, and so that a reader can
check them against the rulebook without reading any code.
"""

from __future__ import annotations

TREASURE_COST = 10
"""Cost of buying the top treasure or a shop item, in cents."""

HAND_LIMIT = 10
"""Loot cards a player may keep at the end of their turn."""

SOULS_TO_WIN = 4
"""Souls required for victory."""

BASE_PLAYER_ATTACK = 1
"""Damage a player deals on a successful attack roll before modifiers."""

BASE_PLAYER_HP = 2
"""Hit points a character starts with before modifiers."""

LOOT_STEP_CARDS = 1
"""Loot cards drawn at the start of a turn, before modifiers."""

LOOT_PLAYS_PER_TURN = 1
"""Loot cards playable during the loot phase before modifiers."""

ATTACKS_PER_TURN = 1
"""Attacks declarable per turn before modifiers."""

PURCHASES_PER_TURN = 1
"""Items buyable per turn before modifiers."""

DICE_SIDES = 6
"""The game uses a single six-sided die."""

STARTING_HAND_SIZE = 3
"""Loot cards dealt to each player at the start of the game."""

MONSTER_SLOTS = 2
"""Monsters face-up in the monster area."""

SHOP_SLOTS = 2
"""Treasures face-up in the shop."""

STALLED_COMBAT_ROUNDS = 3
"""
How many rounds an attack may change nothing before it is called off.

An attack ends when one side dies. If neither side can hurt the other — every
point prevented, every blow reduced to nothing — the rounds would go on for
ever, so the engine stops them. This is a safeguard, not a rule of the game:
nothing printed on a card describes it, and any attack in which damage lands
resets the count.
"""
