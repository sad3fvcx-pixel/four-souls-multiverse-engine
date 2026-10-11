# src/fsme/lab/desk/games.py

"""
Games somebody set up once and wants to deal again.

A custom game is a scenario, and nothing else. `fsme.scenario` already says how
a game starts — which sets are in the decks, who sits in which chair as which
character, what each seat opens with, what the table is worth winning — and the
engine already deals one. So this module writes no format of its own: what it
keeps is an ordinary ``fsme-scenario`` file, read and checked by the same code
that reads the files in ``scenarios/``, and dealt by the same door every other
game is dealt by.

What it adds is what a page needs and a hand-written file does not: a name to
save it under, a folder to keep it in beside the author's sets, and an answer to
"can this still be dealt?" asked against whatever is loaded *now* — a set gets
deleted, a character is renamed, and a game saved last week has to say so
rather than fail without a reason when somebody presses Start.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fsme.cards import CardType
from fsme.content import ContentLibrary
from fsme.content.workspace import home, identifier_for
from fsme.scenario import Scenario, ScenarioError, parse, validate

GAMES = "my games"
"""
Where an author's custom games go, one file each, beside ``my sets``.
"""

LEAST_SEATS = 2
MOST_SEATS = 4
"""
How many chairs a game watched on the desk can have: what a watched session
deals, which is not a rule of Four Souls and is not changed here.
"""


class GameError(ValueError):
    """
    Something about a custom game that the person can fix, said to them.

    ``problems`` carries every reason at once when there was more than one,
    which is how a scenario is checked: somebody filling in a form wants to see
    everything wrong with it, not one thing per press of Save.
    """

    def __init__(self, message: str, problems: list[str] | None = None) -> None:
        super().__init__(message)

        self.problems = list(problems or [message])


def games_directory() -> Path:
    """
    The folder custom games are kept in. Not made until something is saved.
    """
    return home() / GAMES


# ----------------------------------------------------------------------
# What a page sends, turned into a scenario
# ----------------------------------------------------------------------


def scenario_from(described: Any) -> Scenario:
    """
    Build the scenario a page described, or say everything wrong with it.

    The page's own checks are a courtesy; these are the ones that count. Every
    value is read as the type it has to be, text is trimmed, and blank means
    "as the game deals it" — the meaning a scenario already gives to a field it
    leaves out. What is left is handed to the scenario format's own validator,
    which is where a character dealt to two chairs is refused.
    """
    if not isinstance(described, Mapping):
        raise GameError("A custom game is described as an object.")

    problems: list[str] = []

    name = _text(described.get("name"), "the name", problems)

    if not name:
        problems.append("A custom game needs a name.")
    elif not identifier_for(name):
        problems.append(
            "That name has no letters or numbers in it, so there is nothing to "
            "call the file. Try adding a word."
        )

    seats = described.get("players")

    if not isinstance(seats, list):
        problems.append("Say who is playing: a list of seats.")
        seats = []
    elif not LEAST_SEATS <= len(seats) <= MOST_SEATS:
        problems.append(
            f"A game here has between {LEAST_SEATS} and {MOST_SEATS} players, "
            f"and this one has {len(seats)}."
        )

    players = [_seat(index, seat, problems) for index, seat in enumerate(seats)]

    expansions = described.get("sets")

    if expansions is None:
        expansions = []
    elif not isinstance(expansions, list):
        problems.append("The sets are a list.")
        expansions = []

    chosen = []

    for one in expansions:
        wanted = _text(one, "a set", problems)

        if wanted and wanted not in chosen:
            chosen.append(wanted)

    table: dict[str, int] = {}
    asked = described.get("table")

    if asked is None:
        asked = {}
    elif not isinstance(asked, Mapping):
        problems.append("The table settings are an object.")
        asked = {}

    for key in ("souls_to_win", "monster_slots", "shop_slots"):
        value = _whole(asked.get(key), key.replace("_", " "), problems)

        if value is not None:
            table[key] = value

    seed = _whole(described.get("seed"), "the seed", problems)

    data: dict[str, Any] = {
        "format": "fsme-scenario",
        "version": 1,
        "id": identifier_for(name) if name else "",
        "name": name,
        "players": players,
    }

    if chosen:
        data["content"] = {"expansions": chosen}

    if table:
        data["table"] = table

    if seed is not None:
        data["seed"] = seed

    description = _text(described.get("description"), "the description", problems)

    if description:
        data["description"] = description

    if not problems:
        problems.extend(validate(data))

    if problems:
        raise GameError(problems[0], problems)

    return parse(data)


def _seat(index: int, seat: Any, problems: list[str]) -> dict[str, Any]:
    where = f"Player {index + 1}"

    if not isinstance(seat, Mapping):
        problems.append(f"{where} is described as an object.")

        return {}

    written: dict[str, Any] = {}

    for key, what in (
        ("name", "name"),
        ("character", "character"),
        ("starting_item", "starting item"),
    ):
        value = _text(seat.get(key), f"{where}'s {what}", problems)

        if value:
            written[key] = value

    for key, what in (("coins", "starting cents"), ("loot", "starting loot")):
        number = _whole(seat.get(key), f"{where}'s {what}", problems)

        if number is not None:
            written[key] = number

    return written


def _text(value: Any, what: str, problems: list[str]) -> str:
    if value is None:
        return ""

    if not isinstance(value, str):
        problems.append(f"{what[0].upper()}{what[1:]} is text.")

        return ""

    return value.strip()


def _whole(value: Any, what: str, problems: list[str]) -> int | None:
    """
    A whole number, or nothing when the box was left blank.

    A number typed into a page can arrive as a number or as its digits; either
    is read. Anything else — a fraction, a word, ``true`` — is refused rather
    than rounded or guessed at, and a negative number is refused here so that
    the person is told in these words rather than the format's.
    """
    if value is None or value == "":
        return None

    if isinstance(value, bool):
        problems.append(f"{what[0].upper()}{what[1:]} is a whole number.")

        return None

    if isinstance(value, int):
        number = value
    elif isinstance(value, str) and value.strip().isdecimal():
        try:
            number = int(value.strip())
        except ValueError:
            number = -1
    else:
        problems.append(f"{what[0].upper()}{what[1:]} is a whole number.")

        return None

    if number < 0:
        problems.append(f"{what[0].upper()}{what[1:]} cannot be negative.")

        return None

    return number


# ----------------------------------------------------------------------
# Keeping them
# ----------------------------------------------------------------------


def save_game(described: Any, *, replace: bool = False) -> dict[str, Any]:
    """
    Keep a custom game under the name it was given.

    A name already used is refused unless the page says it means to replace
    it, so that saving a new game cannot quietly throw an old one away. The
    file is written beside itself and moved into place, so it is never half a
    game.
    """
    scenario = scenario_from(described)
    path = _game_file(scenario.id)

    if path.exists() and not replace:
        raise GameError(f"You already have a custom game called {scenario.name!r}.")

    body = json.dumps(scenario.to_dict(), indent=2) + "\n"

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _keep(path, body)
    except OSError as error:
        raise GameError(f"The game could not be saved: {error}") from None

    return {"id": scenario.id, "name": scenario.name, "where": str(path)}


def load_game(identifier: str) -> Scenario:
    """
    Read one kept game back, or say why it cannot be.
    """
    path = _existing(identifier)

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise GameError(f"The game could not be read: {error}") from None

    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise GameError(f"The file for this game is not JSON: {error}") from None

    try:
        return parse(data)
    except ScenarioError as error:
        reasons = str(error).splitlines()

        raise GameError(
            "The file for this game is not a game this build can read.", reasons
        ) from None


def delete_game(identifier: str) -> None:
    """
    Throw a kept game away.
    """
    path = _existing(identifier)

    try:
        path.unlink()
    except OSError as error:
        raise GameError(f"The game could not be deleted: {error}") from None


def list_games(library: ContentLibrary) -> list[dict[str, Any]]:
    """
    Every kept game, each saying whether it can be dealt from what is loaded.

    A file that cannot be read is listed rather than skipped, with the reason:
    a game that silently vanished from the list would be a game somebody
    remembers saving and cannot find.
    """
    directory = games_directory()

    if not directory.is_dir():
        return []

    listed: list[dict[str, Any]] = []

    for path in sorted(directory.glob("*.json")):
        identifier = path.stem

        try:
            scenario = load_game(identifier)
        except GameError as error:
            listed.append(
                {
                    "id": identifier,
                    "name": identifier,
                    "ready": False,
                    "problems": error.problems,
                }
            )

            continue

        problems = availability(scenario, library)

        listed.append(
            {
                "id": identifier,
                "name": scenario.name or identifier,
                "ready": not problems,
                "problems": problems,
                "game": scenario.to_dict(),
            }
        )

    return listed


def _game_file(identifier: str) -> Path:
    plain = identifier_for(identifier)

    if not plain:
        raise GameError(f"{identifier!r} is not the name of a custom game.")

    return games_directory() / f"{plain}.json"


def _existing(identifier: str) -> Path:
    path = _game_file(identifier)

    if not path.is_file():
        raise GameError(f"There is no custom game called {identifier!r}.")

    return path


def _keep(path: Path, body: str) -> None:
    beside = path.with_name(f".{path.name}.writing")

    try:
        with beside.open("w", encoding="utf-8", newline="\n") as file:
            file.write(body)
            file.flush()
            os.fsync(file.fileno())

        os.replace(beside, path)
    except BaseException:
        beside.unlink(missing_ok=True)
        raise


# ----------------------------------------------------------------------
# Whether a game can still be dealt
# ----------------------------------------------------------------------


def availability(scenario: Scenario, library: ContentLibrary) -> list[str]:
    """
    What stands between a kept game and being dealt from what is loaded now.

    A quick reading of the same things the deal checks — the sets are there,
    each named character and starting item is in them, there are characters
    enough for the chairs — so a list can mark a game before anybody presses
    Start. It is not the verdict: the deal is, and anything this misses is
    refused there in the engine's own words.
    """
    problems: list[str] = []

    wanted = scenario.content.expansions
    missing = [one for one in wanted if one not in library.expansions]

    for one in missing:
        problems.append(f"The set {one!r} is not loaded any more.")

    if missing:
        return problems

    dealt = library.only(wanted) if wanted else library

    characters = {
        definition.id for definition in dealt.cards_of(CardType.CHARACTER)
    }
    items = {
        definition.id for definition in dealt.cards_of(CardType.STARTING_ITEM)
    }

    for index, seat in enumerate(scenario.players):
        who = seat.name or f"Player {index + 1}"

        if seat.character and seat.character not in characters:
            problems.append(
                f"{who} plays {seat.character!r}, which is not in the chosen sets."
            )

        if seat.starting_item and seat.starting_item not in items:
            problems.append(
                f"{who} starts with {seat.starting_item!r}, which is not a "
                f"starting item in the chosen sets."
            )

    if len(characters) < len(scenario.players):
        problems.append(
            f"{len(scenario.players)} players need {len(scenario.players)} "
            f"characters, and the chosen sets have {len(characters)}."
        )

    return problems


def catalogue(library: ContentLibrary) -> dict[str, Any]:
    """
    What a form can offer: every loaded set, with its characters and items.
    """
    return {
        "sets": [
            {
                "id": expansion.id,
                "name": expansion.manifest.name,
                "characters": _named(expansion.by_type(CardType.CHARACTER)),
                "starting_items": _named(
                    expansion.by_type(CardType.STARTING_ITEM)
                ),
            }
            for expansion in sorted(library, key=lambda one: one.id)
        ],
        "least": LEAST_SEATS,
        "most": MOST_SEATS,
    }


def _named(definitions: Any) -> list[dict[str, str]]:
    return sorted(
        ({"id": one.id, "name": one.name} for one in definitions),
        key=lambda one: (one["name"].lower(), one["id"]),
    )
