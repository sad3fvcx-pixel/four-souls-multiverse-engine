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
from fsme.runtime.ability_context import AbilityContext
from fsme.runtime.condition_evaluator import ConditionEvaluator
from fsme.state import GameState, TemporaryModifier
from fsme.state.modifiers import (
    ATTACK,
    ATTACKS,
    LOOT_PLAYS,
    MAX_HP,
    ROLL,
    STATS,
)

_CONDITIONS = ConditionEvaluator()
"""
One evaluator, built once.

It holds no game state — only the table of condition implementations — so
sharing it is safe and rebuilding it for every value read would be waste.
"""

__all__ = [
    "ATTACK",
    "ATTACKS",
    "LOOT_PLAYS",
    "MAX_HP",
    "ROLL",
    "STATS",
    "bonus",
    "cards_in_play",
    "expire_turn_modifiers",
    "refresh_derived",
    "static_value",
]


def cards_in_play(state: GameState) -> list[CardInstance]:
    """
    Every card that is in play, in a fixed order.

    This is the engine's single answer to "what is on the table": triggered
    abilities and static modifiers both read it, so a card cannot be live for
    one and dead for the other. A character, an item, a curse afflicting a
    player, an active monster and the current room are all in play; a card in
    hand, in a deck or in a discard pile is not.
    """
    cards: list[CardInstance] = []

    for player in state.players:
        if isinstance(player.character, CardInstance):
            cards.append(player.character)

        cards.extend(
            card for card in player.treasures.cards if isinstance(card, CardInstance)
        )
        cards.extend(
            card for card in player.curses.cards if isinstance(card, CardInstance)
        )

    cards.extend(
        card for card in state.active_monsters.cards if isinstance(card, CardInstance)
    )
    cards.extend(
        card for card in state.room_area.cards if isinstance(card, CardInstance)
    )

    return cards


def _applies_to(
    static: Static,
    source: CardInstance,
    player_id: int,
    state: GameState,
) -> bool:
    """
    Decide whether one card's static reaches one player right now.
    """
    if not _in_scope(static, source, player_id):
        return False

    if not static.conditions:
        return True

    return _CONDITIONS.evaluate_all(
        static.conditions,
        state,
        AbilityContext(
            source=source,
            controller=player_id,
            owner=source.owner,
        ),
    )


def _in_scope(static: Static, source: CardInstance, player_id: int) -> bool:
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

    Printed statics and temporary bonuses are added up together, because they
    are the same thing to whoever is asking: a card that says "you have +1
    attack" and a card that says "+1 attack till end of turn" must not be able
    to disagree about what a player's attack is.
    """
    total = 0

    for card in cards_in_play(state):
        for static in card.definition.statics:
            if static.stat != stat:
                continue

            if _applies_to(static, card, player_id, state):
                total += static.amount

    for modifier in state.modifiers:
        if modifier.stat == stat and modifier.player_id == player_id:
            total += modifier.amount

    return total


def expire_turn_modifiers(state: GameState) -> list[TemporaryModifier]:
    """
    Drop every modifier that only lasted for the turn, and return them.

    A hit point bonus is the one that cannot simply be forgotten. The engine
    stores hit points remaining rather than damage taken, so a player who gained
    +2 HP and then took two damage looks unhurt; letting the bonus lapse without
    lowering their hit points would heal them. Taking the bonus back off keeps
    the damage where it was — and a player whose damage now exceeds their
    maximum dies, which is what the rules say happens.
    """
    expired = [modifier for modifier in state.modifiers if modifier.expires_at_end_of_turn()]

    if not expired:
        return []

    state.modifiers = [
        modifier for modifier in state.modifiers if not modifier.expires_at_end_of_turn()
    ]

    for modifier in expired:
        if modifier.stat != MAX_HP or modifier.amount <= 0:
            continue

        player = state.player(modifier.player_id)
        player.hp = max(0, player.hp - modifier.amount)

    refresh_derived(state)

    return expired


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
