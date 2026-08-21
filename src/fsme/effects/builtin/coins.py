# src/fsme/effects/builtin/coins.py

"""
Economy effects.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fsme.events import EventType
from fsme.state import PlayerState

from ..context import EffectContext
from ..errors import EffectExecutionError
from ..registry import EffectRegistry


def _players(targets: Sequence[Any], effect: str) -> list[PlayerState]:
    """
    Narrow a target list to players.
    """
    players = [target for target in targets if isinstance(target, PlayerState)]

    if len(players) != len(targets):
        raise EffectExecutionError(f"'{effect}' expects player targets")

    return players


def gain_coins(ctx: EffectContext, targets: Sequence[Any], amount: int = 1) -> int:
    """
    Add coins to every target player.

    A gain is offered for replacement before it happens, the way damage is. A
    card that says "if you would gain any number of cents, gain that much +1
    instead" has to be able to change the number before the player has it, and
    the amount is settled per player: two players gaining from one card may have
    different cards of their own to say so.
    """
    if amount < 0:
        raise EffectExecutionError("gain_coins amount must be non-negative")

    gained = 0

    for player in _players(targets, "gain_coins"):
        proposal = ctx.propose(
            EventType.BEFORE_COINS_GAINED,
            controller=player.player_id,
            targets=[player],
            amount=amount,
        )

        if proposal.cancelled:
            continue

        granted = max(0, int(proposal.get("amount", amount)))

        player.pennies += granted
        gained = max(gained, granted)

        ctx.emit(
            EventType.COINS_GAINED,
            controller=player.player_id,
            targets=[player],
            amount=granted,
        )

    return gained


def lose_coins(ctx: EffectContext, targets: Sequence[Any], amount: int = 1) -> int:
    """
    Remove coins from every target player.

    A player never goes below zero; the amount actually lost is returned.
    """
    if amount < 0:
        raise EffectExecutionError("lose_coins amount must be non-negative")

    lost = 0

    for player in _players(targets, "lose_coins"):
        taken = min(player.pennies, amount)
        player.pennies -= taken
        lost += taken

        ctx.emit(
            EventType.COINS_LOST,
            controller=player.player_id,
            targets=[player],
            amount=taken,
        )

    return lost


def set_coins(ctx: EffectContext, targets: Sequence[Any], amount: int = 0) -> int:
    """
    Set the coin total of every target player.
    """
    if amount < 0:
        raise EffectExecutionError("set_coins amount must be non-negative")

    for player in _players(targets, "set_coins"):
        previous = player.pennies
        player.pennies = amount

        event_type = (
            EventType.COINS_GAINED if amount >= previous else EventType.COINS_LOST
        )

        ctx.emit(
            event_type,
            controller=player.player_id,
            targets=[player],
            amount=abs(amount - previous),
        )

    return amount


def transfer_coins(
    ctx: EffectContext,
    targets: Sequence[Any],
    amount: int = 1,
    source_player: int | None = None,
) -> int:
    """
    Move coins from one player to the targets.

    Nobody to take from is not an error. "Steal 1¢ from another player" in a
    two-player game whose other player is dead names nobody, and the rules pass
    over an instruction that cannot be carried out — the same reading
    ``give_treasure`` takes when the recipient turns out not to exist.

    What that costs is worth stating: an ability whose author simply forgot to
    name a source now does nothing quietly instead of raising. That check was
    only ever a runtime one, firing in whichever game happened to reach the
    card, so it was a poor guard against a mistake in the content and a real
    obstacle to a card that legitimately finds nobody to rob.
    """
    if source_player is None or not 0 <= int(source_player) < len(ctx.state.players):
        return 0

    giver = ctx.state.player(source_player)
    receivers = _players(targets, "transfer_coins")

    moved = 0

    for receiver in receivers:
        taken = min(giver.pennies, amount)

        if taken == 0:
            continue

        giver.pennies -= taken
        receiver.pennies += taken
        moved += taken

        ctx.emit(
            EventType.COINS_LOST,
            controller=giver.player_id,
            targets=[giver],
            amount=taken,
        )
        ctx.emit(
            EventType.COINS_GAINED,
            controller=receiver.player_id,
            targets=[receiver],
            amount=taken,
        )

    return moved


def register(registry: EffectRegistry) -> None:
    """
    Register every economy effect.
    """
    registry.register(
        "gain_coins",
        gain_coins,
        needs_target=True,
        primary="amount",
        description="Add coins to a player.",
        least={"amount": 0},
        asks={
            "amount": "how many cents",
        },
    )
    registry.register(
        "lose_coins",
        lose_coins,
        needs_target=True,
        primary="amount",
        description="Remove coins from a player.",
        least={"amount": 0},
        asks={
            "amount": "how many cents",
        },
    )
    registry.register(
        "set_coins",
        set_coins,
        needs_target=True,
        primary="amount",
        description="Set a player's coins.",
        least={"amount": 0},
    )
    registry.register(
        "transfer_coins",
        transfer_coins,
        needs_target=True,
        primary="amount",
        description="Move coins between players.",
    )
