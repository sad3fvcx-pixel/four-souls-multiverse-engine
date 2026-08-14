# src/fsme/stack/labels.py

"""
Names of the engine's own stack objects.

A procedure is registered by the rules and pushed by whoever needs it, and an
effect is allowed to be one of those: a card that says "end the turn" asks for
the same turn ending the rules use, not a second one of its own. The names live
here, below both, so that neither has to import the other to agree on them.
"""

from __future__ import annotations

ADVANCE_TURN = "advance_turn"
"""Close the current turn and open the next."""

DISCARD_PLAYED_LOOT = "discard_played_loot"
"""Send a resolved loot card to the discard pile, if it is still nowhere."""

DISCARD_TO_HAND_LIMIT = "discard_to_hand_limit"
"""Trim a hand down to the limit at the end of a turn."""

COMBAT_ROUND = "combat_round"
"""Resolve one round of an ongoing attack."""

SETTLE_ROLL = "settle_roll"
"""Close a roll the table has finished answering, and carry on."""

COMBAT_STRIKE = "combat_strike"
"""Apply an attack roll once the table has finished answering it."""

LOOT_STEP = "loot_step"
"""Draw the cards a turn opens with, once the start-of-turn effects are done."""

PURCHASE = "purchase"
"""
Carry out a purchase the buyer declared.

COMPREHENSIVE_RULES.md §6: what a player does is declare the buy, and the
declaration goes into the queue. Paying and taking the item happen when it
resolves — which is why a card may answer a purchase, and why a purchase can
find, on resolving, that there is nothing left to buy.
"""

ATTACK_DECLARATION = "attack_declaration"
"""
Begin an attack the attacker declared.

COMPREHENSIVE_RULES.md §7, same shape as a purchase: the declaration queues,
and the attack begins when it resolves.
"""
