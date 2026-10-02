"""
A save keeps everything the game is, and says what it leaves out and why.

The round trips in test_save.py compare `state_digest` before and after, and the
digest is a fingerprint for replays, not a list of what a game holds: it counts
the stack without reading it, and has never looked at how long an attack had
gone without a hit. A save that dropped either still passed. So the contract
here is read off the state's own dataclasses: every field of every class a
saved game reaches comes back equal after save, JSON and load — compared field
by field, never through the digest — or is named below with the reason it does
not.

The positions are found by playing, not built by hand, because what went
missing were things only a game in progress holds: a loot card that has left
its owner's hand and not yet reached the discard pile, what a stack object
carries, an attack that has stalled, a table that answers priority.
"""

from __future__ import annotations

import dataclasses
import enum
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest

from fsme.api import Session
from fsme.cards import CardDefinition, CardInstance
from fsme.content import ContentLibrary, ContentLoader
from fsme.game import Game
from fsme.journal.keeper import JournalKeeper
from fsme.lab.bot import HeuristicBot
from fsme.lab.simulation.runner import NAMES, _whose_move
from fsme.runtime.vocabulary import engine_vocabulary
from fsme.serialization import SAVE_FORMAT_VERSION, SaveError
from fsme.state import PlayerState

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"

# Every field a save does not bring back, with the reason. Nothing else is.
NOT_BROUGHT_BACK: dict[tuple[str, str], str] = {
    ("GameState", "pending_decision"): (
        "a question is only asked inside an ability; a game waiting inside one "
        "is not saved, and a save holding one is refused"
    ),
    ("PendingRoll", "continuation"): (
        "the interpreter's own working inside an ability, which is not saved"
    ),
    ("GameState", "rng_state"): (
        "the generator's position belongs to the Runtime while a game runs; it "
        "is compared there instead"
    ),
}

NOT_BROUGHT_BACK_AT_ALL = {
    "PendingDecision": "only ever held by a game waiting inside an ability",
}

# Brought back by what it is called rather than as the object it was.
BY_IDENTIFIER: dict[tuple[str, str], str] = {
    ("CardInstance", "definition"): "looked up again in the content by its id",
    ("CardInstance", "copy_of"): "looked up again in the content by its id",
}

# Brought back as the same content in the containers a reader builds.
BY_CONTENT: dict[tuple[str, str], str] = {
    ("StackItem", "ability"): "rebuilt from the data it is, frozen as abilities are",
}


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return ContentLoader(engine_vocabulary()).load_root(CONTENT_ROOT)


# ----------------------------------------------------------------------
# Comparing two states, field by field
# ----------------------------------------------------------------------


class Compared:
    """What a comparison looked at: every field, and the values it saw there."""

    def __init__(self) -> None:
        self.fields: set[tuple[str, str]] = set()
        self.differences: list[str] = []


def differences(before: Any, after: Any, compared: Compared) -> list[str]:
    _same(before, after, "state", compared, set())

    return compared.differences


def _same(a: Any, b: Any, path: str, compared: Compared, seen: set[Any]) -> None:
    def differ(what: str) -> None:
        compared.differences.append(f"{path}: {what}")

    if isinstance(a, CardInstance) or isinstance(b, CardInstance):
        if not (isinstance(a, CardInstance) and isinstance(b, CardInstance)):
            differ(f"{a!r} became {b!r}")
        elif a.instance_id != b.instance_id:
            differ(f"card {a.instance_id} became card {b.instance_id}")
        elif ("card", a.instance_id) not in seen:
            seen.add(("card", a.instance_id))
            _fields(a, b, path, compared, seen)

        return

    if isinstance(a, PlayerState) and isinstance(b, PlayerState):
        if a.player_id != b.player_id:
            differ(f"player {a.player_id} became player {b.player_id}")
        elif ("player", a.player_id) not in seen:
            seen.add(("player", a.player_id))
            _fields(a, b, path, compared, seen)

        return

    if isinstance(a, CardDefinition) and isinstance(b, CardDefinition):
        if a.id != b.id:
            differ(f"{a.id} became {b.id}")

        return

    if dataclasses.is_dataclass(a) and not isinstance(a, type):
        if type(a) is not type(b):
            differ(f"{type(a).__name__} became {type(b).__name__}")
        else:
            _fields(a, b, path, compared, seen)

        return

    if hasattr(a, "_items") and hasattr(b, "_items"):  # the stack
        _same(list(a._items), list(b._items), f"{path}.items", compared, seen)

        return

    if hasattr(a, "_queue") and hasattr(b, "_queue"):  # the event queue
        _same(list(a._queue), list(b._queue), f"{path}.queue", compared, seen)

        return

    if isinstance(a, Mapping) and isinstance(b, Mapping):
        if set(map(str, a)) != set(map(str, b)):
            differ(f"keys {sorted(map(str, a))} became {sorted(map(str, b))}")

            return

        theirs = {str(key): value for key, value in b.items()}

        for key, value in a.items():
            _same(value, theirs[str(key)], f"{path}[{key!r}]", compared, seen)

        return

    # A save is JSON, and JSON has one kind of list.
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            differ(f"{len(a)} items became {len(b)}")

            return

        for index, (one, other) in enumerate(zip(a, b, strict=True)):
            _same(one, other, f"{path}[{index}]", compared, seen)

        return

    if isinstance(a, enum.Enum) or isinstance(b, enum.Enum):
        if str(a) != str(b):
            differ(f"{a!r} became {b!r}")

        return

    if a != b:
        differ(f"{a!r} became {b!r}")


def _fields(a: Any, b: Any, path: str, compared: Compared, seen: set[Any]) -> None:
    kind = type(a).__name__

    if kind in NOT_BROUGHT_BACK_AT_ALL:
        return

    for field in dataclasses.fields(a):
        key = (kind, field.name)
        compared.fields.add(key)

        if key in NOT_BROUGHT_BACK:
            continue

        mine, theirs = getattr(a, field.name), getattr(b, field.name)

        if key in BY_IDENTIFIER:
            if getattr(mine, "id", None) != getattr(theirs, "id", None):
                compared.differences.append(
                    f"{path}.{field.name}: {getattr(mine, 'id', None)!r} became "
                    f"{getattr(theirs, 'id', None)!r}"
                )

            continue

        _same(mine, theirs, f"{path}.{field.name}", compared, seen)


# ----------------------------------------------------------------------
# Positions only a game in progress holds
# ----------------------------------------------------------------------


def saved(game: Game) -> dict[str, Any] | None:
    try:
        return dict(json.loads(json.dumps(game.save(engine_version="test"))))
    except SaveError:
        return None


def first_position(
    everything: ContentLibrary,
    seed: int,
    found: Callable[[Game, dict[str, Any]], bool],
    *,
    interactive: bool = True,
    moves: int = 3000,
) -> Game:
    """
    Play until a position the save can hold has what is being looked for.
    """
    game = Game.from_content(
        everything, list(NAMES[:4]), seed=seed, interactive_priority=interactive
    )
    assert game.start().accepted

    keeper = JournalKeeper(game)
    bot = HeuristicBot(seed)

    for _ in range(moves):
        if game.is_over:
            break

        data = saved(game)

        if data is not None and found(game, data):
            return game

        thought = bot.choose(game, seats=(_whose_move(game),))

        if thought is None:
            break

        command, label, working = thought

        assert keeper.submit(command, label=label, decision=working.to_dict()).accepted

    raise AssertionError(f"seed {seed} never reached the position looked for")


def a_loot_card_being_played(game: Game, data: dict[str, Any]) -> bool:
    return bool(data["in_flight"]) and any(
        not item.cancellable for item in game.state.stack
    )


def a_stack_object_carrying_something(game: Game, data: dict[str, Any]) -> bool:
    return any(item.payload for item in game.state.stack)


def an_attack_that_has_stalled(game: Game, data: dict[str, Any]) -> bool:
    return game.state.combat.active and game.state.combat.stalled_rounds > 0


def counted(game: Game) -> Game:
    """Counters on a card and on a player, which nothing in an opening sets."""
    card = next(
        player.character
        for player in game.state.players
        if isinstance(player.character, CardInstance)
    )
    card.counters["charge"] = 3
    game.state.players[1].counters["poison"] = 2

    return game


@pytest.fixture(scope="module")
def positions(everything: ContentLibrary) -> dict[str, Game]:
    plain = first_position(
        everything, 2, lambda game, data: game.state.turn.turn_number >= 3,
        interactive=False,
    )

    return {
        "an ordinary game": plain,
        "a loot card being played": first_position(
            everything, 0, a_loot_card_being_played
        ),
        "a stack object carrying something": first_position(
            everything, 0, a_stack_object_carrying_something
        ),
        "an attack that has stalled": first_position(
            everything, 1, an_attack_that_has_stalled
        ),
        "counters on a card and a player": counted(
            first_position(
                everything, 3, lambda game, data: game.state.turn.turn_number >= 2,
                interactive=False,
            )
        ),
    }


POSITIONS = (
    "an ordinary game",
    "a loot card being played",
    "a stack object carrying something",
    "an attack that has stalled",
    "counters on a card and a player",
)


# ----------------------------------------------------------------------
# The contract
# ----------------------------------------------------------------------


@pytest.mark.parametrize("where", POSITIONS)
def test_every_field_comes_back_or_is_named(
    everything: ContentLibrary, positions: dict[str, Game], where: str
) -> None:
    game = positions[where]
    data = saved(game)

    assert data is not None and data["format"] == SAVE_FORMAT_VERSION

    back = Game.load(data, everything)
    compared = Compared()

    assert differences(game.state, back.state, compared) == []
    assert back.runtime.rng.get_state() == game.runtime.rng.get_state()
    assert back.interactive_priority is game.interactive_priority


def test_the_contract_is_not_empty(
    everything: ContentLibrary, positions: dict[str, Game]
) -> None:
    """
    The positions hold what went missing, so the contract is about something.

    Every field of every class the comparison reached was looked at, and each
    of the things format 1 lost is really there, not at its default.
    """
    compared = Compared()

    for game in positions.values():
        data = saved(game)
        assert data is not None
        differences(game.state, Game.load(data, everything).state, compared)

    reached = {kind for kind, _ in compared.fields}

    for kind in reached:
        cls = next(
            type(obj) for obj in _instances(positions) if type(obj).__name__ == kind
        )
        assert {(kind, field.name) for field in dataclasses.fields(cls)} <= (
            compared.fields
        ), kind

    assert {"GameState", "PlayerState", "CardInstance", "StackItem", "Event",
            "CombatState", "PriorityState", "TurnState"} <= reached

    states = [game.state for game in positions.values()]

    assert any(not item.cancellable for state in states for item in state.stack)
    assert any(item.payload for state in states for item in state.stack)
    assert any(state.combat.stalled_rounds > 0 for state in states)
    assert any(state.priority.is_open for state in states)
    assert any(
        card.counters
        for state in states
        for player in state.players
        for card in [player.character]
        if isinstance(card, CardInstance)
    )
    assert any(player.counters for state in states for player in state.players)
    assert any(saved(game)["in_flight"] for game in positions.values())  # type: ignore[index]


def _instances(positions: dict[str, Game]) -> list[Any]:
    found: list[Any] = []

    def walk(value: Any, seen: set[int]) -> None:
        if id(value) in seen:
            return

        seen.add(id(value))

        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            found.append(value)

            for field in dataclasses.fields(value):
                walk(getattr(value, field.name), seen)
        elif isinstance(value, Mapping):
            for item in value.values():
                walk(item, seen)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item, seen)
        elif hasattr(value, "_items"):
            walk(list(value._items), seen)
        elif hasattr(value, "_queue"):
            walk(list(value._queue), seen)

    for game in positions.values():
        walk(game.state, set())

    return found


@pytest.mark.parametrize("where", POSITIONS)
def test_no_card_the_save_points_at_comes_back_as_nothing(
    everything: ContentLibrary, positions: dict[str, Game], where: str
) -> None:
    """
    Including a card the save holds only because it is in flight.
    """
    data = saved(positions[where])
    assert data is not None

    back = Game.load(data, everything)

    for written, item in zip(data["stack"], back.state.stack, strict=True):
        for key, value in (("source", item.source), ("targets", item.targets)):
            assert _pointed(written[key]) == _held(value), (where, key)

        if written["event"] is not None:
            assert _pointed(written["event"]["source"]) == _held(item.event.source)

    # And what it points at reads back the same when it is saved again.
    assert saved(back) == data


def _pointed(written: Any) -> Any:
    if isinstance(written, list):
        return [_pointed(one) for one in written]

    return written.get("$card") if isinstance(written, Mapping) else written


def _held(value: Any) -> Any:
    if isinstance(value, list):
        return [_held(one) for one in value]

    if value is None:
        return None

    assert isinstance(value, CardInstance), value

    return value.instance_id


# ----------------------------------------------------------------------
# Cards in flight
# ----------------------------------------------------------------------


def pointed_in_flight(data: dict[str, Any]) -> list[str]:
    """Every pointer the stack makes at a card the save holds as in flight."""
    flying = {card["instance_id"] for card in data["in_flight"]}

    return [
        ref
        for item in data["stack"]
        for ref in (
            _pointed(item["source"]),
            _pointed((item["event"] or {}).get("source")),
        )
        if ref in flying
    ]


def test_a_card_being_played_is_written_once_and_left_where_it_is(
    everything: ContentLibrary,
) -> None:
    """
    The loot card and its own ability point at the same card, which is written
    down once; and finding it moves nothing.
    """
    game = first_position(
        everything,
        0,
        lambda game, data: len(pointed_in_flight(data))
        > len(set(pointed_in_flight(data))),
    )
    stack_before = list(game.state.stack)
    hands_before = [list(player.hand.cards) for player in game.state.players]

    data = saved(game)
    assert data is not None

    flying = [card["instance_id"] for card in data["in_flight"]]

    assert len(flying) == len(set(flying))
    assert set(pointed_in_flight(data)) <= set(flying)
    assert list(game.state.stack) == stack_before
    assert [list(player.hand.cards) for player in game.state.players] == hands_before
    assert differences(game.state, Game.load(data, everything).state, Compared()) == []


def test_a_save_pointing_at_a_card_it_does_not_hold_is_refused(
    everything: ContentLibrary, positions: dict[str, Game]
) -> None:
    data = saved(positions["a loot card being played"])
    assert data is not None

    missing = data["in_flight"][0]["instance_id"]
    data["in_flight"] = []

    with pytest.raises(SaveError, match=f"card '{missing}'"):
        Game.load(data, everything)


# ----------------------------------------------------------------------
# What the current format cannot be read without
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    (
        ("interactive_priority",),
        ("combat", "stalled_rounds"),
        ("stack", 0, "cancellable"),
        ("stack", 0, "payload"),
        ("stack", 0, "stack_id"),
        ("stack", 0, "order"),
    ),
)
def test_the_current_format_does_not_read_without(
    everything: ContentLibrary, positions: dict[str, Game], path: tuple[Any, ...]
) -> None:
    data = saved(positions["a loot card being played"])
    assert data is not None

    holder: Any = data

    for key in path[:-1]:
        holder = holder[key]

    del holder[path[-1]]

    with pytest.raises(SaveError, match=f"missing '{path[-1]}'"):
        Game.load(data, everything)


# ----------------------------------------------------------------------
# Format 1
# ----------------------------------------------------------------------


def as_format_1(data: dict[str, Any]) -> dict[str, Any]:
    """The save as format 1 wrote it: without what format 2 added."""
    old = json.loads(json.dumps(data))
    old["format"] = "1"

    for key in ("interactive_priority", "in_flight"):
        old.pop(key, None)

    old["combat"].pop("stalled_rounds", None)

    for item in old["stack"]:
        for key in ("payload", "stack_id", "order", "cancellable"):
            item.pop(key, None)

    return dict(old)


def test_format_1_that_lost_nothing_loads(
    everything: ContentLibrary, positions: dict[str, Game]
) -> None:
    game = positions["an ordinary game"]
    data = saved(game)
    assert data is not None and not data["stack"] and not data["combat"]["active"]

    back = Game.load(as_format_1(data), everything)

    assert differences(game.state, back.state, Compared()) == []
    assert back.state.combat.stalled_rounds == 0
    assert back.interactive_priority is False
    assert Game.load(as_format_1(data), everything, interactive_priority=True).interactive_priority


@pytest.mark.parametrize(
    ("where", "said"),
    (
        ("a loot card being played", "on the stack"),
        ("an attack that has stalled", "during an attack|on the stack"),
    ),
)
def test_format_1_that_lost_something_is_refused(
    everything: ContentLibrary, positions: dict[str, Game], where: str, said: str
) -> None:
    data = saved(positions[where])
    assert data is not None

    with pytest.raises(SaveError, match=said):
        Game.load(as_format_1(data), everything)


def test_format_1_during_an_attack_with_nothing_on_the_stack_is_refused(
    everything: ContentLibrary, positions: dict[str, Game]
) -> None:
    data = as_format_1(saved(positions["an attack that has stalled"]) or {})
    data["stack"] = []

    with pytest.raises(SaveError, match="during an attack"):
        Game.load(data, everything)


# ----------------------------------------------------------------------
# Whether the table answers priority
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("passed", "loads_as"),
    ((None, True), (True, True), (False, False)),
    ids=("nothing passed", "true passed", "false passed"),
)
def test_a_game_loads_answering_priority_as_it_was_saved_unless_told(
    everything: ContentLibrary,
    positions: dict[str, Game],
    passed: bool | None,
    loads_as: bool,
) -> None:
    data = saved(positions["a loot card being played"])
    assert data is not None and data["interactive_priority"] is True

    if passed is None:
        back = Game.load(data, everything)
    else:
        back = Game.load(data, everything, interactive_priority=passed)

    assert back.interactive_priority is loads_as


def test_a_game_saved_without_priority_loads_without_it(
    everything: ContentLibrary, positions: dict[str, Game]
) -> None:
    data = saved(positions["an ordinary game"])
    assert data is not None and data["interactive_priority"] is False

    assert Game.load(data, everything).interactive_priority is False
    assert Game.load(data, everything, interactive_priority=True).interactive_priority


def test_a_session_follows_the_game_it_loads(
    everything: ContentLibrary, positions: dict[str, Game]
) -> None:
    data = saved(positions["an ordinary game"])
    assert data is not None

    session = Session(everything, players=4, seed=0, interactive_priority=True)
    session.load(data)

    assert session.game.interactive_priority is False
    assert session._interactive is False
