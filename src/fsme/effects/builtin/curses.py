# src/fsme/effects/builtin/curses.py

"""
Curse effects.

A curse is a card that lives on a player instead of on the table. Once
attached it is in play like an item: its triggers answer events and its
statics count. What ends it is written on the card, not in the engine.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fsme.content.vocabulary import WHOM
from fsme.events import EventType
from fsme.state import PlayerState

from ..context import EffectContext
from ..errors import EffectExecutionError
from ..registry import EffectRegistry


def _players(targets: Sequence[Any], effect: str) -> list[PlayerState]:
    players = [target for target in targets if isinstance(target, PlayerState)]

    if len(players) != len(targets):
        raise EffectExecutionError(f"'{effect}' expects player targets")

    return players


def attach_curse(
    ctx: EffectContext,
    targets: Sequence[Any],
    card: Any | None = None,
) -> int:
    """
    Put a curse on each target player.

    The curse is the card whose ability is resolving unless one is named, so a
    curse card does not have to be told which card it is.
    """
    curse = card if card is not None else ctx.source

    if curse is None:
        raise EffectExecutionError(
            "attach_curse needs a card; none was given and there is no source"
        )

    attached = 0

    for player in _players(targets, "attach_curse"):
        if curse in player.curses.cards:
            continue

        curse.owner = player.player_id
        curse.controller = player.player_id

        player.curses.add_top(curse)
        attached += 1

        ctx.emit(
            EventType.ON_ENTER,
            source=curse,
            controller=player.player_id,
            targets=[player],
        )

    return attached


def remove_curse(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Take curses off the players carrying them.
    """
    state = ctx.state
    removed = 0

    for curse in targets:
        for player in state.players:
            if curse not in player.curses.cards:
                continue

            player.curses.cards.remove(curse)
            state.loot_discard.add_top(curse)
            removed += 1

            ctx.emit(
                EventType.ON_LEAVE,
                source=curse,
                controller=player.player_id,
                targets=[player],
            )

            break

    return removed


def register(registry: EffectRegistry) -> None:
    """
    Register every curse effect.
    """
    registry.register(
        "attach_curse",
        attach_curse,
        needs_target=True,
        description="Put a curse on a player.",
        roles={"card": WHOM},
    )
    registry.register(
        "remove_curse",
        remove_curse,
        needs_target=True,
        description="Take a curse off a player.",
    )
