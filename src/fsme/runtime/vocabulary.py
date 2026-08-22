# src/fsme/runtime/vocabulary.py

"""
What this engine actually implements.

The content pipeline validates card meaning against a list of names. That list
has to come from the engine rather than from a document, or the two drift and
content passes validation for effects nobody wrote.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import Field, fields
from types import MappingProxyType
from typing import Any

from fsme.cards.definition import Ability, Static
from fsme.content import Vocabulary
from fsme.content.vocabulary import (
    A_LIST,
    A_MAPPING,
    BY_BINDING,
    BY_ENGINE,
    BY_PLAYER_OF,
    CARDS,
    CONDITION,
    COST,
    EFFECT,
    MODE,
    OPEN,
    PLAYERS,
    STRUCTURE,
    TARGET,
    UNCHECKED,
    EffectShape,
    NodeShape,
    ParamShape,
)
from fsme.effects import EffectRegistry, builtin_registry
from fsme.effects.registry import EffectSpec, ParamKind
from fsme.events import EventType
from fsme.rules.costs import COINS, COUNTERS, DISCARD, HP, TAP
from fsme.rules.restrictions import ACTIONS
from fsme.rules.statics import STATIC_SCOPES

from .condition_evaluator import ConditionEvaluator
from .interpreter import (
    _MODIFIER_KEYS,
    CONTROL_BODIES,
    CONTROL_KEYS,
    CONTROL_NAMES,
)
from .runtime import ABILITY_SCOPES, ABILITY_ZONES, ability_scope
from .target_resolver import TargetResolver

BOOLEAN_CONDITIONS = frozenset({"and", "or", "not"})


def engine_vocabulary(effects: EffectRegistry | None = None) -> Vocabulary:
    """
    Read the vocabulary out of the live engine.

    This is the one function that knows both sides. What goes in is a registry
    full of callables; what comes out is names and plain descriptions, and the
    pipeline that receives it never learns there was an engine to ask.
    """
    registry = effects if effects is not None else builtin_registry()
    conditions = ConditionEvaluator()
    targets = TargetResolver()

    return Vocabulary(
        effects=frozenset(registry.names()) | CONTROL_NAMES,
        triggers=frozenset(str(event_type) for event_type in EventType),
        conditions=frozenset(conditions.names()) | BOOLEAN_CONDITIONS,
        targets=frozenset(targets.names()),
        shapes=MappingProxyType(
            {name: _shape_of(registry.spec(name)) for name in registry.names()}
        ),
        condition_shapes=conditions.shapes(),
        target_shapes=targets.shapes(),
        node_shapes=_node_shapes(),
        trigger_scopes=_trigger_scopes(),
    )


def _trigger_scopes() -> Mapping[str, str]:
    """
    What each trigger means by silence, asked of the engine rather than copied.

    ``ability_scope`` is the branch that decides it, so an ability carrying
    nothing but the trigger is handed to it and the answer written down. A list
    written out here instead would be free to drift from the branch, which is
    exactly how the wrong scope came to be invisible in the first place.
    """
    return MappingProxyType(
        {
            str(event_type): ability_scope(Ability(trigger=str(event_type)))
            for event_type in EventType
        }
    )


TEXT = "text"
WHOLE = "a whole number"
FLAG = "true or false"


def _node_shapes() -> Mapping[str, NodeShape]:
    """
    What an ability, a static and each control node may be written with.

    The two card structures are read off their own dataclasses: ``from_data``
    reads exactly the fields, so the fields are what a card may write, and
    adding one to the language widens this the moment it exists. The control
    nodes are read off the table beside the expanders that consume them.

    What each field *is* comes from the same two places. The kind comes off the
    annotation, exactly as an effect's parameters come off its handler's
    signature — a derivation, not a table, so it cannot fall out of step with
    the dataclass. Everything an annotation cannot say is declared beside the
    code that enforces it: the scopes beside the branch that reads them, the
    zones beside the lookup that fails on a wrong one, the costs beside the
    check that refuses an unknown key, the prohibitions beside the comparison
    that silently never matches.

    These used to be typed ``text`` across the board. That was not thin, it was
    wrong: ``optional`` is a flag, ``cost`` is a small node of its own, and
    ``effects`` is a list of the same effect nodes an ability holds at the top.
    Anything drawing a form from this would have drawn four boxes.
    """
    return MappingProxyType(
        {
            "ability": NodeShape(
                name="ability",
                params=MappingProxyType(
                    {field.name: _ability_field(field) for field in fields(Ability)}
                ),
            ),
            "static": NodeShape(
                name="static",
                params=MappingProxyType(
                    {field.name: _static_field(field) for field in fields(Static)}
                ),
            ),
            "cost": _COST,
            "mode": _MODE,
            **{
                name: NodeShape(
                    name=name,
                    params=MappingProxyType(
                        {
                            key: _control_field(name, key)
                            for key in tuple(keys) + tuple(sorted(_MODIFIER_KEYS))
                        }
                    ),
                    bodies=CONTROL_BODIES.get(name, ()),
                )
                for name, keys in CONTROL_KEYS.items()
            },
        }
    )


_ANNOTATIONS = {
    "int": WHOLE,
    "str": TEXT,
    "bool": FLAG,
    "tuple[Any, ...]": A_LIST,
    "Mapping[str, Any]": A_MAPPING,
    "str | None": TEXT,
}
"""
What a dataclass field holds, read off how it was written down.

The same trick `parameters_of` plays on an effect handler, for the same reason:
a signature cannot drift from the function it belongs to, and a field's
annotation cannot drift from the field.
"""


def _kind_of(field: Field[Any]) -> str:
    """
    The kind a dataclass field's annotation names.
    """
    return _ANNOTATIONS.get(str(field.type), UNCHECKED)


ABILITY_WORDS = {
    "trigger": "when it happens",
    "conditions": "what must be true for it to happen at all",
    "targets": "what it picks out before anything runs",
    "effects": "what happens",
    "optional": "the controller may decline it",
    "cost": "what the player pays to use it",
    "replacement": "it changes the event instead of reacting to it",
    "scope": "whose events it listens to",
    "zone": "where the card must be standing, if not in play",
    "description": "what it says, in a person's words",
}

STATIC_WORDS = {
    "stat": "which number it changes",
    "amount": "by how much",
    "forbids": "an action it does not allow instead",
    "per_counter": "a counter it is worth its amount for each of",
    "scope": "who it applies to",
    "conditions": "when it applies, beyond its card being in play",
    "description": "what it says, in a person's words",
}


def _ability_field(field: Field[Any]) -> ParamShape:
    """
    One field of an ability, as a card may write it.
    """
    lists = {"conditions": CONDITION, "targets": TARGET, "effects": EFFECT}
    values = {
        "trigger": tuple(str(event_type) for event_type in EventType),
        "scope": ABILITY_SCOPES,
        "zone": ABILITY_ZONES,
    }

    return ParamShape(
        field.name,
        _kind_of(field),
        values=values.get(field.name, ()),
        a_list_of=lists.get(field.name, ""),
        shaped_like=COST if field.name == "cost" else "",
        describes=ABILITY_WORDS.get(field.name, ""),
        default=None if field.name == "scope" else _default_of(field),
    )


def _static_field(field: Field[Any]) -> ParamShape:
    """
    One field of a static, as a card may write it.

    ``stat`` carries no domain on purpose. Which stats a static may change
    depends on what its scope reaches and on whether its card is a monster —
    the checker says so in `STATIC_STAT_BY_SCOPE` — and a domain that is right
    half the time is worse than none.
    """
    return ParamShape(
        field.name,
        _kind_of(field),
        values=(
            STATIC_SCOPES
            if field.name == "scope"
            else ACTIONS
            if field.name == "forbids"
            else ()
        ),
        a_list_of=CONDITION if field.name == "conditions" else "",
        describes=STATIC_WORDS.get(field.name, ""),
        default=_default_of(field),
    )


def _default_of(field: Field[Any]) -> Any:
    """
    What a card gets for leaving a field out, where the dataclass says.
    """
    from dataclasses import MISSING

    if field.default is not MISSING:
        return field.default

    return None


_COST = NodeShape(
    name="cost",
    params=MappingProxyType(
        {
            TAP: ParamShape(TAP, FLAG, describes="tap the card", default=False),
            COINS: ParamShape(COINS, WHOLE, least=0, describes="cents", default=0),
            DISCARD: ParamShape(
                DISCARD, WHOLE, least=0, describes="loot cards to discard", default=0
            ),
            COUNTERS: ParamShape(
                COUNTERS,
                UNCHECKED,
                role=OPEN,
                describes="counters to spend, as a number or a named number",
            ),
            HP: ParamShape(
                HP, WHOLE, least=0, describes="hit points, never the last one", default=0
            ),
        }
    ),
)
"""
What an activated ability may charge.

The five keys `unpayable` accepts and refuses anything else. ``counters`` is
the one that is not a plain number: a card with several kinds on it says which
it is spending, so the value is either a count or ``{counter, amount}``.
"""

_MODE = NodeShape(
    name="mode",
    params=MappingProxyType(
        {
            "description": ParamShape(
                "description", TEXT, required=True, describes="what this option offers"
            ),
            "effects": ParamShape(
                "effects", A_LIST, a_list_of=EFFECT, describes="what it does"
            ),
        }
    ),
    bodies=("effects",),
)
"""
One option of a ``choose``.

Described here because nothing else describes it: the description is what the
player is offered, so a client can show the choice without knowing anything
about the effects behind it.
"""


_CONTROL_FIELDS: dict[tuple[str, str], ParamShape] = {}


def _control_field(node: str, key: str) -> ParamShape:
    """
    One key of one control node, as the expander that reads it will take it.

    A body holds more of the language and says which kind; the head of a node
    is usually the body written the short way; and the handful of keys any node
    accepts mean the same thing wherever they appear.
    """
    bodies = {
        ("if", "then"): EFFECT,
        ("if", "else"): EFFECT,
        ("if", "if"): CONDITION,
        ("if", "conditions"): CONDITION,
        ("may", "may"): EFFECT,
        ("may", "effects"): EFFECT,
        ("choose", "choose"): MODE,
        ("choose", "modes"): MODE,
        ("repeat", "effects"): EFFECT,
        ("for_each", "effects"): EFFECT,
        ("sequence", "sequence"): EFFECT,
        ("sequence", "effects"): EFFECT,
    }

    if (node, key) in bodies:
        return ParamShape(
            key,
            A_LIST,
            a_list_of=bodies[(node, key)],
            describes=_CONTROL_WORDS.get((node, key), ""),
        )

    if (node, key) == ("for_each", "for_each") or (node, key) == ("for_each", "of"):
        return ParamShape(
            key, UNCHECKED, shaped_like=TARGET, describes="what to do it for each of"
        )

    if (node, key) in (("repeat", "repeat"), ("repeat", "times")):
        return ParamShape(key, WHOLE, least=0, describes="how many times")

    if (node, key) == ("stop", "stop"):
        return ParamShape(key, FLAG, describes="stop the ability here")

    return _ANY_NODE.get(key, ParamShape(key, TEXT))


_CONTROL_WORDS = {
    ("if", "if"): "what must be true",
    ("if", "conditions"): "what must be true",
    ("if", "then"): "what happens when it is",
    ("if", "else"): "what happens when it is not",
    ("may", "may"): "what happens if they say yes",
    ("may", "effects"): "what happens if they say yes",
    ("choose", "choose"): "the options",
    ("choose", "modes"): "the options",
    ("repeat", "effects"): "what happens each time",
    ("for_each", "effects"): "what happens for each one",
    ("sequence", "sequence"): "what happens, in order",
    ("sequence", "effects"): "what happens, in order",
}

_ANY_NODE = {
    "as": ParamShape(
        "as",
        TEXT,
        written_as=BY_BINDING,
        describes="the name later steps point at this by",
    ),
    "target": ParamShape("target", UNCHECKED, shaped_like=TARGET,
                         describes="what it acts on"),
    "optional": ParamShape("optional", FLAG, describes="the controller may decline it"),
    "description": ParamShape("description", TEXT, describes="what it says"),
    "prompt": ParamShape("prompt", TEXT, describes="what to ask them"),
    "store": ParamShape("store", TEXT, describes="a name to keep the result under"),
}
"""
The keys the executor takes off any node before the node is looked at.

One meaning each, wherever they appear, which is why they are described once.
"""


def _written_as(refers_to: str) -> str:
    """
    How a card names a player or a card for an *effect*.

    The split is real and belongs here, where both sides are in view. A target
    is resolved inside the ability and reads a bound group by its bare name; an
    effect is handed players as seat numbers, so a card naming one writes the
    single dynamic head that answers with a seat — and there is no head at all
    that answers with a card, which is why an effect taking a card is taking
    one the engine already has.
    """
    if refers_to == PLAYERS:
        return BY_PLAYER_OF

    if refers_to == CARDS:
        return BY_ENGINE

    return ""


def _shape_of(spec: EffectSpec) -> EffectShape:
    """
    An effect, flattened to what a card file may say about it.

    The handler is left behind here deliberately. A description that carried it
    would put a live function into the content pipeline, and the pipeline's
    whole value is that it can check a card without one.
    """
    return EffectShape(
        name=spec.name,
        params=MappingProxyType(
            {
                name: ParamShape(
                    name=param.name,
                    kind=(
                        UNCHECKED
                        if param.kind is ParamKind.OPEN
                        else str(param.kind)
                    ),
                    required=param.required,
                    nullable=param.nullable,
                    values=param.values,
                    least=param.least,
                    default=param.default,
                    describes=param.asks,
                    role=param.role or (STRUCTURE if name in spec.literal else ""),
                    unless=param.unless,
                    unless_when=param.unless_when,
                    refers_to=param.refers_to,
                    written_as=_written_as(param.refers_to),
                )
                for name, param in spec.params.items()
            }
        ),
        primary=spec.primary,
        open_ended=spec.open_ended,
        literal=spec.literal,
    )
