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

from fsme.cards.definition import Ability, CardDefinition, Static
from fsme.cards.references import REPLACES_THE_EVENT
from fsme.cards.types import PRINTED_NUMBERS, TYPE_LABELS, TYPE_WORDS, CardType
from fsme.content import Vocabulary
from fsme.content.vocabulary import (
    A_LIST,
    A_MAPPING,
    ABILITY,
    ANY_GROUP,
    BY_BINDING,
    BY_ENGINE,
    BY_PLAYER_OF,
    CARD,
    CARDS,
    CHANGE,
    CONDITION,
    COST,
    DEEPER,
    FIRST,
    MODE,
    MORE,
    NAMED_COUNT,
    NEVER,
    OPEN,
    PLAYERS,
    REPLACING,
    STATIC,
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
from fsme.events.types import WHEN_IT_HAPPENS
from fsme.rules.activation import ACTIVATED_BY
from fsme.rules.costs import COINS, COUNTERS, DISCARD, HP, TAP
from fsme.rules.loot import PLAYED_BY
from fsme.rules.restrictions import ACTION_WORDS, ACTIONS
from fsme.rules.statics import MONSTER_SCOPES, SCOPE_WORDS, STATIC_SCOPES
from fsme.state.modifiers import MONSTER_STATS, STAT_WORDS, STATS
from fsme.state.promises import CAP, CHANGES, DELTA, FACTOR, FLIP, FLOOR, VALUE

from .condition_evaluator import ConditionEvaluator
from .effect_executor import COUNTABLE, WORKING_OUT
from .interpreter import (
    _MODIFIER_KEYS,
    CONTROL_BODIES,
    CONTROL_KEYS,
    CONTROL_NAMES,
    CONTROL_SPELLINGS,
)
from .runtime import (
    ABILITY_SCOPE_WORDS,
    ABILITY_SCOPES,
    ABILITY_ZONES,
    ZONE_WORDS,
    ability_scope,
)
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
        used_by=USED_BY,
        type_labels=MappingProxyType(
            {str(kind): label for kind, label in TYPE_LABELS.items()}
        ),
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
    What a card, an ability, a static and each control node may be written with.

    The three card structures are read off their own dataclasses: ``from_data``
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

    ``card`` is the one of these the checker does not hold a card to. Inside the
    DSL an unknown key is a mistake, because the interpreter reads these keys
    and hands nothing else on; at the top of a card file an unknown field is
    kept, because a set may carry an artist credit or a schema version this
    engine has never heard of. So the card shape says what a card *may* write
    and never what it may not, which is exactly what something drawing a form
    needs and is not a rule to refuse a file by.
    """
    return MappingProxyType(
        {
            CARD: NodeShape(
                name=CARD,
                params=MappingProxyType(
                    {
                        field.name: _card_field(field)
                        for field in fields(CardDefinition)
                    }
                ),
                bodies=CARD_BODIES,
            ),
            ABILITY: NodeShape(
                name=ABILITY,
                params=MappingProxyType(
                    {field.name: _ability_field(field) for field in fields(Ability)}
                ),
                own_names=ABILITY in OWN_NAMES,
            ),
            STATIC: NodeShape(
                name=STATIC,
                params=MappingProxyType(
                    {field.name: _static_field(field) for field in fields(Static)}
                ),
                own_names=STATIC in OWN_NAMES,
            ),
            COST: _COST,
            MODE: _MODE,
            WORKED_OUT: _WORKED_OUT,
            NAMED_COUNT: _NAMED_COUNT,
            CHANGE: _CHANGE,
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
    "int | None": WHOLE,
    "CardType": TEXT,
    "frozenset[str]": A_LIST,
    "Mapping[str, int]": A_MAPPING,
    "tuple[Ability, ...]": A_LIST,
    "tuple[Static, ...]": A_LIST,
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


OWN_NAMES = (ABILITY, STATIC)
"""
The parts of a card that keep the names they make to themselves.

``Runtime`` builds a fresh ``AbilityContext`` every time it resolves an ability
and the statics are asked one at a time with a context of their own, so nothing
one part of a card stores or binds is there for another to read. A card is a
composition of independent rules, not one rule written down in pieces, and this
is the sentence that says so to anything reading the metadata.
"""

CARD_BODIES = ("abilities", "statics")
"""
Where a card keeps the parts it is composed of.

The same thing ``bodies`` says about a branch, said about the whole card: these
are lists of more of the language, and a card with both of them empty does
nothing at all whatever else it says.
"""

CARD_WORDS = {
    "id": "what the engine calls it",
    "name": "what it is called",
    "type": "which kind of card it is",
    "expansion": "which set it belongs to",
    "abilities": "the rules it follows",
    "statics": "what it changes while it is in play",
    "health": "hit points",
    "attack": "attack",
    "roll": "the roll needed to hit it",
    "cost": "what it costs to buy",
    "souls": "souls it is worth",
    "tags": "families it belongs to",
    "rewards": "what defeating it pays out",
    "metadata": "notes that are not rules — its printed text, and anything else",
}


USED_BY = MappingProxyType(
    {
        str(CardType.LOOT): str(PLAYED_BY),
        str(CardType.TREASURE): str(ACTIVATED_BY),
        str(CardType.STARTING_ITEM): str(ACTIVATED_BY),
    }
)
"""
How a card of each kind does the thing it is for, where the engine settles it.

Somebody who has just said "this card should deal damage" has not been asked
when, and should not have to be: playing a loot card is what a loot card is
for, and an item nobody can activate is an item that does nothing. Both are
the engine's own answers — `play_loot` emits one and `_activatable` refuses an
item without the other — so both are read from beside those rules rather than
written down a second time here.

The kinds missing from this are missing on purpose. A monster, a room, a
character and a curse each react to several moments and no single one of them
is *the* moment, so there is nothing to fill in and whatever is asking has to
ask. Silence is not a claim that such a card cannot act; it is the absence of
one right answer, and guessing would put a trigger on a card that never fires.
"""


CARD_ASKS = {
    "name": "What is it called?",
    "type": "What kind of card is it?",
    "abilities": "What does it do?",
    "statics": "What does it change while it is in play?",
    "health": "How many hit points?",
    "attack": "How much damage does it deal?",
    "roll": "What roll is needed to hit it?",
    "cost": "What does it cost to buy?",
    "souls": "How many souls is it worth?",
    "tags": "Which families does it belong to?",
    "rewards": "What does defeating it pay out?",
    "metadata": "Anything else worth noting?",
}

CARD_ASKED = {
    # A card is a name, a kind, and what it does. The printed numbers matter to
    # the kinds that have them and are noise on the kinds that do not, which
    # `unless` already knows — so they are one click away rather than in front
    # of somebody making a loot card.
    "name": FIRST,
    "type": FIRST,
    "abilities": FIRST,
    "statics": FIRST,
    "health": MORE,
    "attack": MORE,
    "roll": MORE,
    "cost": MORE,
    "souls": MORE,
    "tags": DEEPER,
    "rewards": DEEPER,
    "metadata": DEEPER,
}


def _printed_on(number: str) -> tuple[Any, ...]:
    """
    The kinds of card that do *not* carry this printed number.

    Said as an absence because that is the shape ``unless_when`` has: a
    parameter is moot while another answer holds one of these. A kind nobody
    has described is not in the list, so nothing is refused to it — silence
    about ``starting_item`` is silence, not a claim that it has no cost.
    """
    return tuple(
        str(kind)
        for kind, numbers in PRINTED_NUMBERS.items()
        if number not in numbers
    )


def _card_field(field: Field[Any]) -> ParamShape:
    """
    One field of a card, as a card file may write it.

    The composition falls straight out of the dataclass: ``abilities`` and
    ``statics`` are annotated as tuples of the two things this module already
    describes, so they are lists of those nodes and anything that can draw a
    list of effects can draw them.

    The printed numbers are the one place a card asks a question that depends
    on another answer. A loot card has no hit points, and ``unless`` is already
    the language's word for a question another answer has settled — so it is
    said with that rather than with a rule of its own.
    """
    lists = {"abilities": ABILITY, "statics": STATIC}
    # Written by whatever makes the card, from the set it is going into and the
    # name somebody gave it. A form offering either takes an answer it is about
    # to overwrite.
    ours = ("id", "expansion")
    # Free-form data the engine keeps and does not read: a list of family names
    # with no closed set, what a monster pays out, and the card's own notes.
    # None of them is a value anybody types into a box.
    theirs = ("tags", "rewards", "metadata")

    return ParamShape(
        field.name,
        _kind_of(field),
        nullable="None" in str(field.type),
        required=field.name in ("id", "name", "type", "expansion"),
        values=(
            tuple(str(kind) for kind in CardType) if field.name == "type" else ()
        ),
        a_list_of=lists.get(field.name, ""),
        role=STRUCTURE if field.name in theirs else "",
        written_as=BY_BINDING if field.name in ours else "",
        unless="type" if field.name in _EVERY_PRINTED_NUMBER else "",
        unless_when=(
            _printed_on(field.name)
            if field.name in _EVERY_PRINTED_NUMBER
            else ()
        ),
        values_mean=(
            MappingProxyType({str(k): v for k, v in TYPE_WORDS.items()})
            if field.name == "type"
            else MappingProxyType({})
        ),
        describes=CARD_WORDS.get(field.name, ""),
        asks=CARD_ASKS.get(field.name, ""),
        asked=CARD_ASKED.get(field.name, ""),
        default=_default_of(field),
    )


_EVERY_PRINTED_NUMBER = frozenset(
    number for numbers in PRINTED_NUMBERS.values() for number in numbers
)
"""
Every number some kind of card carries printed on it.

Derived rather than listed: a number nobody has said any card prints is a
number no kind of card can be said to be missing, so it is asked of all of
them.
"""


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
"""
What each field of an ability *is*, for building sentences out of.
"""

ABILITY_ASKS = {
    "trigger": "When does this happen?",
    "conditions": "Only if…?",
    "targets": "What does it pick out first?",
    "effects": "What happens?",
    "optional": "May the player say no?",
    "cost": "What does the player pay?",
    "replacement": "Does it change the event instead of reacting to it?",
    "scope": "Whose actions does it react to?",
    "zone": "Where must the card be?",
    "description": "What does the card say, in your own words?",
}
"""
What each field of an ability *asks*, which is a different question.
"""

ABILITY_ALLOWS = {
    REPLACES_THE_EVENT: REPLACING,
}
"""
Which of an ability's answers lets an effect that needs something be used.

One entry, and the pairing it publishes is the one the validator applies: an
effect that reaches for the event an ability was handed only works where an
ability was handed one. Anything offering effects reads this rather than
knowing the field, which is the difference between a renderer that follows the
language and one that has a copy of it.
"""

ABILITY_ASKED = {
    # What the card does, and when. Everything else is a refinement of it.
    "trigger": FIRST,
    "effects": FIRST,
    "conditions": MORE,
    "cost": MORE,
    "optional": MORE,
    # An ability binds what it picks out under a name; the question "who does
    # this happen to" is already asked beside the effect that acts on it, and
    # asking it twice is how a card comes to choose two different players and
    # mean one.
    "targets": NEVER,
    "scope": DEEPER,
    "zone": DEEPER,
    "replacement": DEEPER,
    "description": DEEPER,
}
"""
When to ask about each field of an ability.

Not derivable: all but two are optional values of ordinary kinds, and being
optional says nothing about whether somebody writing their first card wants to
be asked. Scope and zone are the two that decide whether an ability works at
all, and are still the last two anybody should meet.
"""

STATIC_WORDS = {
    "stat": "which number it changes",
    "amount": "by how much",
    "forbids": "an action it does not allow instead",
    "per_counter": "a counter it is worth its amount for each of",
    "scope": "who it applies to",
    "conditions": "when it applies, beyond its card being in play",
    "description": "what it says, in a person's words",
}
"""
What each field of a static *is*, for building sentences out of.
"""

STATIC_ASKS = {
    "stat": "Which number does it change?",
    "amount": "By how much?",
    "forbids": "Or: which action does it stop?",
    "per_counter": "Count it once per counter of which kind?",
    "scope": "Who does it affect?",
    "conditions": "Only while…?",
    "description": "What does the card say, in your own words?",
}

STATIC_ASKED = {
    # Which number, who it reaches, and by how much: the three that make a
    # static a static. Asking "by how much" before "which number" is what the
    # alphabet used to do.
    "stat": FIRST,
    "scope": FIRST,
    "amount": FIRST,
    "forbids": MORE,
    "conditions": MORE,
    "per_counter": DEEPER,
    "description": DEEPER,
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

    glosses = {
        "trigger": TRIGGER_WORDS,
        "scope": ABILITY_SCOPE_WORDS,
        "zone": ZONE_WORDS,
    }

    return ParamShape(
        field.name,
        _kind_of(field),
        # An ability without one never runs, and the checker says so. Saying it
        # here too is what lets a form ask for it first and mark it needed.
        required=field.name == "trigger",
        values=values.get(field.name, ()),
        values_mean=glosses.get(field.name, MappingProxyType({})),
        a_list_of=lists.get(field.name, ""),
        shaped_like=COST if field.name == "cost" else "",
        describes=ABILITY_WORDS.get(field.name, ""),
        asks=ABILITY_ASKS.get(field.name, ""),
        asked=ABILITY_ASKED.get(field.name, ""),
        allows=ABILITY_ALLOWS.get(field.name, ""),
        default=None if field.name == "scope" else _default_of(field),
    )


TRIGGER_WORDS = MappingProxyType(
    {str(event): said for event, said in WHEN_IT_HAPPENS.items()}
)
"""
What each moment a card can react to is, in a person's words.

The engine's own sentence for every event, keyed by the name a card writes.
A list of sixty-six identifiers is a list somebody has to look up; the same
list with these on it is a question they can answer.
"""


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
    glosses = {
        "scope": SCOPE_WORDS,
        "forbids": ACTION_WORDS,
        "stat": STAT_WORDS,
    }

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
        values_mean=glosses.get(field.name, MappingProxyType({})),
        a_list_of=CONDITION if field.name == "conditions" else "",
        domain_from="scope" if field.name == "stat" else "",
        domains=STAT_BY_SCOPE if field.name == "stat" else MappingProxyType({}),
        describes=STATIC_WORDS.get(field.name, ""),
        asks=STATIC_ASKS.get(field.name, ""),
        asked=STATIC_ASKED.get(field.name, ""),
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


CHANGE_WORDS = {
    VALUE: "what to put there instead",
    DELTA: "add this to it",
    FACTOR: "multiply it by this",
    CAP: "lower it to at most this",
    FLOOR: "raise it to at least this",
    FLIP: "read it from the other side: this less what it was",
}
"""
What each of the six changes does, as a question rather than as prose.

``state/promises.py`` states them for a reader — "Lower a number to at most
this" — and a form needs them for somebody filling one in. Read by name from
``CHANGES`` below, so a change the engine gains and nobody describes fails
where it is built rather than reaching a person as a bare word.
"""


def _one_change(name: str) -> ParamShape:
    """
    One of the six, as a question.

    ``value`` is the one that is not a number: it puts back whatever the event
    should carry, which on `compost` is the word "discard". The other five read
    a number and compose in the order ``CHANGES`` lists them — and every one of
    them is moot once ``value`` is written, because ``apply_to`` settles the
    value and moves on before any of them runs. That is not a rule invented
    here; it is the ``continue`` in the applier, said with the language's own
    word for a question another answer has already closed.
    """
    if name == VALUE:
        return ParamShape(name, UNCHECKED, role=OPEN, describes=CHANGE_WORDS[name])

    return ParamShape(name, WHOLE, unless=VALUE, describes=CHANGE_WORDS[name])


_CHANGE = NodeShape(
    name=CHANGE,
    params=MappingProxyType({name: _one_change(name) for name in CHANGES}),
)
"""
One change a promise owes to a value an event carries.

The six ways the engine has of changing such a value, which until this were
declared in ``state/promises.py``, enforced in ``promise`` itself, and
described nowhere — so three of them, ``cap``, ``floor`` and ``flip``, could
not be found by anybody who did not already know they existed, and three of the
four promises in the shipped sets use one.

Nothing here is required. A change carries one of the six, or several of the
five that compose; insisting on any would refuse every promise ever written.

The names are ``CHANGES`` itself, in its order, so this cannot come to describe
an operation the engine does not have or miss one it gains.
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


def _kept_under_a_name(spec: EffectSpec) -> dict[str, ParamShape]:
    """
    Whether this effect may be asked what to call the value it leaves behind.

    ``store`` is one of the keys the executor takes off any node, described
    once in ``_ANY_NODE`` because it means one thing wherever it appears —
    and a control node has always carried that description. An effect never
    did, though the interpreter accepts the key on any step, which left a
    card saying something the engine reads and nothing offering to say it.

    Which effects may be asked is not a list kept here. It is ``stores``, the
    effect's own statement that it produces a value at all: an effect that
    produces nothing has nothing to name, and asking for a name would be
    asking for one nothing can create.
    """
    return {"store": _ANY_NODE["store"]} if spec.stores else {}


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
                    # The one an effect is mostly about. Thirty-seven effects
                    # already say which, because it is the one the shorthand
                    # form fills: `{"gain_coins": 3}` means the amount. That is
                    # the same parameter a person wants to be asked about
                    # first, so it is read rather than declared again.
                    asked=FIRST if name == spec.primary else "",
                    describes=param.asks,
                    role=param.role or (STRUCTURE if name in spec.literal else ""),
                    unless=param.unless,
                    unless_when=param.unless_when,
                    refers_to=param.refers_to,
                    written_as=_written_as(param.refers_to),
                    # One declaration, published as whichever it is. The
                    # kind already says whether the parts are in a list or
                    # under names, so the effect is not asked twice.
                    a_list_of=(
                        "" if param.kind is ParamKind.MAPPING else param.a_list_of
                    ),
                    each_shaped_like=(
                        param.a_list_of if param.kind is ParamKind.MAPPING else ""
                    ),
                    also=_also_worked_out(spec, name),
                )
                for name, param in spec.params.items()
            }
            | _kept_under_a_name(spec)
        ),
        stores=spec.stores or "",
        hits=spec.hits,
        replacing=spec.replacing,
        primary=spec.primary,
        open_ended=spec.open_ended,
        literal=spec.literal,
    )
