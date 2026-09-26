# src/fsme/serialization/game_save.py

"""
Saving and restoring a game in progress.

SAVE_SYSTEM.md asks for a save that is lossless, deterministic and versioned:
loading one must produce a game that continues exactly as the saved one would
have. That rules out saving object graphs. Every card is written down once, in
the zone that holds it, and everything else that points at a card — the stack,
the events waiting in the queue, the attack in progress, a promise made about
one — points at it by its identifier instead.

What is deliberately not saved is an ability caught in the middle of running:
the queue of operations it had left, and where in that queue it had got to.
That is not data the game has written down anywhere; it is the interpreter's
own working, rebuilt from the card each time an ability resolves. A game
suspended inside an ability is therefore refused rather than saved wrongly,
and the caller is told why.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any

from fsme import __version__
from fsme.cards import (
    Ability,
    CardInstance,
    CardRegistry,
    SoulToken,
    UnknownCardError,
)
from fsme.events import Event, EventStatus, EventType
from fsme.stack import StackItem, StackItemStatus, StackItemType
from fsme.state import (
    CardModifier,
    DamageShield,
    DecisionKind,
    Duration,
    GamePhase,
    GameState,
    MonsterSlot,
    Obligation,
    PendingDecision,
    PendingRoll,
    PlayerState,
    Promise,
    TemporaryModifier,
    Watcher,
    Zone,
    ZoneType,
)
from fsme.util.errors import EngineError

SAVE_FORMAT_VERSION = "1"
"""
The shape of a save file.

A save written by one version of this format is only loadable by an engine that
knows that version, which is what stops a half-understood file from becoming a
half-restored game.
"""

CARD = "$card"
PLAYER = "$player"
TOKEN = "$token"

GLOBAL_ZONES = (
    "loot_deck",
    "loot_discard",
    "monster_deck",
    "monster_discard",
    "treasure_deck",
    "treasure_discard",
    "treasure_shop",
    "bonus_souls",
    "room_deck",
    "room_discard",
    "room_area",
)

PLAYER_ZONES = ("hand", "treasures", "souls", "curses")


class SaveError(EngineError):
    """
    A game could not be saved, or a save could not be loaded.
    """


# ----------------------------------------------------------------------
# Writing
# ----------------------------------------------------------------------


def save_game(
    state: GameState,
    *,
    engine_version: str | None = None,
    rng_state: Any = None,
) -> dict[str, Any]:
    """
    Write a game out as plain data.

    ``engine_version`` left out is the engine writing the file, the same
    version every journal and recording is stamped with. Anything passed is
    written exactly as given, an empty string included.

    ``rng_state`` is the live generator's position, which is not kept in
    GameState while a game is running: the Runtime owns the generator, and a
    save that forgot it would reload into a game that rolls different dice.
    """
    _refuse_if_mid_ability(state)

    return {
        "format": SAVE_FORMAT_VERSION,
        "engine": __version__ if engine_version is None else engine_version,
        "seed": state.seed,
        "rng": _plain(rng_state if rng_state is not None else state.rng_state),
        "started": state.started,
        "game_over": state.game_over,
        "winner": state.winner,
        "souls_to_win": state.souls_to_win,
        "monster_slots": state.monster_slots,
        "shop_slots": state.shop_slots,
        "starting_coins": state.starting_coins,
        "starting_hand": state.starting_hand,
        "skipped_players": list(state.skipped_players),
        "ids": state.ids.counter,
        "turn": _save_turn(state),
        "priority": {
            "holder": state.priority.holder,
            "passes": state.priority.passes,
            "is_open": state.priority.is_open,
        },
        "combat": {
            "attacker": state.combat.attacker,
            "monster": _ref(state.combat.monster),
            "round_number": state.combat.round_number,
            "settled_roll": state.combat.settled_roll,
            "active": state.combat.active,
        },
        "players": [_save_player(player) for player in state.players],
        "zones": {name: _save_zone(getattr(state, name)) for name in GLOBAL_ZONES},
        "monster_area": [
            [_save_card(card) for card in slot.cards] for slot in state.monster_area
        ],
        "stack": [_save_stack_item(item) for item in state.stack],
        "events": [_save_event(event) for event in state.events],
        "shields": [
            {
                "player_id": shield.player_id,
                "amount": shield.amount,
                "label": shield.label,
                "duration": str(shield.duration),
            }
            for shield in state.shields
        ],
        "modifiers": [
            {
                "stat": modifier.stat,
                "amount": modifier.amount,
                "player_id": modifier.player_id,
                "duration": str(modifier.duration),
            }
            for modifier in state.modifiers
        ],
        "promises": [
            {
                "event": promise.event,
                "changes": _plain(promise.changes),
                "player_id": promise.player_id,
                "card_id": promise.card_id,
                "when": _plain(promise.when),
                "uses": promise.uses,
                "duration": str(promise.duration),
            }
            for promise in state.promises
        ],
        "watchers": [
            {
                "event": watcher.event,
                "controller": watcher.controller,
                "source": _ref(watcher.source),
                "label": watcher.label,
                "conditions": _plain(watcher.conditions),
                "effects": _plain(watcher.effects),
                "player_id": watcher.player_id,
                "uses": watcher.uses,
                "duration": str(watcher.duration),
                "waits": watcher.waits,
                "fired": list(watcher.fired),
            }
            for watcher in state.watchers
        ],
        "pending_decision": _save_decision(state.pending_decision),
        "pending_roll": _save_roll(state.pending_roll),
    }


def _refuse_if_mid_ability(state: GameState) -> None:
    """
    Refuse to save a game that is suspended inside an ability.
    """
    waiting = state.pending_decision

    if waiting is not None and waiting.continuation is not None:
        raise SaveError(
            "this game is waiting inside an ability and cannot be saved yet; "
            "answer the question first, then save"
        )

    rolling = state.pending_roll

    if rolling is not None and rolling.continuation is not None:
        raise SaveError(
            "this game is waiting on a roll inside an ability and cannot be "
            "saved yet; settle the roll first, then save"
        )


def _save_turn(state: GameState) -> dict[str, Any]:
    turn = state.turn

    return {
        "turn_number": turn.turn_number,
        "active_player": turn.active_player,
        "priority_player": turn.priority_player,
        "phase": str(turn.phase),
        "stack_depth": turn.stack_depth,
        "loot_played": turn.loot_played,
        "attacks_declared": turn.attacks_declared,
        "extra_turn_for": turn.extra_turn_for,
        "attack_rolls": turn.attack_rolls,
        "monster_died": turn.monster_died,
        "triggers_fired": dict(turn.triggers_fired),
        "obligations": [
            {
                "player_id": owed.player_id,
                "action": owed.action,
                "card_id": owed.card_id,
                "remaining": owed.remaining,
            }
            for owed in turn.obligations
        ],
    }


def _save_player(player: PlayerState) -> dict[str, Any]:
    saved: dict[str, Any] = {
        "player_id": player.player_id,
        "name": player.name,
        "hp": player.hp,
        "max_hp": player.max_hp,
        "pennies": player.pennies,
        "counters": dict(player.counters),
        "attacks_left": player.attacks_left,
        "purchases_left": player.purchases_left,
        "additional_loot_plays": player.additional_loot_plays,
        "loot_limit_lifted": player.loot_limit_lifted,
        "loot_played": player.loot_played,
        "alive": player.alive,
        "died_this_turn": player.died_this_turn,
        "hp_before_lethal": player.hp_before_lethal,
        "starting_coins": player.starting_coins,
        "starting_hand": player.starting_hand,
        "character": _save_card(player.character) if player.character else None,
    }

    for name in PLAYER_ZONES:
        saved[name] = _save_zone(getattr(player, name))

    return saved


def _save_zone(zone: Zone[Any]) -> dict[str, Any]:
    return {
        "type": str(zone.zone_type),
        "cards": [_save_card(card) for card in zone.cards],
    }


def _save_card(card: Any) -> dict[str, Any]:
    """
    Write a card down where it lies, with everything that has happened to it.
    """
    if isinstance(card, SoulToken):
        return {"token": card.token_id}

    if not isinstance(card, CardInstance):
        raise SaveError(f"cannot save {card!r}: it is not a card")

    return {
        "id": card.definition.id,
        "instance_id": card.instance_id,
        "owner": card.owner,
        "controller": card.controller,
        "zone": card.zone,
        "hp": card.hp,
        "tapped": card.tapped,
        "alive": card.alive,
        "last_damaged_by": card.last_damaged_by,
        "counters": dict(card.counters),
        "modifiers": [
            {
                "stat": modifier.stat,
                "amount": modifier.amount,
                "duration": str(modifier.duration),
            }
            for modifier in card.modifiers
        ],
        "copy_of": card.copy_of.id if card.copy_of is not None else None,
        "copy_expires": card.copy_expires,
        "eternal": card.eternal,
        "silenced_while": card.silenced_while,
        "recharge_skipped": card.recharge_skipped,
    }


def _save_stack_item(item: StackItem) -> dict[str, Any]:
    return {
        "kind": str(item.kind),
        "label": item.label,
        "source": _ref(item.source),
        "ability": _save_ability(item.ability),
        "controller": item.controller,
        "targets": [_ref(target) for target in item.targets],
        "event": _save_event(item.event) if item.event is not None else None,
        "status": str(item.status),
    }


def _save_ability(ability: Any) -> dict[str, Any] | None:
    """
    Write an ability down as the data it is.

    An ability on the stack usually belongs to a card, but not always: the
    engine builds one to make a player discard down to the hand limit. Saving
    the data rather than a reference covers both without asking where it came
    from.
    """
    if ability is None:
        return None

    if not isinstance(ability, Ability):
        raise SaveError(f"cannot save {ability!r}: it is not an ability")

    return {
        "trigger": ability.trigger,
        "conditions": _plain(ability.conditions),
        "targets": _plain(ability.targets),
        "effects": _plain(ability.effects),
        "optional": ability.optional,
        "cost": _plain(ability.cost),
        "replacement": ability.replacement,
        "scope": ability.scope,
        "description": ability.description,
    }


def _save_event(event: Event) -> dict[str, Any]:
    return {
        "type": str(event.type),
        "source": _ref(event.source),
        "controller": event.controller,
        "targets": [_ref(target) for target in event.targets],
        "payload": _plain(event.payload),
        "event_id": event.event_id,
        "sequence": event.sequence,
        "replacements_applied": list(event.replacements_applied),
        "status": str(event.status),
    }


def _save_decision(decision: PendingDecision | None) -> dict[str, Any] | None:
    if decision is None:
        return None

    return {
        "decision_id": decision.decision_id,
        "player": decision.player,
        "kind": str(decision.kind),
        "options": [_ref(option) for option in decision.options],
        "minimum": decision.minimum,
        "maximum": decision.maximum,
        "bind": decision.bind,
        "prompt": decision.prompt,
        "chosen": _plain(decision.chosen),
    }


def _save_roll(roll: PendingRoll | None) -> dict[str, Any] | None:
    if roll is None:
        return None

    return {
        "roll_id": roll.roll_id,
        "sides": roll.sides,
        "natural": roll.natural,
        "value": roll.value,
        "roller": roll.roller,
        "attack": roll.attack,
    }


def _ref(value: Any) -> Any:
    """
    Point at something rather than copying it.
    """
    if value is None:
        return None

    if isinstance(value, CardInstance):
        return {CARD: value.instance_id}

    if isinstance(value, PlayerState):
        return {PLAYER: value.player_id}

    if isinstance(value, SoulToken):
        return {TOKEN: value.token_id}

    return _plain(value)


def _plain(value: Any) -> Any:
    """
    Reduce a value to something a save file can hold.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, (CardInstance, PlayerState, SoulToken)):
        return _ref(value)

    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(item) for item in value]

    if isinstance(value, StackItem):
        raise SaveError(
            "a stack object was found inside an event or a decision; the save "
            "format points at cards and players, not at pending work"
        )

    return str(value)


# ----------------------------------------------------------------------
# Reading
# ----------------------------------------------------------------------


def load_game(data: Mapping[str, Any], cards: CardRegistry) -> GameState:
    """
    Rebuild a game from what was written down.

    The card registry supplies the printed side of every card: a save holds
    what happened to a card, not what is on it, so a game reloads against the
    content it was played with.
    """
    if not isinstance(data, Mapping):
        raise SaveError("a save must be an object")

    written = str(data.get("format", ""))

    if written != SAVE_FORMAT_VERSION:
        raise SaveError(
            f"this save is in format '{written}', and this engine reads "
            f"format '{SAVE_FORMAT_VERSION}'"
        )

    state = GameState(seed=_integer(data, "seed", 0))

    state.rng_state = _tuples(data.get("rng"))
    state.started = _flag(data, "started", False)

    # Before the start nothing has rolled, and no state means the one the seed
    # gives. After it the generator may have rolled or may not have, and the
    # save says nothing else about which - a game in progress that does not
    # hold the state would reload into another game.
    if state.started and state.rng_state is None:
        raise SaveError(
            "this save is of a game in progress and holds no random generator "
            "state"
        )

    state.game_over = _flag(data, "game_over", False)
    state.winner = data.get("winner")
    state.souls_to_win = _integer(data, "souls_to_win", 4)
    state.monster_slots = _integer(data, "monster_slots", 2)
    state.shop_slots = _integer(data, "shop_slots", 2)

    # Read with a default rather than required, and the format is not bumped
    # for them. A save is taken from a game in progress, and these two are read
    # by `start_game` and by nothing after it — so a save written before they
    # existed reloads into exactly the game it was.
    state.starting_coins = _integer(data, "starting_coins", 3)
    state.starting_hand = _integer(data, "starting_hand", 3)

    state.skipped_players = [
        _whole(seat, "skipped_players") for seat in _listing(data, "skipped_players")
    ]

    try:
        state.ids.restore(_integer(data, "ids", 0))
    except ValueError as error:
        raise SaveError(f"this save cannot restore its identifiers: {error}") from error

    index: dict[str, Any] = {}

    zones = _section(data, "zones")

    for name in GLOBAL_ZONES:
        saved = _maybe_section(zones, name)

        if saved is not None:
            _load_zone(getattr(state, name), saved, cards, index)

    _load_monster_area(state, _listing(data, "monster_area"), cards, index)

    for saved_player in _entries(data, "players"):
        state.add_player(_load_player(saved_player, cards, index))

    _load_turn(state, _section(data, "turn"), index)
    _check_seats(state)

    priority = _section(data, "priority")

    holder = priority.get("holder")
    state.priority.holder = None if holder is None else _whole(holder, "holder")
    state.priority.passes = _integer(priority, "passes", 0)
    state.priority.is_open = _flag(priority, "is_open", False)
    _check_priority(state)

    combat = _section(data, "combat")

    state.combat.attacker = combat.get("attacker")
    state.combat.monster = _resolve(combat.get("monster"), state, index)
    state.combat.round_number = _integer(combat, "round_number", 0)
    state.combat.settled_roll = combat.get("settled_roll")
    state.combat.active = _flag(combat, "active", False)

    for saved_item in _entries(data, "stack"):
        state.stack.push(_load_stack_item(saved_item, state, index))

    for saved_event in _entries(data, "events"):
        state.events.push(_load_event(saved_event, state, index))

    state.shields = [
        DamageShield(
            player_id=_integer(saved, "player_id"),
            amount=saved.get("amount"),
            label=str(saved.get("label", "")),
            duration=_duration(saved),
        )
        for saved in _entries(data, "shields")
    ]

    state.modifiers = [
        TemporaryModifier(
            stat=str(_needed(saved, "stat")),
            amount=_integer(saved, "amount"),
            player_id=_integer(saved, "player_id"),
            duration=_duration(saved),
        )
        for saved in _entries(data, "modifiers")
    ]

    state.promises = [
        Promise(
            event=str(_needed(saved, "event")),
            changes=dict(_section(saved, "changes")),
            player_id=saved.get("player_id"),
            card_id=saved.get("card_id"),
            when=dict(_section(saved, "when")),
            uses=saved.get("uses"),
            duration=_duration(saved),
        )
        for saved in _entries(data, "promises")
    ]

    state.watchers = [
        Watcher(
            event=str(_needed(saved, "event")),
            controller=saved.get("controller"),
            source=_resolve(saved.get("source"), state, index),
            label=str(saved.get("label", "")),
            conditions=tuple(_listing(saved, "conditions")),
            effects=tuple(_listing(saved, "effects")),
            player_id=saved.get("player_id"),
            uses=saved.get("uses"),
            duration=_duration(saved),
            waits=_flag(saved, "waits", False),
            fired=list(_listing(saved, "fired")),
        )
        for saved in _entries(data, "watchers")
    ]

    saved_decision = _maybe_section(data, "pending_decision")

    if saved_decision is not None:
        state.pending_decision = PendingDecision(
            decision_id=str(_needed(saved_decision, "decision_id")),
            player=_integer(saved_decision, "player"),
            kind=_member(DecisionKind, _needed(saved_decision, "kind"), "decision"),
            options=[
                _resolve(option, state, index)
                for option in _listing(saved_decision, "options")
            ],
            minimum=_integer(saved_decision, "minimum", 1),
            maximum=_integer(saved_decision, "maximum", 1),
            bind=str(saved_decision.get("bind", "chosen")),
            prompt=str(saved_decision.get("prompt", "")),
        )

    saved_roll = _maybe_section(data, "pending_roll")

    if saved_roll is not None:
        state.pending_roll = PendingRoll(
            roll_id=str(_needed(saved_roll, "roll_id")),
            sides=_integer(saved_roll, "sides"),
            natural=_integer(saved_roll, "natural"),
            value=_integer(saved_roll, "value"),
            roller=saved_roll.get("roller"),
            attack=_flag(saved_roll, "attack", False),
        )

    _relink_copies(index, cards)

    return state


def _load_player(
    saved: Mapping[str, Any],
    cards: CardRegistry,
    index: dict[str, Any],
) -> PlayerState:
    player = PlayerState(
        player_id=_integer(saved, "player_id"),
        name=str(saved.get("name", "")),
        hp=_integer(saved, "hp", 0),
        max_hp=_integer(saved, "max_hp", 0),
        pennies=_integer(saved, "pennies", 0),
        counters={
            str(key): _whole(value, "counters")
            for key, value in _section(saved, "counters").items()
        },
        attacks_left=_integer(saved, "attacks_left", 0),
        purchases_left=_integer(saved, "purchases_left", 0),
        additional_loot_plays=_integer(saved, "additional_loot_plays", 0),
        loot_played=_integer(saved, "loot_played", 0),
        alive=_flag(saved, "alive", True),
    )

    player.loot_limit_lifted = _flag(saved, "loot_limit_lifted", False)
    player.died_this_turn = _flag(saved, "died_this_turn", False)
    player.hp_before_lethal = _integer(saved, "hp_before_lethal", 0)

    # Absent in a save written before a seat could be dealt its own opening,
    # and absent in every ordinary game since. `None` is the right answer to
    # both, so the format is not bumped for them.
    opening = saved.get("starting_coins")
    player.starting_coins = (
        None if opening is None else _whole(opening, "starting_coins")
    )

    hand = saved.get("starting_hand")
    player.starting_hand = None if hand is None else _whole(hand, "starting_hand")

    character = _maybe_section(saved, "character")

    if character is not None:
        player.character = _load_card(character, cards, index)

    for name in PLAYER_ZONES:
        written = _maybe_section(saved, name)

        if written is not None:
            _load_zone(getattr(player, name), written, cards, index)

    return player


def _load_zone(
    zone: Zone[Any],
    saved: Mapping[str, Any],
    cards: CardRegistry,
    index: dict[str, Any],
) -> None:
    zone.zone_type = _by_name(saved.get("type"), ZoneType, zone.zone_type, "zone")
    zone.cards.clear()

    for written in _entries(saved, "cards"):
        zone.cards.append(_load_card(written, cards, index))


def _load_monster_area(
    state: GameState,
    saved: Any,
    cards: CardRegistry,
    index: dict[str, Any],
) -> None:
    """
    Rebuild the row of slots, and the face-up view over it.

    The slots are what is written down: which monster is standing on which
    other one is part of the position, and a save that kept only the face-up
    cards would reload a board with the buried monsters gone.
    """
    from fsme.rules.slots import sync

    state.monster_area.clear()

    for written in saved:
        if not isinstance(written, (list, tuple)):
            raise SaveError(f"this save holds {written!r} for a monster slot")

        state.monster_area.append(
            MonsterSlot(
                cards=[
                    _load_card(_object(card, "monster_area"), cards, index)
                    for card in written
                ]
            )
        )

    sync(state)


def _flag(saved: Mapping[str, Any], key: str, default: bool) -> bool:
    """
    Read a yes-or-no back, or its default when the save does not hold it.

    The writer only ever puts true or false here, so anything else is refused
    rather than guessed at: read as Python reads it, the text "false" is true,
    and a game written as not over would reload over. A number is refused too,
    though Python counts true and false as one and zero — a save is JSON, and
    JSON keeps the two apart.

    A field that is missing keeps its default, as it always did: that is how a
    save written before the field existed still loads.
    """
    if key not in saved:
        return default

    value = saved[key]

    if not isinstance(value, bool):
        raise SaveError(
            f"this save holds {value!r} for '{key}', which can only be true or false"
        )

    return value


def _needed(saved: Mapping[str, Any], key: str) -> Any:
    """
    A field the save cannot be read without.
    """
    if key not in saved:
        raise SaveError(f"this save is missing '{key}'")

    return saved[key]


def _whole(value: Any, key: str) -> int:
    """
    A whole number, exactly as JSON writes one.

    The writer only ever puts a whole number here. Read as Python reads it, 3.7
    is quietly 3, the text "3" is 3 and true is 1 — each a guess about a file
    somebody else wrote, so each is refused. Whether the number makes sense
    for the field is not asked here: a modifier may take one away.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise SaveError(
            f"this save holds {value!r} for '{key}', which can only be a whole number"
        )

    return value


def _integer(saved: Mapping[str, Any], key: str, default: int | None = None) -> int:
    """
    Read a whole number back, or its default when the save does not hold it.

    With no default the field is required, and a save without it is refused.
    """
    if key not in saved:
        if default is None:
            raise SaveError(f"this save is missing '{key}'")

        return default

    return _whole(saved[key], key)


def _object(value: Any, key: str) -> Mapping[str, Any]:
    """
    Something the save holds as an object, checked to be one.
    """
    if not isinstance(value, Mapping):
        raise SaveError(
            f"this save holds {value!r} for '{key}', which should be an object"
        )

    return value


def _section(saved: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """
    An object inside the save, empty when the save does not hold it.
    """
    return _object(saved.get(key, {}), key)


def _maybe_section(saved: Mapping[str, Any], key: str) -> Mapping[str, Any] | None:
    """
    An object inside the save that may be absent, or written down as nothing.
    """
    value = saved.get(key)

    return None if value is None else _object(value, key)


def _listing(saved: Mapping[str, Any], key: str) -> Sequence[Any]:
    """
    A list inside the save, empty when the save does not hold it.

    A text is refused rather than read letter by letter.
    """
    value = saved.get(key, ())

    if not isinstance(value, (list, tuple)):
        raise SaveError(
            f"this save holds {value!r} for '{key}', which should be a list"
        )

    return value


def _entries(saved: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    """
    A list of objects inside the save, each checked to be one.
    """
    return [_object(entry, key) for entry in _listing(saved, key)]


def _member[E: Enum](kind: type[E], written: Any, what: str) -> E:
    """
    Read an enumeration back from the value it was written under.
    """
    try:
        return kind(written)
    except ValueError as error:
        raise SaveError(f"this save holds an unknown {what}: {written!r}") from error


def _duration(saved: Mapping[str, Any]) -> Duration:
    """
    How long something lasts, until the end of the turn when the save is silent.
    """
    return _member(Duration, saved.get("duration", Duration.END_OF_TURN), "duration")


def _by_name(written: Any, choices: Any, fallback: Any, what: str) -> Any:
    """
    Read a numbered enumeration back from the name it was written under.

    Zones and phases are numbered rather than named, and a save holding the
    number would be a save nobody could read — nor one that survives a
    renumbering. The name goes in the file and is looked up again here.
    """
    if not written:
        return fallback

    for choice in choices:
        if str(choice) == str(written):
            return choice

    raise SaveError(f"this save holds an unknown {what}: '{written}'")


def _load_card(
    saved: Mapping[str, Any],
    cards: CardRegistry,
    index: dict[str, Any],
) -> Any:
    if "token" in saved:
        token = SoulToken(token_id=str(saved["token"]))

        index[token.token_id] = token

        return token

    try:
        definition = cards.get(str(saved["id"]))
    except Exception as error:  # noqa: BLE001 - the registry raises its own type
        raise SaveError(
            f"this save holds '{saved.get('id')}', which the loaded content "
            f"does not have"
        ) from error

    card = CardInstance(
        definition=definition,
        instance_id=str(saved.get("instance_id", "")),
        owner=saved.get("owner"),
        controller=saved.get("controller"),
        zone=str(saved.get("zone", "")),
        hp=saved.get("hp"),
        tapped=_flag(saved, "tapped", False),
        alive=_flag(saved, "alive", True),
        last_damaged_by=saved.get("last_damaged_by"),
        counters=dict(_section(saved, "counters")),
    )

    card.modifiers = [
        CardModifier(
            stat=str(_needed(modifier, "stat")),
            amount=_integer(modifier, "amount"),
            duration=_duration(modifier),
        )
        for modifier in _entries(saved, "modifiers")
    ]

    card.copy_expires = str(saved.get("copy_expires", ""))
    card.eternal = _flag(saved, "eternal", False)
    card.silenced_while = str(saved.get("silenced_while", ""))
    card.recharge_skipped = _flag(saved, "recharge_skipped", False)

    if saved.get("copy_of"):
        # Kept as a name until every card is back, then looked up: a copy may
        # wear the face of a card that has not been read yet.
        index.setdefault("__copies__", []).append((card, str(saved["copy_of"])))

    index[card.instance_id] = card

    return card


def _relink_copies(index: Mapping[str, Any], cards: CardRegistry) -> None:
    """
    Give back the faces that copies were wearing.

    A copy is relinked once every card is back, because the card it copies may
    be one that had not been read yet when the copy was.
    """
    for card, definition_id in index.get("__copies__", ()):
        try:
            card.copy_of = cards.get(definition_id)
        except UnknownCardError as error:
            raise SaveError(
                f"this save holds a copy of '{definition_id}', which the loaded "
                f"content does not have"
            ) from error


def _check_priority(state: GameState) -> None:
    """
    Refuse a priority window that nobody could act in, or one held while shut.

    A window is opened for a seat and passed round the table, so while it is
    open somebody at the table holds it; shut, nobody does. A save that has it
    open for nobody - or for a seat nobody sits in - used to load, and then no
    one could pass and the game waited for ever.
    """
    holder = state.priority.holder

    if not state.priority.is_open:
        if holder is not None:
            raise SaveError(
                f"this save gives priority to seat {holder} with no window open"
            )

        return

    if holder is None or holder not in range(len(state.players)):
        raise SaveError(
            f"this save has a priority window open for seat {holder}, "
            f"and it has {len(state.players)} players"
        )


def _check_seats(state: GameState) -> None:
    """
    Refuse a save whose seats do not line up with its players.

    A player's identifier is also where they sit: the rules look a player up
    by it, and a turn names its player by it. The writer always numbers the
    seats from nought, so a save that does not is somebody else's file - and
    one the game would not refuse later but misread: a turn given to seat -1
    goes to the last player by Python's reckoning, and nobody may act in it.

    A save with no players at all is left as it was; what it should mean is a
    question of its own.
    """
    for seat, player in enumerate(state.players):
        if player.player_id != seat:
            raise SaveError(
                f"this save seats player {player.player_id} in seat {seat}"
            )

    if not state.players:
        return

    seats = range(len(state.players))

    if state.turn.active_player not in seats:
        raise SaveError(
            f"this save gives the turn to seat {state.turn.active_player}, "
            f"and it has {len(state.players)} players"
        )

    promised = state.turn.extra_turn_for

    if promised is not None and promised not in seats:
        raise SaveError(
            f"this save promises an extra turn to seat {promised}, "
            f"and it has {len(state.players)} players"
        )


def _load_turn(
    state: GameState, saved: Mapping[str, Any], index: dict[str, Any]
) -> None:
    turn = state.turn

    turn.turn_number = _integer(saved, "turn_number", 1)
    turn.active_player = _integer(saved, "active_player", 0)
    turn.priority_player = _integer(saved, "priority_player", 0)
    turn.phase = _by_name(saved.get("phase"), GamePhase, GamePhase.START, "phase")
    turn.stack_depth = _integer(saved, "stack_depth", 0)
    turn.loot_played = _integer(saved, "loot_played", 0)
    turn.attacks_declared = _integer(saved, "attacks_declared", 0)
    promised = saved.get("extra_turn_for")
    turn.extra_turn_for = (
        None if promised is None else _whole(promised, "extra_turn_for")
    )
    turn.attack_rolls = _integer(saved, "attack_rolls", 0)
    turn.monster_died = _flag(saved, "monster_died", False)
    turn.triggers_fired = dict(_section(saved, "triggers_fired"))
    turn.obligations = [
        Obligation(
            player_id=_integer(owed, "player_id"),
            action=str(owed.get("action", "attack")),
            card_id=owed.get("card_id"),
            remaining=_integer(owed, "remaining", 1),
        )
        for owed in _entries(saved, "obligations")
    ]


def _load_stack_item(
    saved: Mapping[str, Any], state: GameState, index: dict[str, Any]
) -> StackItem:
    item = StackItem(
        kind=_member(StackItemType, _needed(saved, "kind"), "stack item"),
        label=str(saved.get("label", "")),
        source=_resolve(saved.get("source"), state, index),
        ability=_load_ability(_maybe_section(saved, "ability")),
        controller=saved.get("controller"),
        targets=[
            _resolve(target, state, index) for target in _listing(saved, "targets")
        ],
        event=(
            _load_event(event, state, index)
            if (event := _maybe_section(saved, "event")) is not None
            else None
        ),
    )

    item.status = _member(
        StackItemStatus, saved.get("status", StackItemStatus.CREATED), "status"
    )

    return item


def _load_ability(saved: Mapping[str, Any] | None) -> Ability | None:
    if saved is None:
        return None

    _needed(saved, "trigger")

    for key in ("conditions", "targets", "effects"):
        _listing(saved, key)

    return Ability.from_data(dict(saved))


def _load_event(
    saved: Mapping[str, Any], state: GameState, index: dict[str, Any]
) -> Event:
    event = Event(
        type=_member(EventType, _needed(saved, "type"), "event"),
        source=_resolve(saved.get("source"), state, index),
        controller=saved.get("controller"),
        targets=[
            _resolve(target, state, index) for target in _listing(saved, "targets")
        ],
        payload=_resolve(saved.get("payload", {}), state, index),
        event_id=str(saved.get("event_id", "")),
        sequence=_integer(saved, "sequence", 0),
        replacements_applied=list(_listing(saved, "replacements_applied")),
    )

    event.status = _member(
        EventStatus, saved.get("status", EventStatus.CREATED), "status"
    )

    return event


def _resolve(value: Any, state: GameState, index: Mapping[str, Any]) -> Any:
    """
    Turn a pointer back into the object it was pointing at.
    """
    if isinstance(value, Mapping):
        if CARD in value:
            return index.get(str(value[CARD]))

        if TOKEN in value:
            return index.get(str(value[TOKEN]))

        if PLAYER in value:
            seat = value[PLAYER]

            if seat is None or not 0 <= _whole(seat, "player") < len(state.players):
                return None

            return state.player(_whole(seat, "player"))

        return {key: _resolve(item, state, index) for key, item in value.items()}

    if isinstance(value, list):
        return [_resolve(item, state, index) for item in value]

    return value


def _tuples(value: Any) -> Any:
    """
    Rebuild the nested tuples a random generator wants its state in.
    """
    if isinstance(value, list):
        return tuple(_tuples(item) for item in value)

    return value


def zones_of(state: GameState) -> Sequence[tuple[str, Zone[Any]]]:
    """
    Every zone in a game, named — global first, then each player's.
    """
    named: list[tuple[str, Zone[Any]]] = [
        (name, getattr(state, name)) for name in GLOBAL_ZONES
    ]

    named.append(("active_monsters", state.active_monsters))

    for player in state.players:
        for name in PLAYER_ZONES:
            named.append((f"{player.player_id}.{name}", getattr(player, name)))

    return named
