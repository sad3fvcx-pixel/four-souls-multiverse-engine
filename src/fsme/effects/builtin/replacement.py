# src/fsme/effects/builtin/replacement.py

"""
Effects that edit an event instead of changing the game.

These only make sense inside a replacement ability, where the engine has
offered an event for editing before it happens. Outside that window there is
nothing to edit, and they say so rather than silently doing nothing.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from fsme.events import EventType
from fsme.state import DamageShield, Duration, Promise, Watcher
from fsme.state.promises import CHANGES

from ..context import EffectContext
from ..errors import EffectExecutionError
from ..registry import EffectRegistry


def _open_event(ctx: EffectContext, effect: str) -> Any:
    event = ctx.event

    if event is None:
        raise EffectExecutionError(
            f"'{effect}' may only be used by a replacement ability"
        )

    return event


def prevent_damage(
    ctx: EffectContext,
    targets: Sequence[Any],
    amount: int = 1,
) -> int:
    """
    Reduce the damage an event is about to deal.

    Preventing everything cancels the event outright, so nothing is recorded
    as having dealt zero damage.
    """
    if amount < 0:
        raise EffectExecutionError("prevent_damage amount must be non-negative")

    event = _open_event(ctx, "prevent_damage")

    before = int(event.get("amount", 0))
    after = max(0, before - amount)

    event.set("amount", after)

    if after == 0:
        event.cancel()

    return before - after


def prevent_next_damage(
    ctx: EffectContext,
    targets: Sequence[Any],
    amount: int | None = None,
    label: str = "",
) -> int:
    """
    Promise that the next damage a player takes will be reduced.

    This is the other kind of prevention. ``prevent_damage`` edits damage that
    is happening now; this one is written on a card played before the damage
    exists, so it is recorded on the game and spent by the first instance of
    damage that arrives.

    Leaving ``amount`` out prevents the whole instance, however large: that is
    what "prevent the next instance of damage" says, and it is not the same card
    as "prevent the next 1 damage".
    """
    if amount is not None and amount < 0:
        raise EffectExecutionError("prevent_next_damage amount must be non-negative")

    promised = 0

    for player in targets:
        player_id = getattr(player, "player_id", None)

        if player_id is None:
            raise EffectExecutionError("prevent_next_damage expects player targets")

        ctx.state.shields.append(
            DamageShield(
                player_id=int(player_id),
                amount=None if amount is None else int(amount),
                label=str(label),
            )
        )

        promised += 1

    return promised



def promise(
    ctx: EffectContext,
    targets: Sequence[Any],
    event: str = "",
    changes: Any = None,
    uses: int = 1,
    unlimited: bool = False,
) -> int:
    """
    Owe a change to an event that has not happened yet.

    "The next time a player would loot, they loot from the discard pile
    instead" is a replacement written on a card that will be tapped and done
    long before anybody loots. So the change is recorded on the game and kept
    when the event arrives, exactly as a promised prevention is.

    With no target the promise is about nobody in particular, which is what
    "a player" means when the card does not say which. Targets narrow it: a
    player, or a monster, or anything else an event can be about.

    ``unlimited`` is the difference between "the next time" and "each time till
    end of turn"; both are printed on cards, and they are not the same promise.
    """
    if not event:
        raise EffectExecutionError("promise requires an event to wait for")

    if str(event) not in {str(known) for known in EventType}:
        raise EffectExecutionError(f"promise cannot wait for unknown event '{event}'")

    if not isinstance(changes, Mapping) or not changes:
        raise EffectExecutionError("promise requires the changes it owes")

    for key, change in changes.items():
        if not isinstance(change, Mapping) or not set(change) <= set(CHANGES):
            raise EffectExecutionError(
                f"promise cannot change '{key}' by {change!r}; "
                f"a change is one of {', '.join(CHANGES)}"
            )

    owed = {
        str(key): {str(name): value for name, value in change.items()}
        for key, change in changes.items()
    }

    subjects: list[Promise] = []

    if not targets:
        subjects.append(Promise(event=str(event), changes=dict(owed)))

    for target in targets:
        player_id = getattr(target, "player_id", None)

        subjects.append(
            Promise(
                event=str(event),
                changes=dict(owed),
                player_id=None if player_id is None else int(player_id),
                card_id=(
                    None
                    if player_id is not None
                    else str(getattr(target, "instance_id", ""))
                ),
            )
        )

    for made in subjects:
        made.uses = None if unlimited else int(uses)
        made.duration = Duration.END_OF_TURN

        ctx.state.promises.append(made)

    return len(subjects)


def watch_for(
    ctx: EffectContext,
    targets: Sequence[Any],
    event: str = "",
    effects: Any = None,
    conditions: Any = None,
    uses: int = 1,
    unlimited: bool = False,
    mine: bool = False,
    waits: bool = False,
) -> int:
    """
    Wait for an event that has not happened yet, and act when it does.

    This is a promise's other half. A promise edits the event it was waiting
    for; this resolves an ability because of it, on the stack, where it can ask
    questions and be responded to like any other triggered ability.

    ``mine`` narrows it to the controller's own events: "the next time *you*
    would loot" is not the next time anybody would.
    """
    if not event:
        raise EffectExecutionError("watch_for requires an event to wait for")

    if str(event) not in {str(known) for known in EventType}:
        raise EffectExecutionError(f"watch_for cannot wait for unknown event '{event}'")

    if not isinstance(effects, (list, tuple)) or not effects:
        raise EffectExecutionError("watch_for requires the effects it will run")

    watching = Watcher(
        event=str(event),
        controller=ctx.actor,
        source=ctx.source,
        label=f"{getattr(ctx.source, 'id', 'watcher')}:{event}",
        conditions=tuple(conditions or ()),
        effects=tuple(effects),
        player_id=ctx.actor if mine else None,
        uses=None if unlimited else int(uses),
        duration=Duration.END_OF_TURN,
        waits=bool(waits),
    )

    ctx.state.watchers.append(watching)

    return 1


def cancel_event(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> bool:
    """
    Stop the event from happening at all.
    """
    _open_event(ctx, "cancel_event").cancel()

    return True


def modify_event(
    ctx: EffectContext,
    targets: Sequence[Any],
    key: str = "",
    value: Any = None,
    delta: int | None = None,
    factor: int | None = None,
) -> Any:
    """
    Change one value carried by the event.

    ``delta`` shifts a number, ``factor`` multiplies it — "damage this deals is
    doubled" — and ``value`` replaces it outright.
    """
    if not key:
        raise EffectExecutionError("modify_event requires a key")

    event = _open_event(ctx, "modify_event")

    if delta is not None:
        event.set(key, int(event.get(key, 0)) + int(delta))
    elif factor is not None:
        event.set(key, int(event.get(key, 0)) * int(factor))
    else:
        event.set(key, value)

    return event.get(key)


def register(registry: EffectRegistry) -> None:
    """
    Register every replacement effect.
    """
    registry.register(
        "prevent_damage",
        prevent_damage,
        primary="amount",
        description="Reduce incoming damage before it lands.",
    )
    registry.register(
        "prevent_next_damage",
        prevent_next_damage,
        needs_target=True,
        primary="amount",
        description="Promise to reduce the next damage a player takes.",
    )
    registry.register(
        "promise",
        promise,
        needs_target=False,
        primary="event",
        literal=("changes",),
        description="Owe a change to the next event of a kind.",
    )
    registry.register(
        "watch_for",
        watch_for,
        needs_target=False,
        primary="event",
        literal=("effects", "conditions"),
        description="Wait for an event and resolve an ability when it happens.",
    )
    registry.register(
        "cancel_event",
        cancel_event,
        description="Stop the event being replaced from happening.",
    )
    registry.register(
        "modify_event",
        modify_event,
        primary="key",
        description="Change a value carried by the event being replaced.",
    )
