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
from typing import Any

from fsme.cards import Ability, CardInstance, CardRegistry, SoulToken
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
    engine_version: str = "",
    rng_state: Any = None,
) -> dict[str, Any]:
    """
    Write a game out as plain data.

    ``rng_state`` is the live generator's position, which is not kept in
    GameState while a game is running: the Runtime owns the generator, and a
    save that forgot it would reload into a game that rolls different dice.
    """
    _refuse_if_mid_ability(state)

    return {
        "format": SAVE_FORMAT_VERSION,
        "engine": engine_version,
        "seed": state.seed,
        "rng": _plain(rng_state if rng_state is not None else state.rng_state),
        "started": state.started,
        "game_over": state.game_over,
        "winner": state.winner,
        "souls_to_win": state.souls_to_win,
        "monster_slots": state.monster_slots,
        "shop_slots": state.shop_slots,
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

    state = GameState(seed=int(data.get("seed", 0)))

    state.rng_state = _tuples(data.get("rng"))
    state.started = bool(data.get("started", False))
    state.game_over = bool(data.get("game_over", False))
    state.winner = data.get("winner")
    state.souls_to_win = int(data.get("souls_to_win", 4))
    state.monster_slots = int(data.get("monster_slots", 2))
    state.shop_slots = int(data.get("shop_slots", 2))
    state.skipped_players = [int(seat) for seat in data.get("skipped_players", ())]
    state.ids.restore(int(data.get("ids", 0)))

    index: dict[str, Any] = {}

    for name in GLOBAL_ZONES:
        saved = data.get("zones", {}).get(name)

        if saved is not None:
            _load_zone(getattr(state, name), saved, cards, index)

    _load_monster_area(state, data.get("monster_area", ()), cards, index)

    for saved_player in data.get("players", ()):
        state.add_player(_load_player(saved_player, cards, index))

    _load_turn(state, data.get("turn", {}), index)

    priority = data.get("priority", {})

    state.priority.holder = priority.get("holder")
    state.priority.passes = int(priority.get("passes", 0))
    state.priority.is_open = bool(priority.get("is_open", False))

    combat = data.get("combat", {})

    state.combat.attacker = combat.get("attacker")
    state.combat.monster = _resolve(combat.get("monster"), state, index)
    state.combat.round_number = int(combat.get("round_number", 0))
    state.combat.settled_roll = combat.get("settled_roll")
    state.combat.active = bool(combat.get("active", False))

    for saved_item in data.get("stack", ()):
        state.stack.push(_load_stack_item(saved_item, state, index))

    for saved_event in data.get("events", ()):
        state.events.push(_load_event(saved_event, state, index))

    state.shields = [
        DamageShield(
            player_id=int(saved["player_id"]),
            amount=saved.get("amount"),
            label=str(saved.get("label", "")),
            duration=Duration(saved.get("duration", Duration.END_OF_TURN)),
        )
        for saved in data.get("shields", ())
    ]

    state.modifiers = [
        TemporaryModifier(
            stat=str(saved["stat"]),
            amount=int(saved["amount"]),
            player_id=int(saved["player_id"]),
            duration=Duration(saved.get("duration", Duration.END_OF_TURN)),
        )
        for saved in data.get("modifiers", ())
    ]

    state.promises = [
        Promise(
            event=str(saved["event"]),
            changes=dict(saved.get("changes", {})),
            player_id=saved.get("player_id"),
            card_id=saved.get("card_id"),
            when=dict(saved.get("when", {})),
            uses=saved.get("uses"),
            duration=Duration(saved.get("duration", Duration.END_OF_TURN)),
        )
        for saved in data.get("promises", ())
    ]

    state.watchers = [
        Watcher(
            event=str(saved["event"]),
            controller=saved.get("controller"),
            source=_resolve(saved.get("source"), state, index),
            label=str(saved.get("label", "")),
            conditions=tuple(saved.get("conditions", ())),
            effects=tuple(saved.get("effects", ())),
            player_id=saved.get("player_id"),
            uses=saved.get("uses"),
            duration=Duration(saved.get("duration", Duration.END_OF_TURN)),
            waits=bool(saved.get("waits", False)),
            fired=list(saved.get("fired", ())),
        )
        for saved in data.get("watchers", ())
    ]

    saved_decision = data.get("pending_decision")

    if saved_decision is not None:
        state.pending_decision = PendingDecision(
            decision_id=str(saved_decision["decision_id"]),
            player=int(saved_decision["player"]),
            kind=DecisionKind(saved_decision["kind"]),
            options=[
                _resolve(option, state, index)
                for option in saved_decision.get("options", ())
            ],
            minimum=int(saved_decision.get("minimum", 1)),
            maximum=int(saved_decision.get("maximum", 1)),
            bind=str(saved_decision.get("bind", "chosen")),
            prompt=str(saved_decision.get("prompt", "")),
        )

    saved_roll = data.get("pending_roll")

    if saved_roll is not None:
        state.pending_roll = PendingRoll(
            roll_id=str(saved_roll["roll_id"]),
            sides=int(saved_roll["sides"]),
            natural=int(saved_roll["natural"]),
            value=int(saved_roll["value"]),
            roller=saved_roll.get("roller"),
            attack=bool(saved_roll.get("attack", False)),
        )

    _relink_copies(index, cards)

    return state


def _load_player(
    saved: Mapping[str, Any],
    cards: CardRegistry,
    index: dict[str, Any],
) -> PlayerState:
    player = PlayerState(
        player_id=int(saved["player_id"]),
        name=str(saved.get("name", "")),
        hp=int(saved.get("hp", 0)),
        max_hp=int(saved.get("max_hp", 0)),
        pennies=int(saved.get("pennies", 0)),
        counters={str(k): int(v) for k, v in saved.get("counters", {}).items()},
        attacks_left=int(saved.get("attacks_left", 0)),
        purchases_left=int(saved.get("purchases_left", 0)),
        additional_loot_plays=int(saved.get("additional_loot_plays", 0)),
        loot_played=int(saved.get("loot_played", 0)),
        alive=bool(saved.get("alive", True)),
    )

    player.loot_limit_lifted = bool(saved.get("loot_limit_lifted", False))
    player.died_this_turn = bool(saved.get("died_this_turn", False))
    player.hp_before_lethal = int(saved.get("hp_before_lethal", 0))

    character = saved.get("character")

    if character is not None:
        player.character = _load_card(character, cards, index)

    for name in PLAYER_ZONES:
        written = saved.get(name)

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

    for written in saved.get("cards", ()):
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
        state.monster_area.append(
            MonsterSlot(cards=[_load_card(card, cards, index) for card in written])
        )

    sync(state)


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
        tapped=bool(saved.get("tapped", False)),
        alive=bool(saved.get("alive", True)),
        last_damaged_by=saved.get("last_damaged_by"),
        counters=dict(saved.get("counters", {})),
    )

    card.modifiers = [
        CardModifier(
            stat=str(modifier["stat"]),
            amount=int(modifier["amount"]),
            duration=Duration(modifier.get("duration", Duration.END_OF_TURN)),
        )
        for modifier in saved.get("modifiers", ())
    ]

    card.copy_expires = str(saved.get("copy_expires", ""))
    card.eternal = bool(saved.get("eternal", False))
    card.silenced_while = str(saved.get("silenced_while", ""))
    card.recharge_skipped = bool(saved.get("recharge_skipped", False))

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
        card.copy_of = cards.get(definition_id)


def _load_turn(
    state: GameState, saved: Mapping[str, Any], index: dict[str, Any]
) -> None:
    turn = state.turn

    turn.turn_number = int(saved.get("turn_number", 1))
    turn.active_player = int(saved.get("active_player", 0))
    turn.priority_player = int(saved.get("priority_player", 0))
    turn.phase = _by_name(saved.get("phase"), GamePhase, GamePhase.START, "phase")
    turn.stack_depth = int(saved.get("stack_depth", 0))
    turn.loot_played = int(saved.get("loot_played", 0))
    turn.attacks_declared = int(saved.get("attacks_declared", 0))
    turn.extra_turn_for = saved.get("extra_turn_for")
    turn.attack_rolls = int(saved.get("attack_rolls", 0))
    turn.triggers_fired = dict(saved.get("triggers_fired", {}))
    turn.obligations = [
        Obligation(
            player_id=int(owed["player_id"]),
            action=str(owed.get("action", "attack")),
            card_id=owed.get("card_id"),
            remaining=int(owed.get("remaining", 1)),
        )
        for owed in saved.get("obligations", ())
    ]


def _load_stack_item(
    saved: Mapping[str, Any], state: GameState, index: dict[str, Any]
) -> StackItem:
    item = StackItem(
        kind=StackItemType(saved["kind"]),
        label=str(saved.get("label", "")),
        source=_resolve(saved.get("source"), state, index),
        ability=_load_ability(saved.get("ability")),
        controller=saved.get("controller"),
        targets=[
            _resolve(target, state, index) for target in saved.get("targets", ())
        ],
        event=(
            _load_event(saved["event"], state, index)
            if saved.get("event") is not None
            else None
        ),
    )

    item.status = StackItemStatus(saved.get("status", StackItemStatus.CREATED))

    return item


def _load_ability(saved: Mapping[str, Any] | None) -> Ability | None:
    if saved is None:
        return None

    return Ability.from_data(dict(saved))


def _load_event(
    saved: Mapping[str, Any], state: GameState, index: dict[str, Any]
) -> Event:
    event = Event(
        type=EventType(saved["type"]),
        source=_resolve(saved.get("source"), state, index),
        controller=saved.get("controller"),
        targets=[_resolve(target, state, index) for target in saved.get("targets", ())],
        payload=_resolve(saved.get("payload", {}), state, index),
        event_id=str(saved.get("event_id", "")),
        sequence=int(saved.get("sequence", 0)),
        replacements_applied=list(saved.get("replacements_applied", ())),
    )

    event.status = EventStatus(saved.get("status", EventStatus.CREATED))

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

            if seat is None or not 0 <= int(seat) < len(state.players):
                return None

            return state.player(int(seat))

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
