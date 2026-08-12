# src/fsme/effects/builtin/damage.py

"""
Health effects.

Death is never applied here. An effect reduces hit points and announces what
happened; killing a player or a monster is a State-Based Action performed by
the Runtime after the stack finishes resolving, exactly as ABILITY_RESOLUTION.md
requires.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fsme.events import EventType
from fsme.state import PlayerState

from ..context import EffectContext
from ..errors import EffectExecutionError
from ..registry import EffectRegistry


def _controller_of(target: Any) -> int | None:
    if isinstance(target, PlayerState):
        return target.player_id

    return getattr(target, "controller", None)


def _attribute(target: Any, actor: int | None) -> None:
    """
    Remember who damaged a card, so its reward can find them later.
    """
    if actor is not None and hasattr(target, "last_damaged_by"):
        target.last_damaged_by = actor


def _hit_points(target: Any) -> int:
    hp = getattr(target, "hp", None)

    if hp is None:
        raise EffectExecutionError(
            f"target {target!r} has no hit points"
        )

    return int(hp)


def deal_damage(ctx: EffectContext, targets: Sequence[Any], amount: int = 1) -> int:
    """
    Deal damage to players or monsters.
    """
    if amount < 0:
        raise EffectExecutionError("deal_damage amount must be non-negative")

    dealt = 0

    for target in targets:
        proposal = ctx.propose(
            EventType.BEFORE_DAMAGE,
            controller=_controller_of(target),
            targets=[target],
            amount=amount,
            actor=ctx.actor,
        )

        if proposal.cancelled:
            continue

        incoming = max(0, int(proposal.get("amount", amount)))

        if incoming == 0:
            continue

        before = _hit_points(target)
        after = max(0, before - incoming)

        target.hp = after
        dealt += before - after

        _attribute(target, ctx.actor)

        ctx.emit(
            EventType.DAMAGE_DEALT,
            controller=_controller_of(target),
            targets=[target],
            amount=before - after,
            remaining_hp=after,
            actor=ctx.actor,
        )
        ctx.emit(
            EventType.AFTER_DAMAGE,
            controller=_controller_of(target),
            targets=[target],
            amount=before - after,
        )

    return dealt


def heal(ctx: EffectContext, targets: Sequence[Any], amount: int = 1) -> int:
    """
    Restore hit points, never above the target's maximum.
    """
    if amount < 0:
        raise EffectExecutionError("heal amount must be non-negative")

    healed = 0

    for target in targets:
        proposal = ctx.propose(
            EventType.BEFORE_HEAL,
            controller=_controller_of(target),
            targets=[target],
            amount=amount,
        )

        if proposal.cancelled:
            continue

        amount = max(0, int(proposal.get("amount", amount)))

        before = _hit_points(target)
        maximum = int(getattr(target, "max_hp", before + amount))
        after = min(maximum, before + amount)

        target.hp = after
        healed += after - before

        ctx.emit(
            EventType.HEALED,
            controller=_controller_of(target),
            targets=[target],
            amount=after - before,
        )

    return healed


def kill(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Reduce targets to zero hit points.

    The resulting death is detected by State-Based Actions.
    """
    killed = 0

    for target in targets:
        before = _hit_points(target)

        if before == 0:
            continue

        target.hp = 0
        killed += 1

        _attribute(target, ctx.actor)

        ctx.emit(
            EventType.DAMAGE_DEALT,
            controller=_controller_of(target),
            targets=[target],
            amount=before,
            remaining_hp=0,
            lethal=True,
            actor=ctx.actor,
        )

    return killed


def revive(ctx: EffectContext, targets: Sequence[Any], hp: int = 1) -> int:
    """
    Return dead players to the game.
    """
    if hp <= 0:
        raise EffectExecutionError("revive hp must be positive")

    revived = 0

    for target in targets:
        if not isinstance(target, PlayerState):
            raise EffectExecutionError("revive expects player targets")

        if target.alive:
            continue

        target.revive(hp)
        revived += 1

        ctx.emit(
            EventType.PLAYER_REVIVED,
            controller=target.player_id,
            targets=[target],
            hp=target.hp,
        )

    return revived


def register(registry: EffectRegistry) -> None:
    """
    Register every health effect.
    """
    registry.register(
        "deal_damage",
        deal_damage,
        uses_stack=True,
        needs_target=True,
        primary="amount",
        description="Deal damage to a player or monster.",
    )
    registry.register(
        "heal", heal, needs_target=True, primary="amount", description="Restore hit points."
    )
    registry.register(
        "kill", kill, needs_target=True, description="Reduce a target to zero hit points."
    )
    registry.register(
        "revive",
        revive,
        needs_target=True,
        primary="hp",
        description="Return a dead player to play."
    )
