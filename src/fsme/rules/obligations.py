# src/fsme/rules/obligations.py

"""
Paying what a turn owes.

An obligation is recorded by a card and discharged by the rules: the engine
checks, when a player wants to stop, whether there is something they still have
to do and can still do. "If able" is the whole difficulty — a debt nobody can
pay is not a debt, and a turn that ends with one ends anyway.
"""

from __future__ import annotations

from typing import Any

from fsme.state import GameState, Obligation
from fsme.state.obligations import ATTACK

from .restrictions import ATTACK as ATTACK_ACTION
from .restrictions import forbidden_by


def owed_by(state: GameState, player_id: int) -> Obligation | None:
    """
    Return an obligation this player still has to pay and still can pay.
    """
    for obligation in state.turn.obligations:
        if obligation.player_id != player_id or obligation.remaining <= 0:
            continue

        if _payable(state, obligation):
            return obligation

    return None


def _payable(state: GameState, obligation: Obligation) -> bool:
    """
    Decide whether a player is able to do what they owe.
    """
    if obligation.action != ATTACK:
        return False

    player = state.player(obligation.player_id)

    if not player.alive or not player.can_attack():
        return False

    return any(_attackable(state, monster, obligation) for monster in _monsters(state))


def _monsters(state: GameState) -> list[Any]:
    return list(state.active_monsters.cards)


def _attackable(state: GameState, monster: Any, obligation: Obligation) -> bool:
    if not getattr(monster, "alive", False):
        return False

    if obligation.card_id is not None and obligation.card_id != monster.instance_id:
        return False

    return (
        forbidden_by(
            state, ATTACK_ACTION, player=obligation.player_id, card=monster
        )
        is None
    )


def pay(state: GameState, action: str, player_id: int, card: Any | None = None) -> None:
    """
    Record that a player has done something they owed.

    The oldest matching debt is paid first, and a debt paid down to nothing is
    forgotten rather than left at zero.
    """
    card_id = getattr(card, "instance_id", None)

    for obligation in state.turn.obligations:
        if not obligation.matches(action, player_id, card_id):
            continue

        obligation.remaining -= 1

        if obligation.remaining <= 0:
            state.turn.obligations.remove(obligation)

        return


def refuse_to_stop(state: GameState, player_id: int) -> str | None:
    """
    Return the reason a player may not stop yet, if there is one.
    """
    obligation = owed_by(state, player_id)

    if obligation is None:
        return None

    return f"this player must still {obligation.action} this turn"
