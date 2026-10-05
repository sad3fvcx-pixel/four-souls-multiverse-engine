# src/fsme/replay/digest.py

"""
Deterministic fingerprints of a game position.

A replay is verified by comparing what the engine reproduces against what was
recorded. That comparison needs a value that is identical for identical games
and different for different ones, computed the same way on any machine — so it
is built from gameplay facts in a fixed order, never from object identity,
memory addresses or dictionary iteration order.

There are two fingerprints. ``state_fingerprint`` — the one ``state_digest``
hashes, and the one every journal and recording holds — covers less of the
game than it claims to, so two different positions can share one; it is kept
exactly as it is, because records already written are checked against it.
``state_fingerprint_v2`` covers what the rules read. Nothing records or checks
it yet.
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Callable, Iterable, Mapping
from enum import Enum
from typing import Any

from fsme.cards import CardDefinition, CardInstance, SoulToken
from fsme.events import Event
from fsme.stack import StackItem
from fsme.state import (
    CardModifier,
    CombatState,
    DamageShield,
    GameState,
    MonsterSlot,
    Obligation,
    PendingDecision,
    PendingRoll,
    PlayerState,
    PriorityState,
    Promise,
    TemporaryModifier,
    TurnState,
    Watcher,
    Zone,
)


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


# ----------------------------------------------------------------------
# Version 2 — what the rules read
# ----------------------------------------------------------------------

INCLUDED: dict[type, tuple[str, ...]] = {
    GameState: (
        "started",
        "game_over",
        "winner",
        "turn",
        "players",
        "monster_area",
        "treasure_shop",
        "bonus_souls",
        "room_area",
        "loot_deck",
        "loot_discard",
        "monster_deck",
        "monster_discard",
        "treasure_deck",
        "treasure_discard",
        "room_deck",
        "room_discard",
        "stack",
        "events",
        "priority",
        "combat",
        "shields",
        "promises",
        "watchers",
        "modifiers",
        "pending_decision",
        "pending_roll",
        "skipped_players",
        "ids",
        "rng_state",
    ),
    PlayerState: (
        "player_id",
        "hp",
        "max_hp",
        "pennies",
        "alive",
        "counters",
        "attacks_left",
        "purchases_left",
        "additional_loot_plays",
        "loot_limit_lifted",
        "loot_played",
        "died_this_turn",
        "hp_before_lethal",
        "character",
        "hand",
        "treasures",
        "souls",
        "curses",
    ),
    # `definition` and `copy_of` are written as the identifier of the card they
    # name, never as the definition itself.
    CardInstance: (
        "instance_id",
        "definition",
        "owner",
        "controller",
        "hp",
        "tapped",
        "alive",
        "counters",
        "modifiers",
        "eternal",
        "copy_of",
        "copy_expires",
        "silenced_while",
        "recharge_skipped",
        "last_damaged_by",
    ),
    SoulToken: ("token_id",),
    Zone: ("cards",),
    MonsterSlot: ("cards",),
    TurnState: (
        "turn_number",
        "active_player",
        "phase",
        "loot_played",
        "attacks_declared",
        "extra_turn_for",
        "obligations",
        "triggers_fired",
        "monster_died",
        "attack_rolls",
    ),
    CombatState: (
        "attacker",
        "monster",
        "round_number",
        "settled_roll",
        "active",
        "stalled_rounds",
    ),
    PriorityState: ("holder", "passes", "is_open"),
    StackItem: (
        "kind",
        "label",
        "source",
        "controller",
        "targets",
        "ability",
        "event",
        "payload",
        "status",
        "cancellable",
        "stack_id",
        "order",
    ),
    Event: (
        "type",
        "source",
        "controller",
        "targets",
        "payload",
        "event_id",
        "sequence",
        "replacements_applied",
        "status",
    ),
    PendingRoll: ("roll_id", "sides", "natural", "value", "roller", "attack"),
    PendingDecision: (
        "decision_id",
        "player",
        "kind",
        "options",
        "minimum",
        "maximum",
        "bind",
        "chosen",
        "picked",
    ),
    Watcher: (
        "event",
        "controller",
        "source",
        "label",
        "conditions",
        "effects",
        "player_id",
        "uses",
        "duration",
        "waits",
        "fired",
    ),
    Promise: ("event", "changes", "player_id", "card_id", "when", "uses", "duration"),
    DamageShield: ("player_id", "amount", "label", "duration"),
    TemporaryModifier: ("stat", "amount", "player_id", "duration"),
    CardModifier: ("stat", "amount", "duration"),
    Obligation: ("player_id", "action", "card_id", "remaining"),
}
"""
What version 2 is made of, field by field, in the order it is written.

The fingerprint is built by walking these tuples, so a field is in it exactly
when it is named here.
"""

EXCLUDED: dict[tuple[type, str], str] = {
    (GameState, "active_monsters"): (
        "a view of monster_area, which is the source of truth and is included"
    ),
    (GameState, "seed"): (
        "fixed for the game; where the generator stands is included as rng_state"
    ),
    (GameState, "souls_to_win"): "configuration, fixed before the game starts",
    (GameState, "monster_slots"): "configuration, fixed before the game starts",
    (GameState, "shop_slots"): "configuration, fixed before the game starts",
    (GameState, "starting_coins"): "configuration, read once by start_game",
    (GameState, "starting_hand"): "configuration, read once by start_game",
    (PlayerState, "name"): "what the player is called, which no rule reads",
    (PlayerState, "starting_coins"): "configuration, read once by start_game",
    (PlayerState, "starting_hand"): "configuration, read once by start_game",
    (CardInstance, "zone"): (
        "a label the rules write and never read; where the card is, is said by "
        "the zone that holds it"
    ),
    (Zone, "zone_type"): "fixed when the zone is made; which zone it is, is its place",
    (TurnState, "priority_player"): (
        "written once when the game starts and never read; priority.holder is "
        "the live value"
    ),
    (TurnState, "stack_depth"): "no rule writes or reads it",
    (PendingRoll, "continuation"): (
        "the interpreter's own working inside an ability; what it does next "
        "shows in the state it leaves"
    ),
    (PendingDecision, "prompt"): "the question as it is shown, which no rule reads",
    (PendingDecision, "continuation"): (
        "the interpreter's own working inside an ability; what it does next "
        "shows in the state it leaves"
    ),
}
"""Every field version 2 leaves out, with the reason it may."""

_HIDDEN_ZONES = frozenset(
    {
        "loot_deck",
        "loot_discard",
        "monster_deck",
        "monster_discard",
        "treasure_deck",
        "treasure_discard",
        "room_deck",
        "room_discard",
    }
)
"""
The piles a card mostly sits in untouched, and hundreds of them at that.

A card in one is written as its identifier when nothing about it differs from a
card just made, and in full when anything does: a discard pile holds dead
monsters, tapped items and cards with counters on them, and a card that comes
back out comes back as it was.
"""


def _canon(value: Any) -> Any:
    """
    One value as plain, ordered data.

    Cards, players, stack objects, soul tokens and card definitions are written
    as what they are called and never followed, which is what keeps the walk
    finite. Anything this does not know is refused rather than guessed at: a
    fallback through ``repr`` would put a memory address into the fingerprint.
    """
    kind = type(value)

    if value is None or kind is str or kind is int or kind is bool or kind is float:
        return value

    if isinstance(value, CardInstance):
        return ("card", value.instance_id)

    if isinstance(value, PlayerState):
        return ("player", value.player_id)

    if isinstance(value, StackItem):
        return ("stack", value.stack_id)

    if isinstance(value, SoulToken):
        return ("token", value.token_id)

    if isinstance(value, CardDefinition):
        return ("definition", value.id)

    if isinstance(value, Enum):
        return _canon(value.value)

    if isinstance(value, bool):
        return bool(value)

    if isinstance(value, str):
        return str(value)

    if isinstance(value, int):
        return int(value)

    if isinstance(value, float):
        return float(value)

    if isinstance(value, Mapping):
        return (
            "map",
            tuple(
                sorted(
                    ((_canon(key), _canon(item)) for key, item in value.items()),
                    key=lambda pair: repr(pair[0]),
                )
            ),
        )

    if isinstance(value, (list, tuple)):
        return tuple(_canon(item) for item in value)

    if isinstance(value, (set, frozenset)):
        return ("set", tuple(sorted((_canon(item) for item in value), key=repr)))

    if kind in INCLUDED:
        return _record(value)

    if (
        dataclasses.is_dataclass(value)
        and not isinstance(value, type)
        and kind.__dataclass_params__.frozen
    ):
        return (kind.__name__,) + tuple(
            _canon(getattr(value, field.name)) for field in dataclasses.fields(value)
        )

    raise TypeError(
        f"a game position holds a {kind.__name__}, which the fingerprint does "
        f"not know how to write"
    )


_NOTHING_COUNTED = ("map", ())
"""How ``_canon`` writes an empty mapping, which is what most cards carry."""


def _card(card: Any) -> Any:
    """
    A card where it lies, in full.

    The fields of ``INCLUDED[CardInstance]``, in that order, written out one by
    one rather than walked: a position holds hundreds of cards, and looking each
    field up by name made the fingerprint several times slower than a game
    step. The tests hold this to the table, field by field.
    """
    if not isinstance(card, CardInstance):
        return _canon(card)

    copy_of = card.copy_of

    return (
        "CardInstance",
        card.instance_id,
        ("definition", card.definition.id),
        card.owner,
        card.controller,
        card.hp,
        card.tapped,
        card.alive,
        _canon(card.counters) if card.counters else _NOTHING_COUNTED,
        _canon(card.modifiers) if card.modifiers else (),
        card.eternal,
        None if copy_of is None else ("definition", copy_of.id),
        card.copy_expires,
        card.silenced_while,
        card.recharge_skipped,
        card.last_damaged_by,
    )


def _cards(zone: Any) -> tuple[Any, ...]:
    return tuple(_card(card) for card in zone.cards)


def _pile(zone: Any) -> tuple[Any, ...]:
    # A card is written as its identifier when every included field reads as
    # it does on a card just made: identity aside — ``instance_id`` and
    # ``definition`` — and with health read against what is printed, which is
    # where a new card takes it from. The test is written out here rather than
    # called once per card, because a pile is hundreds of cards and the call
    # cost more than the test; the tests hold it to ``INCLUDED[CardInstance]``.
    return tuple(
        card.instance_id
        if type(card) is CardInstance
        and card.hp == card.definition.health
        and card.owner is None
        and card.controller is None
        and not card.tapped
        and card.alive
        and not card.counters
        and not card.modifiers
        and not card.eternal
        and card.copy_of is None
        and not card.copy_expires
        and not card.silenced_while
        and not card.recharge_skipped
        and card.last_damaged_by is None
        else _card(card)
        for card in zone.cards
    )


def _rng(value: Any) -> Any:
    # The generator's state is a tuple of numbers already, and walking six
    # hundred of them one by one after every command would buy nothing.
    if value is None or type(value) is tuple:
        return value

    return _canon(value)


_WRITTEN_AS: dict[tuple[type, str], Callable[[Any], Any]] = {
    (GameState, "players"): lambda players: tuple(_record(one) for one in players),
    (GameState, "monster_area"): lambda slots: tuple(_cards(slot) for slot in slots),
    (GameState, "treasure_shop"): _cards,
    (GameState, "bonus_souls"): _cards,
    (GameState, "room_area"): _cards,
    **{(GameState, name): _pile for name in _HIDDEN_ZONES},
    (GameState, "stack"): lambda stack: tuple(_record(item) for item in stack),
    (GameState, "events"): lambda events: tuple(_record(event) for event in events),
    (GameState, "ids"): lambda ids: ids.counter,
    (GameState, "rng_state"): _rng,
    (PlayerState, "character"): _card,
    (PlayerState, "hand"): _cards,
    (PlayerState, "treasures"): _cards,
    (PlayerState, "souls"): _cards,
    (PlayerState, "curses"): _cards,
    (StackItem, "event"): lambda event: None if event is None else _record(event),
    (Zone, "cards"): lambda cards: tuple(_card(card) for card in cards),
    (MonsterSlot, "cards"): lambda cards: tuple(_card(card) for card in cards),
}
"""
The fields that hold something rather than point at it.

A player's hand holds its cards, so they are written in full; the same cards
named in a stack object's targets are only pointed at.
"""


def _record(value: Any) -> tuple[Any, ...]:
    kind = type(value)

    return (kind.__name__,) + tuple(
        (
            written(getattr(value, name))
            if (written := _WRITTEN_AS.get((kind, name))) is not None
            else _canon(getattr(value, name))
        )
        for name in INCLUDED[kind]
    )


def state_fingerprint_v2(state: GameState) -> tuple[Any, ...]:
    """
    The version 2 summary: every field in ``INCLUDED``, in that order.
    """
    return (2,) + _record(state)
