# src/fsme/lab/desk/capabilities.py

"""
What FSME can do, in a form a page can render.

An author should not have to find out what the engine supports by guessing, by
reading source, or by searching documentation. So the engine is asked, and what
comes back is the whole vocabulary with the words already on it: every effect
with what it does and what it takes, every condition, every target, every
moment a card can react to.

Nothing here decides anything. Every name, every parameter, every domain and
every sentence comes from the registries — the same ones validation checks
against — so a page built from this cannot offer a card the loader would
refuse, and cannot fall out of step with the engine without the engine
changing first. There is no second list.
"""

from __future__ import annotations

from typing import Any

from fsme.content.vocabulary import (
    A_LIST,
    BY_BINDING,
    BY_ENGINE,
    BY_NAME,
    BY_PLAYER_OF,
    STRUCTURE,
)
from fsme.events.types import WHEN_IT_HAPPENS, EventType
from fsme.runtime.interpreter import CONTROL_NAMES
from fsme.runtime.vocabulary import engine_vocabulary

COMMON_EFFECTS = (
    "gain_coins",
    "draw_loot",
    "deal_damage",
    "heal",
    "roll_dice",
    "lose_coins",
    "add_modifier",
    "discard_loot",
    "gain_treasure",
    "destroy_treasure",
)
"""
The effects to show first.

Measured across the 352 cards that have rules: a short list covers most of
what real cards do, and a list of sixty-three sorted alphabetically is a wall.
Everything else is still there, one click further on.
"""

COMMON_TRIGGERS = (
    "on_play",
    "on_activate",
    "turn_start",
    "turn_end",
    "monster_killed",
    "player_died",
    "damage_dealt",
    "after_roll",
)
"""
The moments real cards react to most, for the same reason.
"""

COMMON_TARGETS = (
    "target_player",
    "another_player",
    "all_players",
    "controller",
    "target_treasure",
    "target_monster",
    "current_monster",
    "target_loot",
    "random_player",
    "self",
)
"""
The things a card most often acts on, shown before the rest.

An ordering over the registry's own list, like the two above — not a list of
what exists. Everything the engine has is still offered; this decides what a
person sees without opening "everything else".
"""

NEEDS_SOMETHING_EARLIER = "passthrough"
"""
Targets that hand back whatever they were given.

`group`, `most_common`, `previous_target` and the rest mean nothing on their
own — they refer to something the ability already chose. That does not make
them un-aimable: "deal 1 damage, then destroy what you damaged" points an
effect straight at `previous_target`, and the engine resolves it like any
other. It makes them *second*, so they are offered apart and said to need
something before them. Read off `yields` rather than listed.
"""

CARD_KINDS = (
    ("loot", "Loot card", "Played from your hand, then discarded."),
    ("treasure", "Treasure", "An item you keep in play."),
    ("monster", "Monster", "Something to fight."),
    ("character", "Character", "Somebody to play as."),
    ("room", "Room", "A place that changes the table."),
    ("curse", "Curse", "Something unpleasant that sticks to a player."),
)
"""
The kinds of card an author can make, in the order they are most often made.
"""


def catalogue() -> dict[str, Any]:
    """
    Everything a page needs in order to offer the engine's whole vocabulary.
    """
    vocabulary = engine_vocabulary()

    return {
        "kinds": [
            {"id": kind, "name": name, "about": about}
            for kind, name, about in CARD_KINDS
        ],
        "triggers": _triggers(vocabulary),
        "effects": _effects(vocabulary),
        "conditions": _conditions(vocabulary),
        "targets": _targets(vocabulary),
        "abilities": _nodes(vocabulary, ABILITY_NODES),
        "statics": _nodes(vocabulary, STATIC_NODES),
        "structures": _nodes(vocabulary, STRUCTURE_NODES),
    }


ABILITY_NODES = ("ability", "cost")
"""
What describes a card's ability: the ability itself, and the shape of what it
charges. ``mode`` is not here — it belongs to ``choose``, which is a structure.
"""

STRUCTURE_NODES = (*sorted(CONTROL_NAMES), "mode", "worked_out", "named_count")
"""
The nodes that shape what happens, and the one small shape they refer to.

``mode``, ``worked_out`` and ``named_count`` are published beside them rather
than on their own because none of them is a thing a card writes by itself: one
is what a ``choose`` is a list of, and the other two are the second way of
writing a value somewhere else. A name in ``a_list_of`` or ``shaped_like``
that nothing describes would be a promise this layer cannot keep.
"""

STATIC_NODES = ("static",)
"""
What describes a value a card changes while it is in play.

Separate from an ability on purpose. A static has no trigger, no effects and
nothing that resolves; sharing a section would suggest a kinship that does not
exist, and the two words a card writes on both — ``scope`` and ``conditions``
— do not even mean quite the same thing.
"""


def _nodes(vocabulary: Any, names: Any) -> list[dict[str, Any]]:
    """
    The shapes that describe the parts of the language that are not effects.

    An ability, a static, a control node, and the two small shapes those refer
    to. They are published on exactly the terms an effect is: a list of fields
    with everything the engine says about each. Whatever draws one draws them
    all, which is the whole reason for putting them here rather than inventing
    somewhere else to put them.

    ``bodies`` says where a node keeps the things it does, so that anything
    reading this can tell a node with nothing in it from one that works.
    """
    found = []

    for name in names:
        shape = vocabulary.node_shape(name)

        if shape is None:
            continue

        found.append(
            {
                "id": name,
                "about": ABOUT_NODES.get(name, name.replace("_", " ")),
                "bodies": list(shape.bodies),
                "fields": _fields(shape),
            }
        )

    return found


ABOUT_NODES = {
    "ability": "a rule the card follows",
    "static": "a number this card changes while it is in play",
    "cost": "what a player pays to use an ability",
    "mode": "one option of a choice",
    "worked_out": "a value the ability works out while it runs",
    "named_count": "a price paid in counters of a named kind",
    "if": "depending on something",
    "may": "the controller may choose to",
    "choose": "one of several options",
    "for_each": "once for each of them",
    "repeat": "several times over",
    "sequence": "these, in order",
    "stop": "nothing further happens",
}
"""
What each part of the language is, in the words a person would use for it.

The parameters inside them describe themselves; this is the sentence for the
node, which is the one thing a shape read off a dataclass cannot carry.
"""


def _triggers(vocabulary: Any) -> list[dict[str, Any]]:
    """
    Every moment a card can react to, and what reacting to it means by default.

    ``scope`` is what an ability listening for this trigger listens to when it
    does not say — the engine's own answer, not a rule invented here. It is
    published because leaving it out is not leaving the question open: for all
    but fourteen triggers the unwritten answer is the whole table, and a card
    meaning "when *you* take damage" gets "when anybody does" in silence.
    """
    return [
        {
            "id": str(event),
            "about": WHEN_IT_HAPPENS.get(event, str(event).replace("_", " ")),
            "common": str(event) in COMMON_TRIGGERS,
            "scope": vocabulary.trigger_scopes.get(str(event), ""),
        }
        for event in EventType
    ]


def _effects(vocabulary: Any) -> list[dict[str, Any]]:
    found = []

    for name in sorted(vocabulary.effects):
        shape = vocabulary.shape(name)

        if shape is None:
            # A control node — `if`, `may`, `choose`. They are offered as their
            # own shapes on the page rather than as effects, because a person
            # does not think of "if" as a thing that happens.
            continue

        found.append(
            {
                "id": name,
                "about": _sentence(name, shape),
                "needs_target": bool(getattr(shape, "primary", None) is not None)
                or _wants_target(shape),
                "common": name in COMMON_EFFECTS,
                "fields": _fields(shape),
            }
        )

    return found


def _conditions(vocabulary: Any) -> list[dict[str, Any]]:
    return [
        {
            "id": name,
            "about": shape.describes or name.replace("_", " "),
            "fields": _fields(shape),
        }
        for name in sorted(vocabulary.conditions)
        if (shape := vocabulary.condition_shape(name)) is not None
    ]


def _targets(vocabulary: Any) -> list[dict[str, Any]]:
    return [
        {
            "id": name,
            "about": shape.describes or name.replace("_", " "),
            "gives": shape.yields,
            "common": name in COMMON_TARGETS,
            "aimable": True,
            "after": shape.yields == NEEDS_SOMETHING_EARLIER,
            "fields": _fields(shape),
        }
        for name in sorted(vocabulary.targets)
        if (shape := vocabulary.target_shape(name)) is not None
    ]


def _fields(shape: Any) -> list[dict[str, Any]]:
    """
    One entry per thing a person may be asked, and how to ask it.

    Every parameter appears with everything the engine says about it, and
    nothing is dropped for being hard to render: a parameter the engine
    understands and the interface omits is a capability quietly taken away.

    ``shown`` is the one thing decided here rather than read, and it is decided
    from the metadata alone — never from which effect the parameter belongs to.
    Four answers, because there are four different questions:

    - ``form`` — a value somebody gives. ``role`` says which control.
    - ``group`` — the name of something the ability picks out. Not a box: the
      page offers the engine's own targets and writes the name behind it.
    - ``advanced`` — the effect's own nested data. Shown as what it is.
    - ``given`` — not a question. Either no card can answer it or whatever is
      writing the card answers it, and a box would take an answer that is
      about to be overwritten.
    - ``spelling`` — the same question as another parameter, under a second
      name the engine also reads. Asked once, under the first.
    - ``body`` — more of the language, listed. ``a_list_of`` says of what, and
      whatever draws one list of effects draws every one of them.
    - ``nested`` — more of the language, once. ``shaped_like`` says which.

    ``also`` carries the other ways the same parameter may be written, on the
    same terms, because a parameter that takes a number *or* a way of working
    one out is not two parameters and must not be drawn as one question with
    half its answers refused.
    """
    found = []

    for name, parameter in sorted(shape.params.items()):
        entry: dict[str, Any] = {
            "id": name,
            "about": parameter.describes or name.replace("_", " "),
            "role": parameter.role,
            "kind": parameter.kind,
            "choices": [str(value) for value in parameter.values],
            "least": parameter.least,
            "otherwise": parameter.default,
            "required": parameter.required,
            "unless": parameter.unless,
            "unless_when": [str(value) for value in parameter.unless_when],
            "written": parameter.written_as,
            "instead_of": parameter.instead_of,
            "picks": parameter.refers_to,
            "a_list_of": parameter.a_list_of,
            "shaped_like": parameter.shaped_like,
            "defines": parameter.defines,
            "domain_from": parameter.domain_from,
            "names_the_node": parameter.names_the_node,
            "also": [
                {
                    "kind": way.kind,
                    "choices": [str(v) for v in way.values],
                    "least": way.least,
                    "shaped_like": way.shaped_like,
                    "a_list_of": way.a_list_of,
                    "about": way.describes,
                }
                for way in parameter.also
            ],
            # Several answers out of a known set — which is a control the
            # page has. A list with nothing to choose from is the effect's own
            # data and goes to the advanced view instead.
            "many": parameter.kind == A_LIST and bool(parameter.values),
        }

        entry["shown"] = (
            "spelling"
            if parameter.instead_of
            else "given"
            if parameter.written_as in (BY_ENGINE, BY_BINDING)
            else "group"
            if parameter.written_as in (BY_NAME, BY_PLAYER_OF)
            else "body"
            if parameter.a_list_of
            else "nested"
            if parameter.shaped_like
            else "advanced"
            if parameter.role == STRUCTURE
            else "form"
        )

        found.append(entry)

    return found


def _wants_target(shape: Any) -> bool:
    """
    Whether this effect acts on something rather than on the game at large.

    Read off the shape: an effect written to work on its targets declares no
    parameters of its own, which is exactly what `open_ended` records.
    """
    return bool(getattr(shape, "open_ended", False))


def _sentence(name: str, shape: Any) -> str:
    """
    What an effect does, in the engine's own words.

    Every effect has carried a description since it was written; this is that
    sentence, and there is nowhere else it could come from.
    """
    from fsme.effects import builtin_registry

    try:
        return builtin_registry().spec(name).description or name.replace("_", " ")
    except Exception:
        return name.replace("_", " ")
