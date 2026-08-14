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


def _kind_of(target: Any) -> str:
    """
    What a damage event is about, in one word.

    Cards distinguish "damage to a monster" from "damage to a player", and the
    only thing that knows which is the thing being damaged.
    """
    return "player" if isinstance(target, PlayerState) else "monster"


def _hit_points(target: Any) -> int:
    hp = getattr(target, "hp", None)

    if hp is None:
        raise EffectExecutionError(
            f"target {target!r} has no hit points"
        )

    return int(hp)


def deal_damage(
    ctx: EffectContext,
    targets: Sequence[Any],
    amount: int = 1,
    combat: bool = False,
    dealt_by: Any | None = None,
    roll: int | None = None,
) -> int:
    """
    Deal damage to players or monsters.

    Damage carries who dealt it and whether it was combat damage. Cards
    distinguish both — "each time this deals combat damage" is neither "each
    time this is damaged" nor "each time anybody is damaged" — and only the
    thing dealing it knows.
    """
    if amount < 0:
        raise EffectExecutionError("deal_damage amount must be non-negative")

    dealt = 0

    for target in targets:
        if isinstance(target, PlayerState):
            # Remembered before it is lost: a death that is prevented gives
            # back the health the blow found.
            target.hp_before_lethal = target.hp

        proposal = ctx.propose(
            EventType.BEFORE_DAMAGE,
            source=dealt_by,
            controller=_controller_of(target),
            targets=[target],
            target_kind=_kind_of(target),
            amount=amount,
            actor=ctx.actor,
            combat=combat,
            roll=roll,
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
            source=dealt_by,
            controller=_controller_of(target),
            targets=[target],
            target_kind=_kind_of(target),
            amount=before - after,
            remaining_hp=after,
            actor=ctx.actor,
            combat=combat,
            roll=roll,
        )
        ctx.emit(
            EventType.AFTER_DAMAGE,
            source=dealt_by,
            controller=_controller_of(target),
            targets=[target],
            target_kind=_kind_of(target),
            amount=before - after,
            combat=combat,
            roll=roll,
        )

    return dealt


def divide_damage(
    ctx: EffectContext,
    targets: Sequence[Any],
    each: int = 1,
    dealt_by: Any | None = None,
) -> int:
    """
    Deal damage split among the things the player picked.

    "2 damage divided as they choose to any number of monsters or players" is
    two picks, and picking the same thing twice is not two instances of one
    damage — it is one instance of two. So the picks are counted first and each
    target is damaged once, for as much as it was given.
    """
    if each < 0:
        raise EffectExecutionError("divide_damage each must be non-negative")

    shares: list[tuple[Any, int]] = []

    for target in targets:
        for index, (chosen, amount) in enumerate(shares):
            if chosen is target:
                shares[index] = (chosen, amount + each)
                break
        else:
            shares.append((target, each))

    dealt = 0

    for target, amount in shares:
        dealt += deal_damage(ctx, [target], amount=amount, dealt_by=dealt_by)

    return dealt


def heal(
    ctx: EffectContext,
    targets: Sequence[Any],
    amount: int = 1,
    full: bool = False,
) -> int:
    """
    Restore hit points, never above the target's maximum.

    ``full`` is what a card means by "heal to full HP": not a number of hearts
    but all of them, however hurt the target turned out to be.
    """
    if amount < 0:
        raise EffectExecutionError("heal amount must be non-negative")

    healed = 0

    for target in targets:
        wanted = (
            max(0, int(getattr(target, "max_hp", 0)) - _hit_points(target))
            if full
            else amount
        )

        proposal = ctx.propose(
            EventType.BEFORE_HEAL,
            controller=_controller_of(target),
            targets=[target],
            amount=wanted,
        )

        if proposal.cancelled:
            continue

        amount = max(0, int(proposal.get("amount", wanted)))

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

        if isinstance(target, PlayerState):
            target.hp_before_lethal = before

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


def discard_monsters(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Send monsters away without defeating them.

    Nobody killed them, so nobody is paid: souls and rewards belong to whoever
    beats a monster, and a monster swept off the table was not beaten. The empty
    slots are refilled by the rules, the same way they are after a kill.
    """
    state = ctx.state
    discarded = 0

    for monster in targets:
        if monster not in state.active_monsters.cards:
            continue

        state.active_monsters.cards.remove(monster)
        state.monster_discard.add_top(monster)
        discarded += 1

        ctx.emit(
            EventType.ON_LEAVE,
            source=monster,
            targets=[monster],
        )

    return discarded


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
        "divide_damage",
        divide_damage,
        needs_target=True,
        primary="each",
        description="Deal damage split among the things chosen.",
    )
    registry.register(
        "heal", heal, needs_target=True, primary="amount", description="Restore hit points."
    )
    registry.register(
        "kill", kill, needs_target=True, description="Reduce a target to zero hit points."
    )
    registry.register(
        "discard_monsters",
        discard_monsters,
        needs_target=True,
        description="Put monsters into the discard pile undefeated.",
    )
    registry.register(
        "revive",
        revive,
        needs_target=True,
        primary="hp",
        description="Return a dead player to play."
    )
