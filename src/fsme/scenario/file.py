# src/fsme/scenario/file.py

"""
A scenario as a file somebody wrote by hand.

Which is the whole reason this module is separate from the dataclass. A
scenario is not written by the engine — it is written by a person in a text
editor, typing card identifiers from memory, and the difference between a good
tool and a bad one here is entirely in what it says when they get one wrong.

So: every way of being wrong gets its own sentence, and nothing is quietly
repaired. A `monster_slots` of 0 is not turned into 1, a misspelled key is not
ignored, and an empty player list is not read as "deal as usual" — that is what
leaving the key out means, and the two are different requests.

What this module does *not* do is check that a card identifier exists. That is
a question about a content library, which does not exist yet when a file is
read, and it is asked where the library is — the same separation the content
pipeline already keeps between its schema stage and its semantic stage.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .errors import ScenarioError
from .scenario import FORMAT, VERSION, Scenario, from_dict

KNOWN_KEYS = frozenset(
    {
        "format",
        "version",
        "name",
        "description",
        "seed",
        "interactive_priority",
        "content",
        "table",
        "players",
    }
)

KNOWN_CONTENT_KEYS = frozenset({"expansions", "exclude_cards"})
KNOWN_TABLE_KEYS = frozenset({"souls_to_win", "monster_slots", "shop_slots"})
KNOWN_SEAT_KEYS = frozenset(
    {"name", "character", "starting_item", "coins", "loot"}
)

MINIMUM_MONSTER_SLOTS = 1
"""
A monster has to be somewhere.

With no slots the board starts empty and stays empty until somebody attacks the
monster deck — and then `rules.slots.place` makes a slot for the revealed
monster, because losing it would be worse. So a game asked for zero slots
quietly becomes a game with one, which is not what the file said. Refused
rather than honoured badly.
"""


def validate(data: Any, *, where: str = "") -> list[str]:
    """
    Return every problem with a scenario, in the words a reader needs.

    A list rather than the first failure, because somebody typing a file wants
    to see everything wrong with it at once — the reason the content pipeline
    collects its issues too.
    """
    named = f"{where}: " if where else ""
    problems: list[str] = []

    if not isinstance(data, Mapping):
        return [
            f"{named}a scenario must be an object, "
            f"got {type(data).__name__}"
        ]

    marker = data.get("format")

    if marker is None:
        problems.append(
            f"{named}this does not say what it is; a scenario begins with "
            f'"format": "{FORMAT}"'
        )
    elif marker != FORMAT:
        problems.append(
            f"{named}this is written in format '{marker}', "
            f"and a scenario is '{FORMAT}'"
        )

    version = data.get("version")

    if version is None:
        problems.append(f"{named}this scenario does not say which version it is")
    elif not isinstance(version, int) or isinstance(version, bool):
        problems.append(
            f"{named}the version must be a whole number, got {version!r}"
        )
    elif version != VERSION:
        problems.append(
            f"{named}this scenario is version {version}, "
            f"and this build reads version {VERSION}"
        )

    problems.extend(_unknown(named, data, KNOWN_KEYS, "scenario"))

    _check_text(named, data, "name", problems)
    _check_text(named, data, "description", problems)
    _check_whole(named, data, "seed", problems)

    priority = data.get("interactive_priority")

    if priority is not None and not isinstance(priority, bool):
        problems.append(
            f"{named}interactive_priority is true or false, got {priority!r}"
        )

    problems.extend(_content(named, data.get("content")))
    problems.extend(_table(named, data.get("table")))
    problems.extend(_players(named, data))

    return problems


def _unknown(
    named: str,
    data: Mapping[str, Any],
    known: frozenset[str],
    what: str,
) -> list[str]:
    """
    Name every key this build does not understand.

    Ignoring them would mean a misspelled `monster_slots` silently deals an
    ordinary game, and the person would go looking for the bug in the engine.
    """
    strays = sorted(str(key) for key in data if str(key) not in known)

    if not strays:
        return []

    return [
        f"{named}the {what} has {'a key' if len(strays) == 1 else 'keys'} "
        f"this build does not know: {', '.join(strays)}"
    ]


def _check_text(
    named: str, data: Mapping[str, Any], key: str, problems: list[str]
) -> None:
    value = data.get(key)

    if value is not None and not isinstance(value, str):
        problems.append(f"{named}{key} must be text, got {type(value).__name__}")


def _check_whole(
    named: str,
    data: Mapping[str, Any],
    key: str,
    problems: list[str],
    *,
    least: int | None = None,
    what: str = "",
) -> None:
    value = data.get(key)

    if value is None:
        return

    if not isinstance(value, int) or isinstance(value, bool):
        problems.append(
            f"{named}{what or key} must be a whole number, got {value!r}"
        )

        return

    if least is not None and value < least:
        problems.append(
            f"{named}{what or key} is {value}, and the least it can be is {least}"
        )


def _content(named: str, content: Any) -> list[str]:
    if content is None:
        return []

    if not isinstance(content, Mapping):
        return [f"{named}content must be an object, got {type(content).__name__}"]

    problems = _unknown(named, content, KNOWN_CONTENT_KEYS, "content")

    for key in ("expansions", "exclude_cards"):
        listed = content.get(key)

        if listed is None:
            continue

        if not isinstance(listed, (list, tuple)):
            problems.append(
                f"{named}content.{key} must be a list, got {type(listed).__name__}"
            )

            continue

        for item in listed:
            if not isinstance(item, str) or not item:
                problems.append(
                    f"{named}content.{key} holds {item!r}, "
                    f"and every entry is an identifier"
                )

    return problems


def _table(named: str, table: Any) -> list[str]:
    if table is None:
        return []

    if not isinstance(table, Mapping):
        return [f"{named}table must be an object, got {type(table).__name__}"]

    problems = _unknown(named, table, KNOWN_TABLE_KEYS, "table")

    _check_whole(named, table, "souls_to_win", problems, least=1,
                 what="table.souls_to_win")
    _check_whole(named, table, "monster_slots", problems,
                 least=MINIMUM_MONSTER_SLOTS, what="table.monster_slots")
    _check_whole(named, table, "shop_slots", problems, least=0,
                 what="table.shop_slots")

    if table.get("monster_slots") == 0:
        problems.append(
            f"{named}a game with no monster slots is not a game with no "
            f"monsters: the first monster revealed makes a slot for itself, "
            f"so the table would quietly have one"
        )

    return problems


def _players(named: str, data: Mapping[str, Any]) -> list[str]:
    if "players" not in data:
        return []

    players = data.get("players")

    if not isinstance(players, (list, tuple)):
        return [
            f"{named}players must be a list, got {type(players).__name__}"
        ]

    if not players:
        return [
            f"{named}players is empty; a scenario that does not name the "
            f"seats leaves the key out, which deals the table as usual"
        ]

    problems: list[str] = []
    seen: dict[str, int] = {}

    for index, seat in enumerate(players):
        at = f"{named}players[{index}]"

        if not isinstance(seat, Mapping):
            problems.append(f"{at} must be an object, got {type(seat).__name__}")

            continue

        problems.extend(_unknown(f"{at}: ", seat, KNOWN_SEAT_KEYS, "seat"))

        for key in ("name", "character", "starting_item"):
            value = seat.get(key)

            if value is not None and not isinstance(value, str):
                problems.append(
                    f"{at}: {key} must be text, got {type(value).__name__}"
                )

        _check_whole(f"{at}: ", seat, "coins", problems, least=0)
        _check_whole(f"{at}: ", seat, "loot", problems, least=0)

        character = seat.get("character")

        if isinstance(character, str) and character:
            if character in seen:
                problems.append(
                    f"{at}: character '{character}' is already dealt to seat "
                    f"{seen[character]}; one card cannot sit in two chairs"
                )
            else:
                seen[character] = index

    problems.extend(_one_opening(named, players, "coins"))
    problems.extend(_one_opening(named, players, "loot"))

    return problems


def _one_opening(named: str, players: Sequence[Any], key: str) -> list[str]:
    """
    Refuse an opening that differs from seat to seat.

    The format asks for these per seat, because "what if one player starts
    rich" is a question worth being able to ask. This build deals one opening
    to the whole table, so a scenario whose seats disagree is refused rather
    than half-honoured — the format keeps the shape it will need, and the
    engine says plainly that it has not grown into it yet.
    """
    asked = [
        seat.get(key)
        for seat in players
        if isinstance(seat, Mapping)
    ]

    named_values = {value for value in asked if isinstance(value, int)}

    if len(named_values) > 1:
        return [
            f"{named}the seats ask for openings of "
            f"{', '.join(str(value) for value in sorted(named_values))} "
            f"{key}, and this build deals the same opening to every seat"
        ]

    if named_values and any(value is None for value in asked):
        return [
            f"{named}some seats name the opening {key} and some do not, and "
            f"this build deals the same opening to every seat"
        ]

    return []


def parse(data: Any, *, where: str = "") -> Scenario:
    """
    Check a scenario and build it, or refuse the whole thing.
    """
    problems = validate(data, where=where)

    if problems:
        raise ScenarioError("\n".join(problems))

    assert isinstance(data, Mapping)

    return from_dict(data)


def load(path: Path | str) -> Scenario:
    """
    Read a scenario from a file.
    """
    where = Path(path)

    try:
        text = where.read_text(encoding="utf-8")
    except OSError as error:
        raise ScenarioError(f"{where} cannot be read: {error}") from None

    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ScenarioError(f"{where} is not JSON: {error}") from None

    return parse(data, where=str(where))


def save(scenario: Scenario, path: Path | str) -> Path:
    """
    Write a scenario out, for a person to read and edit.
    """
    where = Path(path)

    where.parent.mkdir(parents=True, exist_ok=True)
    where.write_text(
        json.dumps(scenario.to_dict(), indent=2) + "\n", encoding="utf-8"
    )

    return where
