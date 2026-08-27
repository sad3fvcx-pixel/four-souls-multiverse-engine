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
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fsme.cards import validate_card
from fsme.content.vocabulary import (
    BY_BINDING,
    BY_PLAYER_OF,
    CARD,
    CONDITION,
    COST,
    MODE,
    NAMED_COUNT,
    TARGET,
    WORKED_OUT,
)
from fsme.content.workspace import (
    card_identifier,
    identifier_for,
    sets_directory,
)
from fsme.runtime.vocabulary import engine_vocabulary

CARDS = "cards"
MANIFEST = "manifest.json"
SCHEMA = "1"

__all__ = [
    "AuthorError",
    "build_card",
    "check_card",
    "delete_card",
    "delete_set",
    "make_set",
    "save_card",
    "said_by_the_engine",
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
        "id": card_identifier(set_id, kind, name),
        "name": name,
        "type": kind,
        "expansion": set_id,
        "schema_version": SCHEMA,
    }
    card.update({key: value for key, value in written.items() if key not in card})
    card.setdefault("abilities", [])

    return card


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
        if parameter.instead_of or parameter.written_as == BY_BINDING:
            # A second spelling of a question asked elsewhere, or a name this
            # writes for itself further down.
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
        body = _given(vocabulary.condition_shape(name), described, aimed)

        return {name: body} if body else name

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
        name = _pick_out(target, inside, aimed)

        written[str(key)] = (
            {BY_PLAYER_OF: name}
            if parameter.written_as == BY_PLAYER_OF
            else name
        )

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


def _pick_out(
    target: str,
    fields: Any,
    aimed: list[dict[str, Any]],
) -> str:
    """
    Have the ability choose something, and give it a name to be pointed at.

    The same thing chosen twice is chosen once: two effects that both act on
    "a player somebody picks" mean the same player, which is what a card
    saying "deal 1 damage to a player and steal a cent from them" means.
    """
    written = _written_fields(fields)
    already = [
        one
        for one in aimed
        if target in one and _without_name(one[target]) == written
    ]

    if already:
        return str(already[0][target]["as"])

    name = f"chosen_{len(aimed) + 1}"
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
