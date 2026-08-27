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
    ANY_GROUP,
    BY_BINDING,
    BY_ENGINE,
    BY_PLAYER_OF,
    CARDS,
    CONDITION,
    COST,
    MODE,
    NAMED_COUNT,
    OPEN,
    PLAYERS,
    STEP,
    STRUCTURE,
    TARGET,
    UNCHECKED,
    VALUES,
    WORKED_OUT,
    EffectShape,
    NodeShape,
    ParamShape,
    Written,
)
from fsme.effects import EffectRegistry, builtin_registry
from fsme.effects.registry import EffectSpec, ParamKind
from fsme.events import EventType
from fsme.rules.costs import COINS, COUNTERS, DISCARD, HP, TAP
from fsme.rules.restrictions import ACTIONS
from fsme.rules.statics import MONSTER_SCOPES, STATIC_SCOPES
from fsme.state.modifiers import MONSTER_STATS, STATS

from .condition_evaluator import ConditionEvaluator
from .effect_executor import COUNTABLE, WORKING_OUT
from .interpreter import (
    _MODIFIER_KEYS,
    CONTROL_BODIES,
    CONTROL_KEYS,
    CONTROL_NAMES,
    CONTROL_SPELLINGS,
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
            "worked_out": _WORKED_OUT,
            "named_count": _NAMED_COUNT,
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
    lists = {"conditions": CONDITION, "targets": TARGET, "effects": STEP}
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


STAT_BY_SCOPE = MappingProxyType(
    {
        scope: MONSTER_STATS if scope in MONSTER_SCOPES else STATS
        for scope in STATIC_SCOPES
        if scope != "self"
    }
)
"""
Which numbers a static may change, for each answer but one.

`_static_stat` reads ``scope in MONSTER_SCOPES or (monster and scope ==
"self")``, so five of the six scopes settle it on their own and ``self``
settles it only together with the kind of card the static is written on —
which is not one of the static's own answers, and so is not something this can
say. Leaving it out is the whole point of saying where a domain comes from:
an answer missing here is an answer nobody can resolve from the node alone.
"""


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
        domain_from="scope" if field.name == "stat" else "",
        domains=STAT_BY_SCOPE if field.name == "stat" else MappingProxyType({}),
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
                WHOLE,
                least=0,
                also=(Written(shaped_like=NAMED_COUNT, describes="of a named kind"),),
                describes="counters to spend",
                default=0,
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
                "effects", A_LIST, a_list_of=STEP, describes="what it does"
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


A_HEAD = "the way it is worked out"
"""
The group the five heads belong to: a specification names exactly one.

`_resolve_params` tries them in the order it lists them and takes the first it
finds, so a card writing two has written one and a sentence nobody reads.
"""


_WORKED_OUT = NodeShape(
    name="worked_out",
    params=MappingProxyType(
        {
            "from": ParamShape(
                "from",
                TEXT,
                refers_to=VALUES,
                one_of=A_HEAD,
                describes=WORKING_OUT["from"],
            ),
            "from_event": ParamShape(
                "from_event", TEXT, one_of=A_HEAD,
                describes=WORKING_OUT["from_event"],
            ),
            "last_result": ParamShape(
                "last_result", UNCHECKED, role=OPEN, one_of=A_HEAD,
                describes=WORKING_OUT["last_result"],
            ),
            "count": ParamShape(
                "count", TEXT, values=COUNTABLE, one_of=A_HEAD,
                describes=WORKING_OUT["count"],
            ),
            "player_of": ParamShape(
                "player_of", TEXT, refers_to=PLAYERS, one_of=A_HEAD,
                describes=WORKING_OUT["player_of"],
            ),
            "of": ParamShape(
                "of", UNCHECKED, refers_to=ANY_GROUP, describes=WORKING_OUT["of"]
            ),
            "minus": ParamShape(
                "minus", UNCHECKED, refers_to=ANY_GROUP,
                describes=WORKING_OUT["minus"],
            ),
            "floor": ParamShape("floor", WHOLE, describes=WORKING_OUT["floor"]),
            "times": ParamShape("times", WHOLE, describes=WORKING_OUT["times"]),
            "plus": ParamShape("plus", WHOLE, describes=WORKING_OUT["plus"]),
        }
    ),
)
"""
A number a card does not know when it is written.

Every key `_resolve_params` reads, described where the executor names them, so
that a layer offering "a number, or work one out" can say what working one out
looks like.
"""

_NAMED_COUNT = NodeShape(
    name="named_count",
    params=MappingProxyType(
        {
            "counter": ParamShape(
                "counter", TEXT, describes="which counter to spend"
            ),
            "amount": ParamShape(
                "amount", WHOLE, least=0, describes="how many of them"
            ),
        }
    ),
)
"""
A price paid in counters, when the card has more than one kind on it.

`_counter_cost` reads a plain number as `charge` counters and this as any of
them, which is two ways of writing one price.
"""


_CONTROL_FIELDS: dict[tuple[str, str], ParamShape] = {}


A_TARGET_NAMED = (Written(kind=TEXT, describes="a target, named"),)
"""
The two ways a card may say what something acts on.

``normalise`` takes ``"all_players"`` and
``{"random_player": {"exclude_controller": true}}`` alike, so a layer offering
only one of them would call half the cards in the game mistakes. The described
form leads because it is the general one; this is the other.
"""


def _control_field(node: str, key: str) -> ParamShape:
    """
    One key of one control node, as the expander that reads it will take it.

    A body holds more of the language and says which kind; the head of a node
    is usually the body written the short way; and the handful of keys any node
    accepts mean the same thing wherever they appear.
    """
    bodies = {
        ("if", "then"): STEP,
        ("if", "else"): STEP,
        ("if", "if"): CONDITION,
        ("if", "conditions"): CONDITION,
        ("may", "may"): STEP,
        ("may", "effects"): STEP,
        ("choose", "choose"): MODE,
        ("choose", "modes"): MODE,
        ("repeat", "effects"): STEP,
        ("for_each", "effects"): STEP,
        ("sequence", "sequence"): STEP,
        ("sequence", "effects"): STEP,
    }

    first, second = CONTROL_SPELLINGS.get(node, ("", ""))
    spelling = key if key == second else ""
    # A head that is also the second spelling has to be there to name its node
    # and is read only when the first spelling is absent, so what it carries
    # when the first *is* there is nothing anybody reads.
    placeholder = (
        (Written(kind=UNCHECKED, describes="a placeholder, when the answer is "
                                           "written under its other name"),)
        if spelling and key == node
        else ()
    )

    if (node, key) in bodies:
        return ParamShape(
            key,
            A_LIST,
            a_list_of=bodies[(node, key)],
            also=placeholder,
            instead_of=first if spelling else "",
            names_the_node=key == node,
            describes=_CONTROL_WORDS.get((node, key), ""),
        )

    if (node, key) == ("for_each", "for_each") or (node, key) == ("for_each", "of"):
        return ParamShape(
            key,
            UNCHECKED,
            shaped_like=TARGET,
            also=A_TARGET_NAMED,
            instead_of=first if spelling else "",
            names_the_node=key == node,
            describes="what to do it for each of",
        )

    if (node, key) in (("repeat", "repeat"), ("repeat", "times")):
        return ParamShape(
            key,
            WHOLE,
            least=0,
            instead_of=first if spelling else "",
            names_the_node=key == node,
            describes="how many times",
        )

    if (node, key) == ("stop", "stop"):
        # The head names the node and carries nothing: the interpreter reads
        # `op.name` and never looks at the value.
        return ParamShape(
            key,
            UNCHECKED,
            role=OPEN,
            names_the_node=True,
            describes="nothing further happens",
        )

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
        defines=ANY_GROUP,
        describes="the name later steps point at this by",
    ),
    "target": ParamShape(
        "target",
        UNCHECKED,
        shaped_like=TARGET,
        also=A_TARGET_NAMED,
        describes="what it acts on",
    ),
    "optional": ParamShape("optional", FLAG, describes="the controller may decline it"),
    "description": ParamShape("description", TEXT, describes="what it says"),
    "prompt": ParamShape("prompt", TEXT, describes="what to ask them"),
    "store": ParamShape(
        "store",
        TEXT,
        defines=VALUES,
        describes="a name to keep the result under",
    ),
}
"""
The keys the executor takes off any node before the node is looked at.

One meaning each, wherever they appear, which is why they are described once.
"""


WORKED_OUT_INSTEAD = (
    Written(
        shaped_like=WORKED_OUT,
        describes="worked out while the ability runs",
    ),
)
"""
The second way nearly every effect parameter may be written.
"""


def _also_worked_out(spec: EffectSpec, name: str) -> tuple[Written, ...]:
    """
    Whether this parameter may be given a way of working its value out.

    ``_resolve_params`` walks every key an effect was written with and turns a
    specification into a value — every key except the ones the effect keeps
    exactly as the card wrote them. So the answer is not per parameter and not
    per effect: it is "all of them but the literal ones", read off the same
    ``literal`` the executor reads.

    Which is why this is derived here rather than declared sixty-three times.
    A card writing ``{"amount": {"from": "dice"}}`` has not made a mistake, and
    a layer saying ``amount`` is a whole number and nothing else was calling
    thirteen shipped cards wrong.
    """
    return () if name in spec.literal else WORKED_OUT_INSTEAD


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
                    also=_also_worked_out(spec, name),
                )
                for name, param in spec.params.items()
            }
        ),
        stores=spec.stores or "",
        primary=spec.primary,
        open_ended=spec.open_ended,
        literal=spec.literal,
    )
