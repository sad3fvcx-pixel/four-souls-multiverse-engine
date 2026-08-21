# src/fsme/lab/desk/author.py

"""
Making, checking and keeping an author's cards.

What comes in is what somebody filled in on a page; what goes out is an
ordinary FSME set — a directory with a manifest and card files, exactly what
anybody writing JSON by hand would produce. A set made here and a set made in a
text editor are the same thing, and either opens in the other.

Nothing here decides whether a card is allowed. It builds the card and hands it
to the same validation every other card goes through, so there is one set of
rules and this is not a second one.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from fsme.cards import validate_card
from fsme.content.workspace import (
    card_identifier,
    identifier_for,
    sets_directory,
)
from fsme.runtime.vocabulary import engine_vocabulary

CARDS = "cards"
MANIFEST = "manifest.json"
SCHEMA = "1"

NUMBERS = {
    "monster": ("health", "attack", "roll"),
    "treasure": ("cost",),
    "room": (),
    "character": ("health",),
    "loot": (),
    "curse": (),
}
"""
The printed numbers each kind of card carries.

A monster has hit points and a difficulty; a loot card has neither, and asking
somebody for one would be asking them to invent a fact about their card.
"""


__all__ = [
    "AuthorError",
    "build_card",
    "check_card",
    "delete_card",
    "delete_set",
    "make_set",
    "save_card",
    "sets",
    "sets_directory",
]


class AuthorError(ValueError):
    """
    Something the author did that they can be told about plainly.
    """


# ----------------------------------------------------------------------
# Sets
# ----------------------------------------------------------------------


def sets() -> list[dict[str, Any]]:
    """
    Every set the author has made, with how many cards each holds.
    """
    root = sets_directory()
    found: list[dict[str, Any]] = []

    for directory in sorted(root.iterdir()):
        manifest = directory / MANIFEST

        if not manifest.is_file():
            continue

        try:
            described = json.loads(manifest.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        found.append(
            {
                "id": str(described.get("id", directory.name)),
                "name": str(described.get("name", directory.name)),
                "cards": [card["name"] for card in cards_in(directory)],
                "where": str(directory),
            }
        )

    return found


def make_set(name: str) -> dict[str, Any]:
    """
    Start a new set, named the way a person would name it.

    The identifier is derived rather than asked for. An author names their
    set; needing an identifier as well would be asking the same question
    twice, in a form only one of the answers may take.
    """
    readable = name.strip()

    if not readable:
        raise AuthorError("A set needs a name.")

    identifier = identifier_for(readable)

    if not identifier:
        raise AuthorError(
            "That name has no letters or numbers in it, so there is nothing "
            "to call the folder. Try adding a word."
        )

    directory = sets_directory() / identifier

    if directory.exists():
        raise AuthorError(f"You already have a set called {readable!r}.")

    (directory / CARDS).mkdir(parents=True)
    (directory / MANIFEST).write_text(
        json.dumps(
            {
                "id": identifier,
                "name": readable,
                "version": "1.0.0",
                "schema_version": SCHEMA,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return {"id": identifier, "name": readable, "cards": [], "where": str(directory)}


def delete_set(identifier: str) -> None:
    """
    Throw a whole set away.
    """
    directory = _set_directory(identifier)

    shutil.rmtree(directory)


def _set_directory(identifier: str) -> Path:
    directory = sets_directory() / identifier_for(identifier)

    if not (directory / MANIFEST).is_file():
        raise AuthorError(f"There is no set called {identifier!r}.")

    return directory


# ----------------------------------------------------------------------
# Cards
# ----------------------------------------------------------------------


def cards_in(directory: Path) -> list[dict[str, Any]]:
    """
    Every card in one set, as it was written.
    """
    found: list[dict[str, Any]] = []

    for path in sorted((directory / CARDS).glob("*.json")):
        try:
            body = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        for card in body.get("cards", ()) if isinstance(body, dict) else ():
            found.append(card)

    return found


def save_card(described: Any) -> dict[str, Any]:
    """
    Build a card from what somebody filled in, check it, and keep it.

    Checked before it is kept: a card that would not load is not written, so
    the set on disk always loads. The author sees what is wrong and their old
    card is still there.
    """
    card = build_card(described)
    problems = check_card(card)

    if problems:
        return {"saved": False, "problems": problems, "card": card}

    directory = _set_directory(str(described.get("set", "")))
    path = directory / CARDS / f"{card['id']}.json"
    path.write_text(
        json.dumps({"cards": [card]}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return {"saved": True, "problems": [], "card": card, "where": str(path)}


def delete_card(set_id: str, card_id: str) -> None:
    directory = _set_directory(set_id)
    path = directory / CARDS / f"{card_id}.json"

    if path.is_file():
        path.unlink()


def check_card(card: Any) -> list[str]:
    """
    Everything wrong with a card, from the engine that will have to load it.
    """
    vocabulary = engine_vocabulary()

    return validate_card(
        card,
        known_effects=vocabulary.effects,
        known_triggers=vocabulary.triggers,
        known_conditions=vocabulary.conditions,
        known_targets=vocabulary.targets,
        shapes=vocabulary.shapes,
        condition_shapes=vocabulary.condition_shapes,
        target_shapes=vocabulary.target_shapes,
        node_shapes=vocabulary.node_shapes,
    )


# ----------------------------------------------------------------------
# Turning a filled-in form into a card
# ----------------------------------------------------------------------


def build_card(described: Any) -> dict[str, Any]:
    """
    The card a person described, written the way the loader expects.

    Everything an author never sees is added here: the identifier, the
    expansion, the schema version, the shape of an ability. What they typed is
    a name, some numbers and a list of things that happen.
    """
    if not isinstance(described, dict):
        raise AuthorError("Nothing was sent.")

    set_id = identifier_for(str(described.get("set", "")))
    name = str(described.get("name", "")).strip()
    kind = str(described.get("kind", "loot"))

    if not set_id:
        raise AuthorError("Which set is this card for?")

    if not name:
        raise AuthorError("Give the card a name.")

    card: dict[str, Any] = {
        "id": card_identifier(set_id, kind, name),
        "name": name,
        "type": kind,
        "expansion": set_id,
        "schema_version": SCHEMA,
        "abilities": [],
    }

    for number in NUMBERS.get(kind, ()):
        written = described.get("numbers", {}).get(number)

        if written not in (None, ""):
            card[number] = int(written)

    text = str(described.get("text", "")).strip()

    if text:
        card["metadata"] = {"text": text}

    ability = _ability(described.get("ability"))

    if ability is not None:
        card["abilities"] = [ability]

    return card


def _ability(described: Any) -> dict[str, Any] | None:
    """
    One ability, from a trigger and a list of things that happen.
    """
    if not isinstance(described, dict):
        return None

    effects = _effects(described.get("effects", ()))

    if not effects:
        return None

    ability: dict[str, Any] = {
        "trigger": str(described.get("trigger", "on_play")),
        "effects": effects,
    }

    targets = _targets(described.get("targets", ()))

    if targets:
        ability["targets"] = targets

    return ability


def _targets(described: Any) -> list[dict[str, Any]]:
    """
    The things an ability picks out before it does anything.

    Each gets a name so that effects can point at it. The author never types
    that name — the page shows them "the player chosen above" and this writes
    the `as` behind it.
    """
    if not isinstance(described, (list, tuple)):
        return []

    written: list[dict[str, Any]] = []

    for index, one in enumerate(described):
        if not isinstance(one, dict):
            continue

        target = str(one.get("id", ""))

        if not target:
            continue

        body: dict[str, Any] = dict(one.get("fields", {}) or {})
        body["as"] = str(one.get("as") or f"chosen_{index + 1}")

        written.append({target: body})

    return written


def _effects(described: Any) -> list[Any]:
    """
    The list of things that happen, in order.

    A branch is one of them — "depending on the roll" is a thing that happens
    as much as "gain 3 cents" is, and a person building a card thinks of it
    that way even though the engine calls it a control node.
    """
    if not isinstance(described, (list, tuple)):
        return []

    written: list[Any] = []

    for one in described:
        if not isinstance(one, dict):
            continue

        if "branch" in one:
            written.append(_branch(one["branch"]))

            continue

        effect = str(one.get("id", ""))

        if not effect:
            continue

        node: dict[str, Any] = {"effect": effect}
        node.update(_written_fields(one.get("fields", {})))

        aimed = str(one.get("target", "") or "")

        if aimed:
            node["target"] = aimed

        written.append(node)

    return written


def _branch(described: Any) -> dict[str, Any]:
    """
    "Depending on …" — one condition, and what happens either way.
    """
    if not isinstance(described, dict):
        raise AuthorError("A branch needs something to depend on.")

    condition = described.get("condition")

    if not isinstance(condition, dict) or not condition.get("id"):
        raise AuthorError("Say what the branch depends on.")

    asked = str(condition["id"])
    fields = _written_fields(condition.get("fields", {}))

    node: dict[str, Any] = {
        "if": [{asked: fields} if fields else asked],
        "then": _effects(described.get("then", ())),
    }

    otherwise = _effects(described.get("else", ()))

    if otherwise:
        node["else"] = otherwise

    return node


def _written_fields(fields: Any) -> dict[str, Any]:
    """
    What somebody typed, with blanks left out.

    A field left empty means "you did not say", which for nearly every
    parameter means the effect's own default — not zero, and not an empty
    string.
    """
    if not isinstance(fields, dict):
        return {}

    kept: dict[str, Any] = {}

    for name, value in fields.items():
        if value in (None, ""):
            continue

        kept[str(name)] = value

    return kept
