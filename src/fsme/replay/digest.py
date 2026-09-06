# src/fsme/replay/digest.py

"""
Deterministic fingerprints of a game position.

A replay is verified by comparing what the engine reproduces against what was
recorded. That comparison needs a value that is identical for identical games
and different for different ones, computed the same way on any machine — so it
is built from gameplay facts in a fixed order, never from object identity,
memory addresses or dictionary iteration order.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Any

from fsme.state import GameState


def _card_fingerprint(card: Any) -> tuple[Any, ...]:
    return (
        getattr(card, "instance_id", ""),
        getattr(card, "id", ""),
        getattr(card, "hp", None),
        getattr(card, "alive", None),
        getattr(card, "tapped", None),
        getattr(card, "owner", None),
        getattr(card, "controller", None),
    )


def _zone_fingerprint(cards: Iterable[Any]) -> tuple[Any, ...]:
    return tuple(_card_fingerprint(card) for card in cards)


def state_fingerprint(state: GameState) -> tuple[Any, ...]:
    """
    Return an ordered, comparable summary of everything gameplay depends on.
    """
    players = tuple(
        (
            player.player_id,
            player.hp,
            player.max_hp,
            player.pennies,
            player.alive,
            tuple(sorted(player.counters.items())),
            player.attacks_left,
            player.purchases_left,
            player.additional_loot_plays,
            _zone_fingerprint(player.hand.cards),
            _zone_fingerprint(player.treasures.cards),
            len(player.souls),
        )
        for player in state.players
    )

    return (
        state.started,
        state.game_over,
        state.winner,
        state.turn.turn_number,
        state.turn.active_player,
        str(state.turn.phase),
        state.turn.loot_played,
        state.turn.attacks_declared,
        players,
        _zone_fingerprint(state.active_monsters.cards),
        _zone_fingerprint(state.treasure_shop.cards),
        len(state.loot_deck),
        len(state.loot_discard),
        len(state.monster_deck),
        len(state.monster_discard),
        len(state.treasure_deck),
        len(state.treasure_discard),
        len(state.stack),
        len(state.events),
        state.ids.counter,
        state.combat.attacker,
        state.combat.round_number,
        state.combat.active,
        state.priority.holder,
        state.priority.passes,
        state.priority.is_open,
        state.pending_decision.decision_id if state.pending_decision else "",
        repr(state.rng_state),
    )


def state_digest(state: GameState) -> str:
    """
    Return a short hexadecimal digest of a game position.
    """
    return hashlib.sha256(
        repr(state_fingerprint(state)).encode("utf-8")
    ).hexdigest()[:32]
