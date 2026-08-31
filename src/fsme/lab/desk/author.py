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

import hashlib
import json
import os
import re
import shutil
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from fsme.cards import validate_card
from fsme.content.vocabulary import (
    ABILITY,
    BY_BINDING,
    BY_PLAYER_OF,
    CARD,
    CONDITION,
    COST,
    MODE,
    NAMED_COUNT,
    STATIC,
    STEP,
    TARGET,
    VALUES,
    WORKED_OUT,
)
from fsme.content.workspace import (
    card_identifier,
    identifier_for,
    sets_directory,
)
from fsme.runtime.interpreter import SHORTHAND
from fsme.runtime.vocabulary import engine_vocabulary

CARDS = "cards"
MANIFEST = "manifest.json"
SCHEMA = "1"

OPENED = "opened"
"""
Where a card that came off disk says which card it is and what it was.

A card being made has nothing here — there is no file it came from. A card
that was opened carries it back untouched, and it is the only thing that can
tell one from the other.
"""

A_PLAIN_NAME = re.compile(r"[a-z0-9][a-z0-9_-]*")
"""
What an identifier may look like when it is about to become a file name.

Identifiers are made here, from `card_identifier`, and never typed. But one
arrives back through `OPENED` from outside, and an identifier is joined to a
directory to make a path — so it is checked on the way in rather than trusted
because of where it usually comes from.
"""

__all__ = [
    "AuthorError",
    "build_card",
    "check_card",
    "delete_card",
    "delete_set",
    "make_set",
    "open_card",
    "save_card",
    "said_by_the_engine",
    "read_card",
    "sets",
    "sets_directory",
    "UnreadableCard",
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
                # Name and identifier both. A person reads the one and
                # opening a card needs the other, and a list that carried only
                # the name could be looked at and not opened.
                "cards": [
                    {"id": str(card.get("id", "")), "name": str(card.get("name", ""))}
                    for card in cards_in(directory)
                ],
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
    return [card for _, card in _each_card(directory)]


def _each_card(directory: Path) -> Iterator[tuple[Path, dict[str, Any]]]:
    """
    Every card in one set, with the file it came out of.

    Which file a card is in is not a detail: keeping a card means writing over
    the one it was read from, and a card read from a file named after
    something else is a card this cannot keep.
    """
    for path in sorted((directory / CARDS).glob("*.json")):
        try:
            body = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        for card in body.get("cards", ()) if isinstance(body, dict) else ():
            yield path, card


def open_card(set_id: str, card_id: str) -> dict[str, Any]:
    """
    A card the author already has, as the thing they filled in to make it.

    Read rather than converted: what comes back is the same author state a
    card being made carries, so whatever draws one draws this. A card that
    cannot be read faithfully raises instead of arriving half-read.
    """
    directory = _set_directory(set_id)
    wanted = str(card_id)

    for path, card in _each_card(directory):
        if str(card.get("id", "")) != wanted:
            continue

        return {
            "set": identifier_for(set_id),
            "card": read_card(card)["card"],
            # Which card this is, and what its file said at the moment it was
            # read. Neither can be worked out again later: the first because a
            # card may be renamed and is still the same card, the second
            # because by then the file may be somebody else's.
            OPENED: _identity(path, wanted),
        }

    raise AuthorError(f"There is no card called {wanted!r} in that set.")


def _identity(path: Path, card_id: str) -> dict[str, str]:
    """
    Which card this is, and what its file says at this moment.
    """
    return {
        "card": card_id,
        "file": path.name,
        "fingerprint": _fingerprint(path),
    }


def _fingerprint(path: Path) -> str:
    """
    What a file says, short enough to carry and compare.

    Empty for a file that is not there, which is a difference like any other:
    a card that was deleted while somebody had it open has changed.
    """
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def save_card(described: Any) -> dict[str, Any]:
    """
    Build a card from what somebody filled in, check it, and keep it.

    Three things have to be true before anything is written, and each of them
    is somebody's work if it is not:

    - the card loads, so the set on disk always loads;
    - the file is still the one that was opened, so nobody else's change is
      thrown away;
    - the write either happens or does not, so a card is never half of itself.

    When one of them fails nothing is written at all, and what is on disk is
    exactly what was there before.
    """
    card = build_card(described)
    problems = check_card(card)

    if problems:
        return {"saved": False, "problems": problems, "card": card}

    directory = _set_directory(str(described.get("set", "")))
    path = _card_file(directory, str(card["id"]))
    changed = _changed_underneath(described, path)

    if changed:
        return {
            "saved": False,
            "problems": [changed],
            "card": card,
            "changed": True,
        }

    clashes = _already_there(described, directory, card)

    if clashes:
        return {"saved": False, "problems": [clashes], "card": card}

    _keep(path, json.dumps({"cards": [card]}, indent=2, ensure_ascii=False) + "\n")

    return {
        "saved": True,
        "problems": [],
        "card": card,
        "where": str(path),
        # What the card is now. Keeping a card makes its file say something
        # new, which is the very thing the check above refuses — so whoever
        # kept it is given what it says now, and can keep it again without
        # being told it changed underneath them by themselves. It is also
        # where a card made here first gets an identity to hold on to.
        OPENED: _identity(path, str(card["id"])),
    }


def _card_file(directory: Path, identifier: str) -> Path:
    """
    The file one card is kept in, which is named after the card.
    """
    return directory / CARDS / f"{_a_plain_name(identifier)}.json"


def _a_plain_name(identifier: str) -> str:
    """
    An identifier, refused unless it can only ever name a file in one place.
    """
    if not A_PLAIN_NAME.fullmatch(identifier):
        raise AuthorError(f"{identifier!r} is not the name of a card.")

    return identifier


def _already_there(
    described: Mapping[str, Any],
    directory: Path,
    card: Mapping[str, Any],
) -> str:
    """
    Why a card being made must not be written, or nothing.

    A card that was opened is the card that is already there, and says so by
    carrying its identity — nothing to check. A card being made has never been
    saved, so it has no identity and nothing to compare a file against, and
    its identifier is made out of its name and its type. Two cards called the
    same thing in one set therefore want the same identifier, and the second
    would take the first one's place with nothing said.

    What clashes is the identifier rather than the file name, because a set
    written by hand may keep its cards in files named anything at all, and a
    card is already there wherever it is written.
    """
    if isinstance(described.get(OPENED), Mapping):
        return ""

    wanted = str(card.get("id", ""))

    if not any(str(one.get("id", "")) == wanted for _, one in _each_card(directory)):
        return ""

    return (
        f"You already have a card called {card.get('name', '')!s} in that set, "
        "and this would have been written over it. Nothing has been written. "
        "Call this one something else, or open the one you have and change it."
    )


def _changed_underneath(described: Mapping[str, Any], path: Path) -> str:
    """
    Why this card must not be written yet, or nothing.

    A card being made has no file behind it and nothing to disagree with. A
    card that was opened carries what its file said; if the file says something
    else now, somebody else wrote it in the meantime, and the two changes
    cannot both be kept. Refusing loses neither — merging them is not something
    anything here can do, and overwriting is choosing for a person who is not
    being asked.
    """
    opened = described.get(OPENED)

    if not isinstance(opened, Mapping):
        return ""

    if str(opened.get("file", "")) != path.name:
        return (
            "That card is kept in a file with a different name, so keeping it "
            "would leave the one it came from behind. Nothing has been "
            "written."
        )

    was = str(opened.get("fingerprint", ""))
    now = _fingerprint(path)

    if now == was:
        return ""

    if not now:
        return (
            "That card is no longer in the set — it was removed after you "
            "opened it. Nothing has been written, so nothing was put back."
        )

    return (
        "That card changed on disk after you opened it. Nothing has been "
        "written, so neither change is lost — open it again to see what it "
        "says now."
    )


def _keep(path: Path, body: str) -> None:
    """
    Write a card so that it is never half written.

    The card goes to a name beside its own, is pushed all the way to the disk,
    and only then becomes the card — one step the operating system either does
    or does not do. Writing over the card directly would empty it first, and a
    machine that stopped there would leave a set that no longer loads.
    """
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


def delete_card(set_id: str, card_id: str) -> None:
    directory = _set_directory(set_id)
    path = _card_file(directory, str(card_id))

    if path.is_file():
        path.unlink()


def check_card(card: Any) -> list[str]:
    """
    Everything wrong with a card, from the engine that will have to load it.

    Plus one thing the engine does not mind and a person would: a card with no
    rules at all. That is perfectly valid content — the shipped sets are full
    of cards whose text has not been implemented — but somebody who has just
    filled in a form did not mean to make one, and telling them it is ready
    would be telling them their card works.
    """
    vocabulary = engine_vocabulary()

    if isinstance(card, dict) and not (card.get("abilities") or card.get("statics")):
        return [
            "This card does not do anything yet — say what happens when it "
            "is played."
        ]

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


def in_plain_words(problems: list[str]) -> list[str]:
    """
    Say what is wrong in the words the person used, not the engine's.

    A validation message names a path through a file and an effect by its
    identifier — ``abilities[0].effects[0].amount: 'gain_coins' takes a whole
    number…``. Neither is anything the author wrote: they picked "Add coins to
    a player" from a list and typed into a box labelled "how many cents". So
    the message is rebuilt out of the things they chose.

    The engine's own sentence is kept whenever nothing better can be made,
    because a plain message that has lost the detail is worse than a technical
    one that still has it.
    """
    vocabulary = engine_vocabulary()

    return [_said_plainly(problem, vocabulary) for problem in problems]


ABOUT_A_PARAMETER = (" takes ", " needs '", " wants ", " has no ")
"""
How a validation message says it is about one parameter of one thing.

The three verbs the checker uses, plus the one for a value outside a domain.
A message using none of them is about the card's shape rather than about a box
somebody filled in, and rewriting it as though it named a box names the path
instead.
"""


def _said_plainly(problem: str, vocabulary: Any) -> str:
    """
    One message, with identifiers swapped for the words a person saw.

    A validation message is colon-separated: where it is, then what is wrong.
    The last part carries the complaint and the one before it carries the path,
    whose final step is the field. Both are needed — a message that says a
    number is wanted without saying *which* box is a message that sends
    somebody hunting.
    """
    parts = [part.strip() for part in problem.split(": ") if part.strip()]

    if not parts:
        return problem

    complaint = parts[-1]
    path = parts[-2] if len(parts) > 1 else ""
    field = path.rsplit(".", 1)[-1] if "." in path else ""

    if not any(verb in complaint for verb in ABOUT_A_PARAMETER):
        # Not a complaint about a box, so there is no box to name. Rebuilding
        # it around the last step of the path would put a path there instead —
        # "Effects[0] needs this 'if' has nothing to do" is what that reads
        # like.
        return complaint[:1].upper() + complaint[1:]

    for name in sorted(vocabulary.effects, key=len, reverse=True):
        if f"'{name}'" not in complaint:
            continue

        shape = vocabulary.shape(name)
        parameter = shape.params.get(field) if shape is not None else None
        # Only a parameter the effect actually has. A path ending in a misspelt
        # key names no box, and calling it one turns "takes no parameter called
        # 'amont'" into "Amont needs no parameter called 'amont'".
        label = parameter.describes or field.replace("_", " ") if parameter else ""
        wanted = (
            complaint.split(" takes ", 1)[-1]
            if " takes " in complaint
            else complaint
        )
        wanted = wanted.replace(" here, and the card gives", " — you wrote")

        if label:
            return f"{label.capitalize()} needs {wanted}."

        described = getattr(_spec(name), "description", "") or name
        return f"{described.rstrip('.')}: {wanted}."

    return complaint[:1].upper() + complaint[1:]


def said_by_the_engine(refused: Exception) -> str:
    """
    What the engine stopped on, said to the person who pressed the button.

    An engine message names the effect that refused and why —
    ``effect 'watch_for' failed: watch_for requires the effects it will run``.
    The chain of causes belongs in a log; what an author needs is the last
    thing said, which is the one that names what is missing.
    """
    said = str(refused).split(": ")[-1].strip() or str(refused)

    return f"The engine would not play this card: {said}."


def _spec(name: str) -> Any:
    from fsme.effects import builtin_registry

    try:
        return builtin_registry().spec(name)
    except Exception:
        return None


# ----------------------------------------------------------------------
# Turning a filled-in form into a card
# ----------------------------------------------------------------------


def build_card(described: Any) -> dict[str, Any]:
    """
    The card a person described, written the way the loader expects.

    What a card is made of is the card's own shape — the rules it follows, the
    numbers it changes while it is in play, the numbers printed on it — so this
    reads that shape and writes whatever the shape says a card may have.
    Nothing below knows that a card has abilities: a part added to a card is a
    field added to ``CardDefinition``, and this widens the moment it is.

    Four things are added on top, because none of them is anybody's answer: the
    identifier, the set, the schema version, and the empty list that says a
    card without rules is an unfinished card rather than a broken file.

    The identifier is the card's own and the name is what it is called, and
    they are not the same thing. A name gives a card its identifier once, when
    there is nothing else to make one out of. After that the card carries it,
    and renaming a card changes what it is called and not which card it is —
    which matters because a scenario file names cards by identifier, written
    by hand, and a card that quietly took a new one would stop being the card
    those files mean.
    """
    if not isinstance(described, dict):
        raise AuthorError("Nothing was sent.")

    set_id = identifier_for(str(described.get("set", "")))

    if not set_id:
        raise AuthorError("Which set is this card for?")

    shape = engine_vocabulary().node_shape(CARD)
    written = _written_node(shape, _as_a_card(described), None)

    name = str(written.get("name", "")).strip()

    if not name:
        raise AuthorError("Give the card a name.")

    kind = str(written.get("type") or "loot")
    card: dict[str, Any] = {
        "id": _identity_of(described) or card_identifier(set_id, kind, name),
        "name": name,
        "type": kind,
        "expansion": set_id,
        "schema_version": SCHEMA,
    }
    card.update({key: value for key, value in written.items() if key not in card})
    card.setdefault("abilities", [])

    return card


def _identity_of(described: Mapping[str, Any]) -> str:
    """
    The identifier a card already has, or nothing if it has never had one.
    """
    opened = described.get(OPENED)

    if not isinstance(opened, Mapping):
        return ""

    return _a_plain_name(str(opened.get("card", "")))


def _as_a_card(described: Mapping[str, Any]) -> dict[str, Any]:
    """
    What somebody filled in, as the one node the card shape describes.

    A page sends a card the way it sends everything else — what was typed under
    ``fields``, what was pointed at under ``groups``. The older form sent one
    ability with the card's few facts beside it at the top, and is still read
    here: a page that has not been reloaded is not a mistake, and neither is a
    card somebody saved out of one yesterday.
    """
    given = described.get("card")

    if isinstance(given, dict):
        return dict(given)

    fields: dict[str, Any] = {
        "name": described.get("name", ""),
        "type": described.get("kind", "loot"),
        **(described.get("numbers") or {}),
    }

    text = str(described.get("text", "")).strip()

    if text:
        fields["metadata"] = {"text": text}

    ability = described.get("ability")

    # A page that sends one ability sends it before anything has been put in
    # it, so an empty one is a card nobody has started rather than a rule that
    # does nothing. A page that sends a list says the difference itself: an
    # ability somebody added and left empty is one they can be told about.
    if isinstance(ability, dict) and ability.get("effects"):
        fields["abilities"] = [
            {
                "fields": {"trigger": "on_play", **ability},
                "groups": ability.get("groups", {}),
            }
        ]

    return {"fields": fields, "groups": {}}


def _written_node(
    shape: Any,
    described: Any,
    aimed: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """
    One node of the language, written out of the shape describing it.

    Three sorts of field, and the shape says which each one is: a list of more
    of the language, one nested node, or a value. Nothing below is about
    abilities, or about ``if``, or about any effect — the same function writes
    an ability, a branch, a mode and a cost, because they are the same kind of
    thing described four times.
    """
    if not isinstance(described, dict) or shape is None:
        return {}

    given = described.get("fields", described)
    picked = described.get("groups", {})
    written: dict[str, Any] = {}

    for name, parameter in shape.params.items():
        if parameter.written_as == BY_BINDING:
            # Never asked for — that is what this says, and it still holds:
            # nothing offers a box for it. But a card that wrote one said
            # something, and saying it back is not asking. The sibling writer
            # that puts a target's name back has always done exactly this,
            # for the same reason: without the name, nothing can point at it.
            said = given.get(name)

            if said not in (None, "", [], {}):
                written[name] = said

            continue

        if parameter.instead_of and not parameter.names_the_node:
            # A second spelling of a question asked elsewhere. Unless it is
            # also the key that names its node: `{"may": [...]}` is the second
            # spelling of "what happens", and it is also the only thing that
            # says the node is a `may` at all. Skipping it wrote `{"may": []}`
            # — a card that asks and then does nothing either way.
            continue

        if parameter.a_list_of:
            body = _written_body(parameter.a_list_of, given.get(name), aimed)

            if body or parameter.names_the_node:
                written[name] = body

            continue

        if parameter.shaped_like in _NESTED_SHAPES:
            inside = _written_node(
                engine_vocabulary().node_shape(parameter.shaped_like),
                {"fields": given.get(name) or {}},
                aimed,
            )

            if inside:
                written[name] = inside

            continue

        value = given.get(name)

        # A question another answer has already settled is a question this card
        # must not answer twice. A page keeps what was typed so that changing
        # the other answer gives it back; the card is where it may not appear.
        if _settled(parameter, shape, given):
            continue

        if value not in (None, "", [], {}):
            written[name] = value

    written.update(_given(shape, {"fields": {}, "groups": picked}, aimed))

    return written


_NESTED_SHAPES = (COST, NAMED_COUNT, WORKED_OUT, MODE)
"""
The named shapes a field may hold one of, as opposed to a target.

A target is nested too and is written quite differently — it is bound by the
ability and pointed at — so it goes through `_pick_out` and not through here.
"""


def _written_body(
    kind: str,
    described: Any,
    aimed: list[dict[str, Any]] | None,
) -> list[Any]:
    """
    A list of nodes of one kind, written out.

    Four kinds, and each of them is a thing the catalogue already describes,
    so the only thing decided here is which description to look the node up in.
    """
    if not isinstance(described, (list, tuple)):
        return []

    written: list[Any] = []

    for one in described:
        node = _written_one(kind, one, aimed)

        if node is not None:
            written.append(node)

    return written


def _written_one(kind: str, described: Any, aimed: Any) -> Any:
    """
    One node of one kind.

    Four kinds of answer and the metadata says which each is. A kind the engine
    describes with a shape of its own — a mode, an ability, a static — has no
    name inside it to look up and is simply written out of that shape. The
    other three carry a name and are written the way their registry reads them.
    """
    if not isinstance(described, dict):
        return described if isinstance(described, str) else None

    vocabulary = engine_vocabulary()
    shape = vocabulary.node_shape(kind)

    if shape is not None:
        return _written_part(shape, described, aimed)

    name = str(described.get("id", ""))

    if not name:
        return None

    if kind == CONDITION:
        condition = vocabulary.condition_shape(name)
        body = _given(condition, described, aimed)

        if not body:
            return name

        # A condition holding other conditions is written the long way. The
        # short way — `{"not": [...]}` — means the list *is* the body, so a
        # body written under it reads as one more condition and the card grows
        # a layer every time it is opened. Which conditions those are is the
        # shape's own answer, not a list kept here.
        holds = any(
            key in body
            for key, parameter in (
                condition.params.items() if condition is not None else ()
            )
            if parameter.a_list_of
        )

        return {CONDITION: name, **body} if holds else {name: body}

    if kind == TARGET:
        body = _given(vocabulary.target_shape(name), described, aimed)
        body["as"] = str(described.get("as") or f"chosen_{id(described) % 997}")

        return {name: body}

    return _written_step(name, described, aimed)


def _written_part(
    shape: Any,
    described: Any,
    aimed: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """
    One node of a named shape, given the names it is allowed to make.

    A mode belongs to the ability that holds it and shares everything with it —
    a group bound before a choice is there to be pointed at inside one. An
    ability and a static do not: the engine builds a context per ability and
    shares nothing between them, so each starts with no names and keeps the
    ones it makes. ``own_names`` is where that is said, and this reads it
    rather than knowing which is which.

    Where the names go is read off the shape too. Whatever a part of a card
    keeps its chosen groups under is the field the shape describes as a list of
    targets; a part with no such field cannot choose anything, and whatever is
    drawing it has to say so rather than take an answer nowhere can hold.
    """
    if not shape.own_names:
        return _written_node(shape, described, aimed)

    kept = _chooses(shape)
    ours: list[dict[str, Any]] = []
    node = _written_node(shape, described, ours if kept else None)

    if ours:
        node[kept] = list(node.get(kept, ())) + ours

    return node


def _chooses(shape: Any) -> str:
    """
    Where this part of a card keeps the things it picks out, if it picks any.

    Empty for a static: nothing in one chooses anybody, which is why a static's
    conditions can only ask about the table and never about "them".
    """
    return next(
        (
            parameter.name
            for parameter in shape.params.values()
            if parameter.a_list_of == TARGET
        ),
        "",
    )


def _written_step(name: str, described: Any, aimed: Any) -> Any:
    """
    One thing that happens: an effect, or a control node holding more of them.

    Which it is comes from whether the engine describes it as an effect or as a
    node — the same question the interpreter asks when it reads the card.
    """
    vocabulary = engine_vocabulary()
    control = vocabulary.node_shape(name)

    if control is not None:
        inside = _written_node(control, described, aimed)
        head = next(
            (
                parameter
                for parameter in control.params.values()
                if parameter.names_the_node
            ),
            None,
        )

        if head is not None:
            # The key that makes this node what it is has to be there, whether
            # or not anybody filled it in. What "nothing yet" looks like is the
            # head's own kind: an empty body, a nought, a name not yet given.
            inside.setdefault(head.name, _nothing_yet(head))

        return inside

    node: dict[str, Any] = {"effect": name}
    node.update(_given(vocabulary.shape(name), described, aimed))

    pointed = str(described.get("target", "") or "")
    aim = str(described.get("aim", "") or "")

    if aim and aimed is not None:
        pointed = _pick_out(
            aim,
            _given(
                vocabulary.target_shape(aim),
                {
                    "fields": described.get("aim_fields", {}),
                    "groups": described.get("aim_groups", {}),
                },
                aimed,
            ),
            aimed,
            str(described.get("aim_name", "") or ""),
        )

    if pointed:
        node["target"] = pointed

    return node


def _nothing_yet(parameter: Any) -> Any:
    """
    What an unanswered key of this kind looks like written down.

    A card being built is allowed to be unfinished; what it may not be is a
    node the engine cannot recognise. So the key goes in with the emptiest
    value its own kind admits, and the checker says what is still missing.
    """
    if parameter.a_list_of:
        return []

    if parameter.kind == "a whole number":
        return 0

    if parameter.shaped_like or parameter.kind == "text":
        return ""

    return True


def _given(
    shape: Any,
    described: Any,
    aimed: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """
    Everything written beside one effect, condition or target.

    Two halves. What somebody typed comes through as it is. What they *pointed
    at* — a parameter naming a player or a card rather than carrying a value —
    arrives as a target they picked, and becomes two things: a group the
    ability chooses, and this parameter naming it.

    How it is named is the engine's own answer, read off the parameter rather
    than decided here. A target reads a bound group by its bare name; an effect
    is handed players as seat numbers and writes the one dynamic head that
    answers with a seat. Nothing in this function knows which effect it is
    looking at, and nothing in it may learn.
    """
    written = _without_the_moot(
        shape,
        _written_fields(
            described.get("fields", {}) if isinstance(described, dict) else {}
        ),
    )

    written = _written_inside(shape, written, aimed)

    picked = described.get("groups", {}) if isinstance(described, dict) else {}

    if not isinstance(picked, dict) or aimed is None or shape is None:
        return written

    vocabulary = engine_vocabulary()

    for key, pick in picked.items():
        parameter = shape.params.get(str(key))

        if parameter is None or not isinstance(pick, dict):
            continue

        target = str(pick.get("id", ""))

        if not target:
            continue

        inside = _given(vocabulary.target_shape(target), pick, aimed)
        name = _pick_out(target, inside, aimed, str(pick.get("name", "")))

        written[str(key)] = (
            {BY_PLAYER_OF: name}
            if parameter.written_as == BY_PLAYER_OF
            else name
        )

    return written


def _written_inside(
    shape: Any,
    written: dict[str, Any],
    aimed: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """
    Write out any answer that is itself a list of nodes.

    ``not``, ``and`` and ``or`` hold conditions, and say so — the shape calls
    the field a list of conditions. Without this the nodes inside went into the
    card as the page's own working data, and the checker refused the card with
    "unknown condition 'of'". Read off ``a_list_of`` rather than named, so this
    is not a fact about conditions but about anything the language describes
    that way.

    A body that comes out empty is left out rather than written empty, the way
    the sibling writer of a node already leaves one out. It matters because
    the two are not the same to the checker: an effect that requires a body
    and does not have the key is refused by name, and one whose key holds an
    empty list is a card that says it watches for nothing and passes. Anything
    this could not write is therefore something the card is told about, not
    something it loses quietly.
    """
    if shape is None:
        return written

    for name, value in list(written.items()):
        parameter = shape.params.get(name)

        if parameter is None or not parameter.a_list_of:
            continue

        body = _written_body(parameter.a_list_of, value, aimed)

        if body or parameter.names_the_node:
            written[name] = body
        else:
            del written[name]

    return written


def _without_the_moot(shape: Any, written: dict[str, Any]) -> dict[str, Any]:
    """
    Leave out what the other answers have already settled.

    A form greys out a question another answer makes meaningless, and the card
    has to agree: "heal 3, and heal fully" is a card saying two things and
    getting one, and the one it gets is not the one printed on it. The page
    keeps the greyed-out value so that unticking the box gives it back — the
    card is where it must not appear.

    Which answer settles which is the engine's own statement, read off the
    parameter. Nothing here knows an effect by name.
    """
    if shape is None:
        return written

    return {
        name: value
        for name, value in written.items()
        if not _settled(shape.params.get(name), shape, written)
        and not _ours(shape.params.get(name))
    }


def _ours(parameter: Any) -> bool:
    """
    Whether this is a name we write rather than an answer somebody gives.

    Every target is bound under a name so that later steps can point at it,
    and `_pick_out` chooses it. A value arriving here for one of those is a
    value about to be overwritten, so it never gets as far as the card.
    """
    return parameter is not None and parameter.written_as == BY_BINDING


def _settled(parameter: Any, shape: Any, written: Mapping[str, Any]) -> bool:
    """
    Whether another parameter currently makes this one moot.

    A switch settles it when it is on. Anything else settles it when it holds
    one of the values the engine named, or — where it named none — any value
    at all. What counts as "holds" includes the effect's own default, because
    a question nobody answered still has an answer: `move_cards` puts cards on
    the bottom unless told otherwise, and a depth from the top means nothing
    there.
    """
    if parameter is None or not parameter.unless:
        return False

    other = shape.params.get(parameter.unless)

    if other is None:
        return False

    now = written.get(other.name, other.default)

    if other.kind == "true or false":
        return now is True

    if parameter.unless_when:
        return now in parameter.unless_when

    return now not in (None, "", False)


MADE_UP = "chosen_"
"""
How a name this invents begins, when the card gave none.

A target has to be named to be pointed at, so one is made up for a choice
written where it is used. Such a name is this program's handwriting and not
anything the card said — which is exactly what reading a card back has to be
able to tell, or it would hand a card its own invented names as if the author
had chosen them, and the card would grow a new one every time it was opened.
"""


def _the_card_s_own(called: str) -> str:
    """
    A name if the card gave one, and nothing if this made it up.
    """
    return "" if called.startswith(MADE_UP) else called


def _pick_out(
    target: str,
    fields: Any,
    aimed: list[dict[str, Any]],
    called: str = "",
) -> str:
    """
    Have the ability choose something, and give it a name to be pointed at.

    The same thing chosen twice is chosen once: two effects that both act on
    "a player somebody picks" mean the same player, which is what a card
    saying "deal 1 damage to a player and steal a cent from them" means.

    A card that already called its choice something keeps that name. Two
    choices alike in everything but their names are still two choices — a card
    naming them apart said they were apart — so the name is part of what makes
    one the same as another, and not a label put on afterwards.
    """
    written = _written_fields(fields)
    # A name the card gave *is* which choice this is: it comes from the list
    # an ability binds, where one name means one choice. Without a name there
    # is nothing to go on but the choice itself, and two steps choosing alike
    # mean one — which is what a card saying "damage a player and steal from
    # them" means.
    already = [
        one
        for one in aimed
        if target in one
        and (
            str(one[target].get("as", "")) == called
            if called
            else _without_name(one[target]) == written
        )
    ]

    if already:
        return str(already[0][target]["as"])

    name = called or f"{MADE_UP}{len(aimed) + 1}"
    aimed.append({target: dict(written, **{"as": name})})

    return name


def _without_name(body: Any) -> dict[str, Any]:
    return {k: v for k, v in dict(body).items() if k != "as"}


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
        if value is None or value == "" or value == []:
            continue

        kept[str(name)] = value

    return kept


# ----------------------------------------------------------------------
# Reading a card back
# ----------------------------------------------------------------------
#
# The other direction. `build_card` writes what somebody filled in; this reads
# a card that already exists back into the same thing, so that opening one and
# making one arrive at the same place.
#
# It parses nothing of its own. A card file may spell a step, a condition or a
# target several ways, and the engine already has one function per kind that
# turns every spelling into one — the same ones the runtime reads cards with.
# Using them is the only way to be sure this and the runtime agree about what a
# card says, which is the whole difficulty: a reader that is merely mostly
# right turns a working card into a different working card, quietly.
#
# So the rule here is refusal over approximation. Anything this cannot read
# faithfully raises, naming the part, and the card is not opened at all.


_STEP_TARGETS = "targets"
"""
Where a step keeps what it picks out for itself, when it does.

Not a field the engine describes on an effect — it is read by the interpreter
around one — which is why reading a card has to name it here to say anything
useful about it.
"""

_STORE = "store"
"""
Where a step says to keep its result under a name.

Read by the interpreter around an effect rather than by the effect, so it is
not one of the effect's own fields and has to be recognised here.
"""

_NOT_AN_ANSWER = object()
"""
What comes back for a field that is the builder's writing, not anybody's answer.

Distinct from ``None`` and from an empty list, both of which a card may mean.
"""


class UnreadableCard(AuthorError):
    """
    A card this cannot open, and the part of it that stopped it.

    Deliberately not a warning. A card half-read is a card about to be saved
    with the unread half missing.
    """


def read_card(card: Any, *, set_id: str = "") -> dict[str, Any]:
    """
    A card that already exists, as the thing an author edits.

    What comes back goes straight to ``build_card`` and comes out the same
    card. Bindings are renamed and short spellings written long — the card is
    the same, the file is not — so reading is canonicalising, and reading a
    card that has already been read changes nothing.
    """
    if not isinstance(card, Mapping):
        raise UnreadableCard("That is not a card.")

    # Asked for once. Building it is milliseconds and a card has many nodes,
    # so a reader that asked per node spent all its time on the same answer.
    said = engine_vocabulary()
    shape = said.node_shape(CARD)

    if shape is None:
        raise UnreadableCard("The engine does not describe a card.")

    return {
        "set": set_id or str(card.get("expansion", "")),
        "card": {
            "id": CARD,
            "fields": _read_fields(said, shape, card, CARD),
            "groups": {},
        },
    }


def _read_fields(
    said: Any,
    shape: Any,
    node: Mapping[str, Any],
    what: str,
    bound: Mapping[str, tuple[str, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """
    Everything one node holds, read by what its shape says each field is.

    Nothing here knows a card has abilities or an ability has effects. A field
    that is a list of some kind is read as a list of that kind, which is how a
    part the language gains is read without this changing.
    """
    fields: dict[str, Any] = {}

    for key, value in node.items():
        name = str(key)

        if name == "schema_version":
            # Written by the builder, not by anybody.
            continue

        parameter = shape.params.get(name)

        if parameter is None:
            raise UnreadableCard(
                f"This {what} says {name!r}, which the engine does not describe."
            )

        if parameter.written_as == BY_BINDING:
            # The engine writes it. Reading it back would be reading our own
            # handwriting and calling it somebody's answer.
            continue

        read = _read_value(said, parameter, value, name, bound)

        if read is not _NOT_AN_ANSWER:
            fields[name] = read

    return fields


def _read_value(
    said: Any,
    parameter: Any,
    value: Any,
    name: str,
    bound: Mapping[str, tuple[str, dict[str, Any]]] | None,
) -> Any:
    """
    One answer, read by what kind of thing the shape says it is.
    """
    kind = parameter.a_list_of

    if not kind:
        if (
            isinstance(value, Mapping)
            and not value
            and parameter.shaped_like in _NESTED_SHAPES
        ):
            # An empty nested node written out is the same as one left out,
            # and the builder leaves it out — `if inside: written[name] = …`.
            # An ability that says `"cost": {}` costs nothing, which is what
            # saying nothing says.
            return _NOT_AN_ANSWER

        return value

    if not isinstance(value, (list, tuple)):
        raise UnreadableCard(f"{name!r} should be a list and is not.")

    if not value and kind in (STEP, CONDITION, MODE) and not parameter.names_the_node:
        # An empty body written out is the same as one left out, and the
        # builder leaves it out — `if body or parameter.names_the_node`. So
        # this leaves it out too, or a card would read one way, be written
        # back, and read the other way. A key that names its node is kept
        # because without it the node has no name.
        #
        # Only a body: a card's own lists of parts are kept as they are,
        # because a card with no abilities says so with an empty list and the
        # builder writes one.
        return _NOT_AN_ANSWER

    if kind == TARGET:
        # Where a part says what it picks out. Not an answer anybody gave: an
        # author aims an action at something, and the list is what the builder
        # makes of that. It is put back inside the steps that point at it, and
        # left out here — a card that had none and a card whose list was
        # rebuilt must read the same way.
        return _NOT_AN_ANSWER

    if kind == CONDITION:
        return [_read_condition(said, one) for one in value]

    if kind in (ABILITY, STATIC):
        return [_read_part(said, one, kind) for one in value]

    if kind == MODE:
        # One option of a card that says "choose one": what it offers, and
        # what it does. It is inside an ability and picks nothing out of its
        # own, so it is read with the names that ability already bound.
        if bound is None:
            raise UnreadableCard(
                f"{name!r} holds options, and nothing here says what they may "
                "be aimed at."
            )

        return [_read_inside(said, one, MODE, bound) for one in value]

    if kind == STEP:
        if bound is None:
            raise UnreadableCard(
                f"{name!r} holds things that happen, and nothing here says "
                "what they may be aimed at."
            )

        return [_read_step(said, one, bound) for one in value]

    raise UnreadableCard(f"{name!r} is a list of {kind}, which cannot be read yet.")


def _read_inside(
    said: Any,
    node: Any,
    kind: str,
    bound: Mapping[str, tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    """
    One node that lives inside a part, read with that part's own bindings.

    A part binds the things its steps point at; anything nested inside it
    points at the same names. So this is `_read_part` without the binding —
    the names are the ones already in hand.
    """
    if not isinstance(node, Mapping):
        raise UnreadableCard(f"A {kind} written as {type(node).__name__}.")

    shape = said.node_shape(kind)

    if shape is None:
        raise UnreadableCard(f"The engine does not describe a {kind}.")

    return {
        "id": kind,
        "fields": _read_fields(said, shape, node, kind, bound),
        "groups": {},
    }


def _read_part(said: Any, node: Any, kind: str) -> dict[str, Any]:
    """
    One ability or one static, with what its steps point at put back into them.

    An ability keeps what it picks out in a list of its own and its steps point
    at those by name. An author does not see that list — they aim an action at
    something — so the names are resolved here and the list is dropped, exactly
    as `build_card` builds it back.
    """
    if not isinstance(node, Mapping):
        raise UnreadableCard(f"An {kind} written as {type(node).__name__}.")

    shape = said.node_shape(kind)

    if shape is None:
        raise UnreadableCard(f"The engine does not describe an {kind}.")

    bound = _bound_by(said, node)

    return {
        "id": kind,
        "fields": _read_fields(said, shape, node, kind, bound),
        "groups": {},
    }


def _bound_by(
    said: Any, node: Mapping[str, Any]
) -> dict[str, tuple[str, dict[str, Any]]]:
    """
    Every name this part binds, and what it bound to it.
    """
    from fsme.runtime.target_resolver import normalise as a_target

    found: dict[str, tuple[str, dict[str, Any]]] = {}

    holder = said.node_shape(ABILITY)

    for key, parameter in (holder.params if holder is not None else {}).items():
        if parameter.a_list_of != TARGET:
            continue

        for spec in node.get(key, ()) or ():
            name, params = a_target(_plainly(spec))
            under = str(params.get("as", name))
            found[under] = (
                name,
                {k: v for k, v in params.items() if k != "as"},
            )

    return found


def _read_step(
    said: Any, node: Any, bound: Mapping[str, tuple[str, dict[str, Any]]]
) -> Any:
    """
    One thing that happens, with what it is aimed at put back inside it.
    """
    from fsme.runtime.interpreter import CONTROL_NAMES
    from fsme.runtime.interpreter import normalise as a_step

    name, params, aimed = a_step(_plainly(node))

    if name in CONTROL_NAMES:
        return _read_control(said, name, params, aimed, bound)

    shape = said.shape(name)

    if shape is None:
        raise UnreadableCard(f"This card uses {name!r}, which the engine has not.")

    written = dict(params)
    short = written.pop(SHORTHAND, None)

    if short is not None:
        if not shape.primary:
            raise UnreadableCard(
                f"{name!r} is written the short way and names no parameter "
                "the short way fills."
            )

        written[shape.primary] = short

    fields: dict[str, Any] = {}
    groups: dict[str, Any] = {}

    for key, value in written.items():
        parameter = shape.params.get(str(key))

        if parameter is None:
            if str(key) == _STORE:
                raise UnreadableCard(
                    f"{name!r} keeps its result under a name for a later step "
                    "to read. Cards that do that are edited in full."
                )

            if str(key) == _STEP_TARGETS:
                raise UnreadableCard(
                    f"{name!r} picks something out for itself. Folding that up "
                    "to the ability would let a later step reuse the choice, "
                    "and two separate choices of the same thing become one — "
                    "so this card is edited in full."
                )

            raise UnreadableCard(
                f"{name!r} says {key!r}, which the engine does not describe."
            )

        pointed = _points_at(parameter, value)

        if pointed is None:
            # Not a name this understands. It may still be a value the ability
            # works out from one, which is a name it would drop.
            _refuse_a_working(said, name, str(key), parameter, value, bound)

            # An effect may hold more of the language — `watch_for` keeps the
            # steps it will run and what must be true when it does — and the
            # answer saying so is the same `a_list_of` a part and a control
            # node are read by. Kept as the card's own words instead, it went
            # into author state as something nothing could show and the writer
            # would throw away, which is a card quietly emptied rather than a
            # card refused.
            read = (
                _read_value(said, parameter, value, str(key), bound)
                if parameter.a_list_of
                else value
            )

            if read is not _NOT_AN_ANSWER:
                fields[str(key)] = read

            continue

        if pointed not in bound:
            raise UnreadableCard(
                f"{name!r} names {pointed!r}, which nothing on this card binds."
            )

        groups[str(key)] = _as_chosen(said, bound[pointed], bound, called=pointed)

    step: dict[str, Any] = {"id": name, "fields": fields, "groups": groups}

    if aimed is None:
        return step

    if isinstance(aimed, Mapping):
        # A target written where it is used rather than bound in a list of its
        # own. That is exactly what an aim is — but it may still have been
        # given a name, and the card is entitled to get it back.
        from fsme.runtime.target_resolver import normalise as a_target

        kind, params = a_target(_plainly(aimed))
        chosen = _as_chosen(
            said, (kind, {k: v for k, v in params.items() if k != "as"}), bound
        )
        step |= {
            "aim": chosen["id"],
            "aim_fields": chosen["fields"],
            "aim_groups": chosen["groups"],
        }

        # Whatever this was called where it was written is not kept. The
        # builder gathers every choice into one list for the ability, where a
        # name has to mean one thing — and a card may call two choices in two
        # different branches by the same word, because only one of them ever
        # happens. Keeping such a name would merge them, and the card would
        # come back drawing from the wrong deck.
        return step

    if not isinstance(aimed, str):
        raise UnreadableCard(f"{name!r} is aimed at something written in full.")

    if aimed in bound:
        chosen = _as_chosen(said, bound[aimed], bound, frozenset({aimed}), aimed)
        step |= {
            "aim": chosen["id"],
            "aim_fields": chosen["fields"],
            "aim_groups": chosen["groups"],
        }

        # What the card called what it aimed at, kept beside the aim for the
        # same reason it is kept beside anything else chosen: the card may say
        # it again, and it is what the card said.
        return _also_called(step, aimed)

    if said.target_shape(aimed) is not None:
        step |= {"aim": aimed, "aim_fields": {}, "aim_groups": {}}

        return step

    raise UnreadableCard(
        f"{name!r} is aimed at {aimed!r}, which nothing on this card binds."
    )


def _read_control(
    said: Any,
    name: str,
    params: Mapping[str, Any],
    aimed: Any,
    bound: Mapping[str, tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    """
    A step that holds other steps, read as a node like any other.

    `if` and its two branches, `may` and what happens when they say yes,
    `choose` and its options, `for_each` and what it does for each one. None
    of them is a special case in the card model: each is a node whose shape
    says which of its fields hold steps, which hold conditions and which hold
    options, and reading those is the same descent that reads a card's parts.

    What it may be written with, and which of its keys hold what, are the
    engine's own answers — the shape is built from the same declarations the
    interpreter expands the node by, so a structure the engine gains is one
    this reads without being told.
    """
    shape = said.node_shape(name)

    if shape is None:
        raise UnreadableCard(f"The engine does not describe {name!r}.")

    written = {
        key: value
        for key, value in params.items()
        # The head names the node and is read back from the shape; a target
        # written on it is the aim, and is put back below.
        if key != "target"
    }

    for key, parameter in shape.params.items():
        other = parameter.instead_of

        if other and key in written and other in written:
            raise UnreadableCard(
                f"{name!r} says both {other!r} and {key!r}, which are two "
                "spellings of one question. The engine reads one of them and "
                "drops the other, so this card is edited in full."
            )

    fields: dict[str, Any] = {}

    for key, value in written.items():
        parameter = shape.params.get(str(key))

        if parameter is None:
            raise UnreadableCard(
                f"{name!r} says {key!r}, which the engine does not describe."
            )

        if not parameter.a_list_of and _names_one_of(value, bound):
            # A value that points at something the ability chose. The builder
            # binds what a card picks out under names of its own making, so a
            # name written here would be written back pointing at nothing.
            raise UnreadableCard(
                f"{name!r} points at something the ability chose. Folding that "
                "up would leave it pointing at nothing, so this card is edited "
                "in full."
            )

        read = (
            _read_value(said, parameter, value, str(key), bound)
            if parameter.a_list_of
            else value
        )

        if read is not _NOT_AN_ANSWER:
            fields[str(key)] = read

    step: dict[str, Any] = {"id": name, "fields": fields, "groups": {}}

    if aimed is None:
        return step

    raise UnreadableCard(
        f"{name!r} is aimed at something of its own. Folding that up to the "
        "ability would change which steps it reaches, so this card is edited "
        "in full."
    )


def _names_one_of(
    value: Any, bound: Mapping[str, tuple[str, dict[str, Any]]]
) -> bool:
    """
    Whether anything written in this value is a name the part bound.
    """
    if isinstance(value, str):
        return value in bound

    if isinstance(value, Mapping):
        return any(_names_one_of(one, bound) for one in value.values())

    if isinstance(value, (list, tuple)):
        return any(_names_one_of(one, bound) for one in value)

    return False


def _also_called(step: dict[str, Any], called: str) -> dict[str, Any]:
    """
    A step, with the name it aimed by if the card gave one.

    Left out entirely when there is none, rather than said as nothing: a key
    holding an empty answer and a key that is not there read differently, and
    a card would come back one way and then the other.
    """
    mine = _the_card_s_own(called)

    return step | {"aim_name": mine} if mine else step


def _refuse_a_working(
    said: Any,
    effect: str,
    key: str,
    parameter: Any,
    value: Any,
    bound: Mapping[str, tuple[str, dict[str, Any]]],
) -> None:
    """
    Refuse a value the ability works out from something it chose.

    ``{"count": "loot", "of": "rival"}`` is "as many as that player holds", and
    the name in it is one the ability bound. Reading the answer without the
    binding would leave a card counting nobody's hand, so the whole card goes
    to the editor rather than half of it here.

    What is refused is a value that names something *this ability chose* —
    which is a question about the name, not about the key holding it. ``of``
    names something whether that something was chosen here or was standing
    there all along, and "as much loot as the controller holds" needs nothing
    kept: the controller is the controller in any card that mentions them.
    """
    if not isinstance(value, Mapping):
        return

    working = said.node_shape(WORKED_OUT)

    if working is None or not any(
        way.shaped_like == WORKED_OUT for way in parameter.also
    ):
        return

    named = [
        head
        for head in value
        if getattr(working.params.get(str(head)), "refers_to", "")
        and str(value[head]) in bound
    ]

    if named:
        raise UnreadableCard(
            f"{effect!r} works {key!r} out from something the ability chose "
            f"({', '.join(sorted(named))}). Cards that do that are edited "
            "in full."
        )


def _points_at(parameter: Any, value: Any) -> str | None:
    """
    The name this answer names, if it names one rather than carrying a value.

    Both spellings the engine reads: the bare name a target is bound under,
    and the one dynamic head that answers with a seat. Which of them a
    parameter uses is the parameter's own statement, so nothing here knows an
    effect by name.
    """
    if not parameter.refers_to or parameter.refers_to == VALUES:
        return None

    if parameter.written_as == BY_PLAYER_OF:
        if isinstance(value, Mapping) and set(value) == {BY_PLAYER_OF}:
            return str(value[BY_PLAYER_OF])

        return None

    return str(value) if isinstance(value, str) else None


def _as_chosen(
    said: Any,
    chosen: tuple[str, dict[str, Any]],
    bound: Mapping[str, tuple[str, dict[str, Any]]],
    seen: frozenset[str] = frozenset(),
    called: str = "",
) -> dict[str, Any]:
    """
    One thing an ability picked out, as the answer that picked it.

    A target may itself name another one — "the items owned by the player you
    chose" — and that name means nothing once the list it was bound in has been
    put away. So a parameter naming a binding is followed, and what it named
    becomes an answer inside this one, which is where the builder puts it back.

    What the card *called* it is kept beside it. It is not an answer anybody
    gave and it is not part of what was chosen — two cards choosing the same
    player under different names choose the same player — but it is what the
    card said, and a card that says it again later needs it to still be there.
    """
    kind, body = chosen
    shape = said.target_shape(kind)
    fields: dict[str, Any] = {}
    groups: dict[str, Any] = {}

    for key, value in body.items():
        parameter = None if shape is None else shape.params.get(str(key))

        if (
            parameter is not None
            and parameter.refers_to
            and parameter.refers_to != VALUES
            and isinstance(value, (list, tuple))
            and any(str(one) in bound for one in value)
        ):
            raise UnreadableCard(
                f"{kind!r} is built out of several things the ability chose "
                f"({', '.join(str(one) for one in value)}), and an answer "
                "holds one. This card is edited in full."
            )

        pointed = None if parameter is None else _points_at(parameter, value)

        if pointed is None or pointed not in bound or pointed in seen:
            fields[str(key)] = value

            continue

        groups[str(key)] = _as_chosen(
            said, bound[pointed], bound, seen | {pointed}, pointed
        )

    picked: dict[str, Any] = {"id": kind, "fields": fields, "groups": groups}

    mine = _the_card_s_own(called)

    return picked | {"name": mine} if mine else picked


def _read_condition(said: Any, node: Any) -> dict[str, Any]:
    """
    One condition, and any conditions inside it.

    ``not``, ``and`` and ``or`` hold a list of conditions, which they say by
    describing that field as a list of conditions. Reading it as a value would
    wrap it one layer deeper every time the card was opened.
    """
    from fsme.runtime.condition_evaluator import normalise as a_condition

    name, params = a_condition(_plainly(node))
    shape = said.condition_shape(name)

    if shape is None:
        raise UnreadableCard(f"This card asks {name!r}, which the engine has not.")

    fields: dict[str, Any] = {}

    for key, value in params.items():
        parameter = shape.params.get(str(key))

        if parameter is None:
            raise UnreadableCard(
                f"{name!r} says {key!r}, which the engine does not describe."
            )

        fields[str(key)] = (
            [_read_condition(said, one) for one in value]
            if parameter.a_list_of == CONDITION
            else value
        )

    return {"id": name, "fields": fields, "groups": {}}


def _plainly(node: Any) -> Any:
    """
    A node as ordinary data, whatever it was frozen into.
    """
    if isinstance(node, Mapping):
        return {str(k): _plainly(v) for k, v in node.items()}

    if isinstance(node, (list, tuple)):
        return [_plainly(one) for one in node]

    return node
