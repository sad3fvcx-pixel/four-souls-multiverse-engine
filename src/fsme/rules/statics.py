# src/fsme/rules/statics.py

"""
Static modifiers.

A static changes a number for as long as its card is in play. It is never
triggered and never resolved: when the rules need a value they ask, and every
card in play contributes. Recomputing on demand means the answer cannot drift
out of step with the board — a card leaving play stops mattering immediately,
with nothing to undo.
"""

from __future__ import annotations

from typing import Any

from fsme.cards import CardInstance, Static
from fsme.state import GameState

ATTACK = "attack"
"""Damage a player deals on a successful attack roll."""

MAX_HP = "max_hp"
"""A player's hit point maximum."""

ATTACKS = "attacks"
"""Attacks a player may declare per turn."""

LOOT_PLAYS = "loot_plays"
"""Loot cards a player may play per turn."""

STATS = (ATTACK, MAX_HP, ATTACKS, LOOT_PLAYS)


def cards_in_play(state: GameState) -> list[CardInstance]:
    """
    Every card whose statics currently count, in a fixed order.
    """
    cards: list[CardInstance] = []

    for player in state.players:
        if isinstance(player.character, CardInstance):
            cards.append(player.character)

        cards.extend(
            card for card in player.treasures.cards if isinstance(card, CardInstance)
        )

    cards.extend(
        card for card in state.active_monsters.cards if isinstance(card, CardInstance)
    )
    cards.extend(
        card for card in state.room_area.cards if isinstance(card, CardInstance)
    )

    return cards


def _applies_to(static: Static, source: CardInstance, player_id: int) -> bool:
    """
    Decide whether one card's static reaches one player.
    """
    if static.scope == "all_players":
        return True

    if source.controller is None:
        return False

    if static.scope == "opponents":
        return source.controller != player_id

    return source.controller == player_id


def bonus(state: GameState, stat: str, player_id: int) -> int:
    """
    Return the total modifier to a stat for one player.
    """
    total = 0

    for card in cards_in_play(state):
        for static in card.definition.statics:
            if static.stat != stat:
                continue

            if _applies_to(static, card, player_id):
                total += static.amount

    return total


def static_value(state: GameState, stat: str, player_id: int, base: int) -> int:
    """
    Return a base value with every applicable static applied.

    Nothing goes below zero: a stack of penalties reduces a number to nothing
    rather than turning it inside out.
    """
    return max(0, base + bonus(state, stat, player_id))


def refresh_derived(state: GameState) -> bool:
    """
    Bring stored player values back in line with the board.

    Hit point maxima are stored rather than computed, because effects read and
    write them. This is what keeps that store honest, and it runs with the
    State-Based Actions for the same reason they do: after every change,
    before anybody looks.
    """
    changed = False

    for player in state.players:
        base = _base_hp(player)
        maximum = max(1, base + bonus(state, MAX_HP, player.player_id))

        if player.max_hp != maximum:
            player.max_hp = maximum
            changed = True

        if player.hp > maximum:
            player.hp = maximum
            changed = True

    return changed


def _base_hp(player: Any) -> int:
    """
    A player's printed hit points, before anything modifies them.
    """
    character = player.character

    if isinstance(character, CardInstance) and character.definition.health:
        return int(character.definition.health)

    return int(player.max_hp)
