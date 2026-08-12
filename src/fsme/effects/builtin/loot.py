# src/fsme/effects/builtin/loot.py

"""
Loot and soul effects.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fsme.cards import SoulToken
from fsme.events import EventType
from fsme.state import GameState, PlayerState

from ..context import EffectContext
from ..errors import EffectExecutionError
from ..registry import EffectRegistry


def _players(targets: Sequence[Any], effect: str) -> list[PlayerState]:
    players = [target for target in targets if isinstance(target, PlayerState)]

    if len(players) != len(targets):
        raise EffectExecutionError(f"'{effect}' expects player targets")

    return players


def _refill_loot_deck(ctx: EffectContext, state: GameState) -> bool:
    """
    Shuffle the discard pile back into the loot deck.

    Returns False when there is nothing left to reshuffle, which lets the
    caller stop drawing instead of raising: running out of cards is a legal
    game situation, not an engine error.
    """
    if not state.loot_discard.cards:
        return False

    state.loot_deck.cards.extend(state.loot_discard.cards)
    state.loot_discard.clear()

    ctx.rng.shuffle(state.loot_deck.cards)

    return True


def draw_loot(ctx: EffectContext, targets: Sequence[Any], count: int = 1) -> int:
    """
    Draw loot cards into each target player's hand.
    """
    if count < 0:
        raise EffectExecutionError("draw_loot count must be non-negative")

    state = ctx.state
    drawn = 0

    for player in _players(targets, "draw_loot"):
        for _ in range(count):
            if not state.loot_deck.cards and not _refill_loot_deck(ctx, state):
                break

            card = state.loot_deck.draw()
            player.hand.add_top(card)
            drawn += 1

            ctx.emit(
                EventType.LOOT_DRAWN,
                controller=player.player_id,
                targets=[player],
                card=card,
            )

    return drawn


def discard_loot(ctx: EffectContext, targets: Sequence[Any], count: int = 1) -> int:
    """
    Discard loot cards from the top of each target player's hand.
    """
    if count < 0:
        raise EffectExecutionError("discard_loot count must be non-negative")

    state = ctx.state
    discarded = 0

    for player in _players(targets, "discard_loot"):
        for _ in range(count):
            if not player.hand.cards:
                break

            card = player.hand.draw()
            state.loot_discard.add_top(card)
            discarded += 1

            ctx.emit(
                EventType.LOOT_DISCARDED,
                controller=player.player_id,
                targets=[player],
                card=card,
            )

    return discarded


def gain_soul(
    ctx: EffectContext,
    targets: Sequence[Any],
    count: int = 1,
    card: Any | None = None,
) -> int:
    """
    Give souls to each target player.

    When a card is supplied it becomes the soul, which is how a killed monster
    or a bonus soul card is awarded. Otherwise the engine mints soul tokens.
    """
    if count < 0:
        raise EffectExecutionError("gain_soul count must be non-negative")

    gained = 0

    for player in _players(targets, "gain_soul"):
        for _ in range(count):
            soul = card if card is not None else SoulToken(
                token_id=ctx.state.ids.allocate("soul")
            )

            player.souls.add_top(soul)
            gained += 1

            ctx.emit(
                EventType.SOUL_GAINED,
                controller=player.player_id,
                targets=[player],
                soul=soul,
            )

    return gained


def lose_soul(ctx: EffectContext, targets: Sequence[Any], count: int = 1) -> int:
    """
    Remove souls from each target player.
    """
    if count < 0:
        raise EffectExecutionError("lose_soul count must be non-negative")

    lost = 0

    for player in _players(targets, "lose_soul"):
        for _ in range(count):
            if not player.souls.cards:
                break

            soul = player.souls.draw()
            lost += 1

            ctx.emit(
                EventType.SOUL_LOST,
                controller=player.player_id,
                targets=[player],
                soul=soul,
            )

    return lost


def register(registry: EffectRegistry) -> None:
    """
    Register every loot and soul effect.
    """
    registry.register(
        "draw_loot",
        draw_loot,
        needs_target=True,
        primary="count",
        description="Draw loot cards."
    )
    registry.register(
        "discard_loot",
        discard_loot,
        needs_target=True,
        primary="count",
        description="Discard loot cards.",
    )
    registry.register(
        "gain_soul",
        gain_soul,
        needs_target=True,
        primary="count",
        description="Gain souls."
    )
    registry.register(
        "lose_soul",
        lose_soul,
        needs_target=True,
        primary="count",
        description="Lose souls."
    )
