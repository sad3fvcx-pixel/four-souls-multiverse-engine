# src/fsme/effects/builtin/modifiers.py

"""
Card state modifiers.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fsme.events import EventType
from fsme.state import (
    CardModifier,
    Duration,
    Obligation,
    PlayerState,
    TemporaryModifier,
)
from fsme.state.modifiers import MONSTER_STATS, STATS

from ..context import EffectContext
from ..errors import EffectExecutionError
from ..registry import EffectRegistry


def add_modifier(
    ctx: EffectContext,
    targets: Sequence[Any],
    stat: str = "",
    amount: int = 1,
    duration: str = str(Duration.END_OF_TURN),
) -> int:
    """
    Give players a bonus that outlives the card granting it.

    "+1 attack till end of turn" belongs to nobody once the loot card is in the
    discard pile, so the bonus is recorded on the game itself and the turn is
    what takes it away.

    A hit point bonus raises the player's hit points as well as their maximum.
    The engine stores hit points remaining rather than damage taken, so raising
    only the maximum would give a hurt player nothing until they healed — which
    is not what a card that says "+2 HP" does.
    """
    if not stat:
        raise EffectExecutionError("add_modifier requires a stat")

    if stat not in STATS and stat not in MONSTER_STATS:
        raise EffectExecutionError(
            f"unknown stat '{stat}'; the stats are "
            f"{', '.join(sorted(set(STATS) | set(MONSTER_STATS)))}"
        )

    try:
        lifetime = Duration(duration)
    except ValueError:
        raise EffectExecutionError(f"unknown duration '{duration}'") from None

    granted = 0

    for player in targets:
        if not isinstance(player, PlayerState):
            # A monster is not a player and has no seat, so its bonus lives on
            # the card itself. Everything else about the effect is the same.
            if not hasattr(player, "modifiers"):
                raise EffectExecutionError(
                    "add_modifier expects a player or a card"
                )

            player.modifiers.append(
                CardModifier(stat=stat, amount=int(amount), duration=lifetime)
            )

            granted += 1

            ctx.emit(
                EventType.STAT_MODIFIED,
                source=player,
                stat=stat,
                amount=int(amount),
                duration=str(lifetime),
            )

            continue

        ctx.state.modifiers.append(
            TemporaryModifier(
                stat=stat,
                amount=int(amount),
                player_id=player.player_id,
                duration=lifetime,
            )
        )

        _apply_now(player, stat, int(amount))

        granted += 1

        ctx.emit(
            EventType.STAT_MODIFIED,
            controller=player.player_id,
            targets=[player],
            stat=stat,
            amount=int(amount),
            duration=str(lifetime),
        )

    return granted


def _apply_now(player: PlayerState, stat: str, amount: int) -> None:
    """
    Change what a bonus cannot change by being merely recorded.

    Attack and roll bonuses are read when they are needed, so recording them is
    enough. A player's remaining attacks and loot plays were counted out at the
    start of the turn and will not be counted again, and hit points are stored;
    those have to be handed over now.
    """
    if stat == "max_hp" and amount > 0:
        player.max_hp += amount
        player.hp += amount

    elif stat == "attacks":
        player.attacks_left = max(0, player.attacks_left + amount)

    elif stat == "loot_plays":
        player.additional_loot_plays = max(
            0, player.additional_loot_plays + amount
        )


def take_extra_turn(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Promise a player another turn after this one.

    Only one extra turn is outstanding at a time: a second promise replaces the
    first rather than stacking, because the turn that grants it is the turn that
    pays it, and there is only one of those.
    """
    granted = 0

    for player in targets:
        if not isinstance(player, PlayerState):
            raise EffectExecutionError("take_extra_turn expects player targets")

        ctx.state.turn.extra_turn_for = player.player_id
        granted += 1

    return granted


def expand_slots(
    ctx: EffectContext,
    targets: Sequence[Any],
    area: str = "monster",
    amount: int = 1,
) -> int:
    """
    Make room for another monster or another item for sale.

    The number of slots belongs to the game rather than to the rules, because
    cards change it and a saved game has to reload with the change intact. The
    new slot fills itself the next time the rules top the area up.
    """
    state = ctx.state

    if area == "monster":
        state.monster_slots = max(0, state.monster_slots + int(amount))
    elif area == "shop":
        state.shop_slots = max(0, state.shop_slots + int(amount))
    else:
        raise EffectExecutionError(
            f"unknown area '{area}'; use 'monster' or 'shop'"
        )

    return int(amount)


def skip_next_turn(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Take a player's next turn away from them.
    """
    skipped = 0

    for player in targets:
        if not isinstance(player, PlayerState):
            raise EffectExecutionError("skip_next_turn expects player targets")

        ctx.state.skipped_players.append(player.player_id)
        skipped += 1

    return skipped


def _cards(targets: Sequence[Any], effect: str) -> list[Any]:
    for target in targets:
        if not hasattr(target, "tapped"):
            raise EffectExecutionError(f"'{effect}' expects card targets")

    return list(targets)


def recharge(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Untap items so they may be activated again.
    """
    recharged = 0

    for card in _cards(targets, "recharge"):
        if not card.tapped:
            continue

        card.tapped = False
        recharged += 1

        ctx.emit(
            EventType.TREASURE_CHARGED,
            controller=card.controller,
            targets=[card],
        )

    return recharged


def deactivate(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Tap items so they may not be activated again this turn.
    """
    deactivated = 0

    for card in _cards(targets, "deactivate"):
        if card.tapped:
            continue

        card.tapped = True
        deactivated += 1

        ctx.emit(
            EventType.TREASURE_DEACTIVATED,
            controller=card.controller,
            targets=[card],
        )

    return deactivated


def add_counter(
    ctx: EffectContext,
    targets: Sequence[Any],
    counter: str = "",
    amount: int = 1,
    silences: bool = False,
) -> int:
    """
    Change a named counter on target cards.

    ``silences`` is for the counters that do more than count: a card carrying
    one has no abilities while it is there, which is what a poo counter is.
    """
    if not counter:
        raise EffectExecutionError("add_counter requires a counter name")

    for card in _cards(targets, "add_counter"):
        card.counters[counter] = card.counters.get(counter, 0) + amount

        if silences:
            # The counter is what silences the card, so the card watches for
            # this counter and speaks again when it is gone.
            card.silenced_while = counter

    return amount


def require_attack(
    ctx: EffectContext,
    targets: Sequence[Any],
    times: int = 1,
    who: Any = None,
) -> int:
    """
    Make a player owe an attack this turn.

    The engine allows and forbids; this is the third thing cards ask for. A
    target names what must be attacked — "the active player must attack that
    monster this turn" — and no target means any monster will do, which is what
    an extra attack owed after a monster dies means.

    "If able" is not written here. Whether the debt can be paid is asked when
    the player tries to stop, because by then the board may have changed.
    """
    if times < 1:
        raise EffectExecutionError("require_attack times must be at least one")

    state = ctx.state

    player_id = int(who) if who is not None else state.turn.active_player

    if not 0 <= player_id < len(state.players):
        return 0

    monsters = [card for card in targets if hasattr(card, "instance_id")]

    if targets and not monsters:
        raise EffectExecutionError("require_attack expects monster targets")

    for monster in monsters or [None]:
        state.turn.obligations.append(
            Obligation(
                player_id=player_id,
                card_id=None if monster is None else str(monster.instance_id),
                remaining=int(times),
            )
        )

    return len(monsters) or 1


def lift_limit(
    ctx: EffectContext,
    targets: Sequence[Any],
    what: str = "loot_plays",
) -> int:
    """
    Let a player do something as often as they like this turn.

    A card that says "any number" is not asking for a bigger allowance, and
    writing one in would be a guess about how big. The limit is lifted instead,
    and the turn puts it back.
    """
    if what != "loot_plays":
        raise EffectExecutionError(
            f"there is no limit called '{what}' to lift; loot_plays is the one"
        )

    lifted = 0

    for player in targets:
        if not isinstance(player, PlayerState):
            raise EffectExecutionError("lift_limit expects player targets")

        player.loot_limit_lifted = True
        lifted += 1

    return lifted


def make_eternal(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Make particular cards beyond destroying.

    Eternal is usually printed, and printed things belong to the definition
    every copy shares. This is granted to one card in one game, so it is kept
    on the card in play.
    """
    granted = 0

    for card in _cards(targets, "make_eternal"):
        card.eternal = True
        granted += 1

    return granted


def hold_tapped(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Keep tapped items from waking up at their controller's next turn.

    A tapped item recharges by rule, and this is the card that says one of them
    does not. Nothing else about it changes: it is still tapped, still in play,
    and still recharged by anything that recharges it on purpose.
    """
    held = 0

    for card in _cards(targets, "hold_tapped"):
        card.recharge_skipped = True
        held += 1

    return held


def register(registry: EffectRegistry) -> None:
    """
    Register every card modifier effect.
    """
    registry.register(
        "recharge", recharge, needs_target=True, description="Untap an item."
    )
    registry.register(
        "deactivate", deactivate, needs_target=True, description="Tap an item."
    )
    registry.register(
        "add_counter",
        add_counter,
        needs_target=True,
        primary="counter",
        description="Change a counter on a card.",
    )
    registry.register(
        "take_extra_turn",
        take_extra_turn,
        needs_target=True,
        description="Give a player another turn after this one.",
    )
    registry.register(
        "expand_slots",
        expand_slots,
        primary="area",
        description="Add a monster slot or a shop slot.",
    )
    registry.register(
        "skip_next_turn",
        skip_next_turn,
        needs_target=True,
        description="Take away a player's next turn.",
    )
    registry.register(
        "require_attack",
        require_attack,
        primary="times",
        description="Make a player owe an attack this turn.",
    )
    registry.register(
        "hold_tapped",
        hold_tapped,
        needs_target=True,
        description="Keep an item from recharging at its next turn.",
    )
    registry.register(
        "make_eternal",
        make_eternal,
        needs_target=True,
        description="Make a card in play eternal.",
    )
    registry.register(
        "lift_limit",
        lift_limit,
        needs_target=True,
        primary="what",
        description="Let a player act as often as they like this turn.",
    )
    registry.register(
        "add_modifier",
        add_modifier,
        needs_target=True,
        primary="stat",
        description="Give a player a bonus that lasts beyond its card.",
    )
