# src/fsme/rules/counters.py

"""
Counting how often an ability has answered its trigger this turn.

Some cards care not that something happened but how often: "the first time you
take damage each turn", "every other time this takes damage each turn". Nothing
in the game state records that by itself — an event knows it happened, not how
many like it came before — so the turn keeps the tally, and this module is the
one place that decides what a tally is counted against.
"""

from __future__ import annotations

from typing import Any

from fsme.state import GameState


def trigger_key(card: Any, ability: Any) -> str:
    """
    Name the tally an ability keeps.

    Two copies of a card count separately, and two abilities on one card count
    separately, so the key is made of both. Abilities are compared by value, so
    a card with two identical abilities shares one tally — which is what "this
    card has done it once already" means anyway.
    """
    abilities = getattr(getattr(card, "definition", None), "abilities", ())

    try:
        index = list(abilities).index(ability)
    except ValueError:
        index = 0

    return f"{getattr(card, 'instance_id', '?')}:{index}"


def record_trigger(state: GameState, card: Any, ability: Any) -> int:
    """
    Count one more occurrence and return which one it is.

    Counting happens when the trigger matches, before the ability's conditions
    are asked anything: a card that only acts the first time still watched the
    other times go by.
    """
    key = trigger_key(card, ability)
    counted = state.turn.triggers_fired.get(key, 0) + 1

    state.turn.triggers_fired[key] = counted

    return counted


def times_this_turn(state: GameState, card: Any, ability: Any) -> int:
    """
    How often this ability has answered its trigger so far this turn.
    """
    return state.turn.triggers_fired.get(trigger_key(card, ability), 0)
