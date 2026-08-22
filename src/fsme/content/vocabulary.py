# src/fsme/content/vocabulary.py

"""
The names content is allowed to use.

Semantic validation asks whether a card refers to things the engine actually
implements. That question needs the engine's vocabulary, but the pipeline must
not depend on the engine's execution: content loading happens before a game
exists and must never touch one.

So the vocabulary arrives as plain names. The pipeline checks spelling against
a set of strings; whoever owns a live engine is the one who knows what is in
it, and hands the list over.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

AMOUNT = "amount"
WHICH = "which"
SWITCH = "switch"
NAMES = "names"
WHOM = "whom"
DEFINES = "defines"
STRUCTURE = "structure"
BODY = "body"
NESTED = "nested"
OPEN = "open"

ROLES = (
    AMOUNT,
    WHICH,
    SWITCH,
    NAMES,
    WHOM,
    DEFINES,
    STRUCTURE,
    BODY,
    NESTED,
    OPEN,
)
"""
What a parameter is *for*, as distinct from what it accepts.

``kind`` says what a value must be if a card writes one; a role says what
somebody is being asked and therefore how to ask it. They are different
questions and the difference matters: ``deal_damage.dealt_by`` and
``add_counter.counter`` both accept a thing the pipeline cannot judge, but one
is a card the engine hands over and the other is a word an author types.

- ``amount`` — how many of the effect's own thing. A number.
- ``which`` — one of a closed set. A choice.
- ``switch`` — on or off.
- ``names`` — free text naming something: a counter, a label.
- ``whom`` — a card or a player the *ability* picks out. **Not a field**: an
  author says this by aiming the effect, which is a question the form already
  asks.
- ``defines`` — a name this step invents for a later one to point at. The
  other end of ``whom`` and of ``refers_to``: those read a name, this writes
  one, and calling both of them "some text" is how an interface comes to offer
  a box for reading a name nothing can create.
- ``structure`` — nested data whose inside this layer does not describe. The
  only honest way to show one is as what it is; never a box.
- ``body`` — a list of nodes of a kind that *is* described: effects,
  conditions, targets, modes. The difference from ``structure`` is the whole
  point: whatever draws a list of effects at the top of an ability draws the
  one inside a branch, because they are the same list.
- ``nested`` — exactly one node of a described kind. An ability's cost is a
  small group of related answers, not a value and not a list.
- ``open`` — genuinely any value, and the last resort.

A role is one word rather than a sentence, which is what makes it possible to
require one of every parameter. Anything showing a parameter to a person reads
this to decide *how*; ``describes`` refines *what it is called*.
"""

BY_NAME = "the name of something the ability chose"
BY_PLAYER_OF = "player_of"
BY_STORED = "the name of a value an earlier step stored"
BY_ENGINE = "the engine supplies it"
BY_BINDING = "FSME writes this one for you"

WRITINGS = (BY_NAME, BY_PLAYER_OF, BY_STORED, BY_ENGINE, BY_BINDING)
"""
How a card writes a parameter that names something instead of carrying a value.

Four sentences, because the engine has four answers and no more:

- ``BY_NAME`` — the bare name of a group the ability bound with ``as``. Every
  target that asks whose things it is about reads its ``of`` this way.
- ``BY_PLAYER_OF`` — ``{"player_of": "gift"}``, the one dynamic head that
  answers with a player. Effects are handed players as seat numbers, so an
  effect naming a player writes this and a target naming one does not.
- ``BY_STORED`` — the name of a value an earlier step wrote with ``store``.
  A different namespace from the groups, and asking for one where the other
  belongs is a card that quietly compares nothing.
- ``BY_ENGINE`` — nothing a card writes at all. ``claim_soul`` takes the card
  that becomes the soul and no card file has ever given it one, because the
  only way to name a card is to be one.
- ``BY_BINDING`` — the name a target is bound under, so that later steps can
  point at it. Written in every card file and answered by no author: whatever
  is writing the card chooses the name, and a form offering the box takes an
  answer it is about to overwrite.

Anything showing a parameter to a person reads this to decide *what to offer*;
``role`` decides how to draw it and ``refers_to`` says what kind of thing is
being named.
"""


A_LIST = "a list"
"""
The kind given to a parameter that takes several values rather than one.

Named because the difference between ``"loot"`` and ``["loot"]`` is invisible
in a form and fatal in a card: a parameter that takes a list and is given one
value has been given a mistake, not a shorthand.
"""

EFFECT = "effect"
CONDITION = "condition"
TARGET = "target"
MODE = "mode"
COST = "cost"
STEP = "step"
WORKED_OUT = "worked_out"
NAMED_COUNT = "named_count"

NODES = (EFFECT, CONDITION, TARGET, MODE, COST, STEP, WORKED_OUT, NAMED_COUNT)
"""
The kinds of node one part of the language may be built out of another.

Not a new idea in the DSL — every one of these is already written inside cards
today. What is new is saying so: an ability's ``effects`` is a list of effect
nodes, a branch's ``then`` is the same list, ``choose`` holds a list of modes,
and an ability's ``cost`` is one node of its own kind.

Three of them are described by registries a card already reads — ``effect``,
``condition`` and ``target``. ``step`` is the pair of them a list of things
that happen really holds: an effect node, or a control node, and a list whose
elements may be either is not a list of effects however it is usually written.
The rest are described by node shapes of their own, because nothing else
describes them: ``mode``, ``cost``, ``worked_out`` and ``named_count``.

Named here so that ``a_list_of`` and ``shaped_like`` can only say something the
rest of this layer can answer.
"""


A_MAPPING = "a set of named values"
"""
The kind given to a parameter that takes named values rather than one value.

``promise`` is owed a change per key — ``{"amount": {"times": 2}}`` — and a
card that writes a word there has written a sentence where a structure belongs.
What is *inside* one of these cannot be judged before a game exists; that it is
one can, and the handler already refuses anything else.
"""

UNCHECKED = "anything the engine can only judge during a game"
"""
The kind given to a parameter this layer deliberately does not check.

It means the effect takes a card, a player, or a shape that only means
something once a board exists — **not** that anything is acceptable. The
runtime guard stays where it is and still raises; what this says is that load
time is the wrong place to ask, because answering would need a game.
"""


@dataclass(frozen=True, slots=True)
class Written:
    """
    One of the ways a parameter may be written, when there is more than one.

    ``deal_damage`` takes a number of hearts — or ``{"from": "dice"}``, which
    is not a number and becomes one while the ability runs. Both are correct
    and the card means something different by each, so a layer that can only
    say "a whole number" is a layer that calls half the cards in the game
    mistakes.

    Said with the same words a parameter uses for its first way of being
    written, because it is the same question asked again.
    """

    kind: str = ""
    values: tuple[Any, ...] = ()
    least: int | None = None
    shaped_like: str = ""
    a_list_of: str = ""
    describes: str = ""


@dataclass(frozen=True, slots=True)
class ParamShape:
    """
    What a card may write for one parameter of one effect.

    Plain data on purpose. The engine describes its effects with live objects
    that hold the functions implementing them; this is what survives the trip
    to a pipeline that must never hold one.
    """

    name: str
    kind: str

    required: bool = False
    nullable: bool = False

    values: tuple[Any, ...] = ()
    least: int | None = None

    default: Any = None
    """
    What the effect does when a card leaves this out, where anything knows.

    Only effects say: their parameters are read off the function that
    implements them, so the default is the handler's own. A target or a
    condition names its parameters by hand and names no default with them.
    """

    role: str = ""
    """
    What kind of question this parameter is — see ``ROLES``.

    Empty means nobody has said, which is a fault rather than a default: a
    parameter with no role cannot be shown to anybody, because nothing knows
    how to ask for it. A test refuses an engine that has one.
    """

    unless: str = ""
    """
    Another parameter that makes this one meaningless.

    ``heal`` restores everything when ``full`` is set and ignores ``amount``,
    so a form that shows both at once invites a card that says two things and
    quietly gets one. Named here because the handler is where the choice is
    made.
    """

    describes: str = ""
    """
    What this parameter is, in the words a person would use for it.

    ``amount`` is a name for us; "how many cents" is what a form asks. Empty
    means nobody has said, and whatever is asking should fall back to the
    parameter's own name.
    """

    unless_when: tuple[Any, ...] = ()
    """
    The values of ``unless`` that actually make this parameter moot.

    Empty means any value the author gives — ``modify_event`` reads ``factor``
    only when ``delta`` was left out, so writing a delta at all settles it.
    ``move_cards`` is the other shape: ``depth_from`` is counted from the top
    and means nothing when ``position`` is ``bottom``, which is also the
    default, so the value has to be named or a form would offer a depth that
    the effect will not read.

    A switch is moot-making when it is on, whatever this says: ``false`` is
    what a card that left it out means.
    """

    also: tuple[Written, ...] = ()
    """
    The other ways this parameter may be written — see ``Written``.

    Empty for nearly everything: most parameters take one sort of thing. Where
    it is not empty, the first way is the one above and these are the rest, and
    a card matching any of them is a card that says what it means.
    """

    defines: str = ""
    """
    The kind of name this parameter invents, for a later step to point at.

    The mirror of ``refers_to``. ``store`` writes a name into the ability's
    values and ``values_equal`` reads one back; ``as`` writes a name into its
    groups and ``chooser`` reads one back. Both ends said the same way, so that
    nothing offers a box for reading a name that nothing can create.
    """

    domain_from: str = ""
    """
    Another answer in this node that decides which values are allowed.

    A static's ``stat`` is one of a monster's two or one of a player's eight,
    and which depends on the scope written beside it. There is no list to give
    until that is answered, and giving the union would be giving a list that is
    wrong half the time — so what is said instead is *where the answer comes
    from*.
    """

    names_the_node: bool = False
    """
    Whether this key is the node's name rather than one of its answers.

    ``{"if": [...]}`` is a branch because it says ``if``, and the same key
    carries the conditions. Something writing a card has to put the key there;
    nobody has to be asked for it.
    """

    a_list_of: str = ""
    """
    This parameter holds a list of nodes of one of the kinds in ``NODES``.

    Different from ``kind == A_LIST``, which says only that several values go
    here, and different again from ``STRUCTURE``, which says the inside is not
    described. This says the inside *is* described, and by what — so whatever
    can draw a list of effects can draw every list of effects in the language,
    at any depth, because they are all this.
    """

    shaped_like: str = ""
    """
    This parameter holds exactly one node of one of the kinds in ``NODES``.

    ``for_each`` is given one target specification, and an ability is given
    one cost. Neither is a value and neither is a list, and calling either of
    them text is how a form comes to ask for a structure in a box.
    """

    instead_of: str = ""
    """
    Another parameter this one is a second spelling of.

    ``player_has_coins`` reads ``amount``, then ``count``, then ``value``, and
    takes the first it finds: three names for one number, because cards were
    written with all three. That is right for reading a card and wrong for
    asking a person, who would be asked the same question three times and told
    nothing about which answer wins.

    So the spellings are named here and the question is asked once, under the
    one this points at. Nothing is refused: a card writing any of them still
    loads, because the engine still reads all of them.
    """

    written_as: str = ""
    """
    How a card writes this parameter, when it names something rather than
    carrying a value — see ``WRITINGS``.

    Worked out from ``refers_to`` for anything a target or a condition takes,
    because those all name a group the same way. An effect is the exception
    and says so at registration: the engine hands effects players and cards
    directly, so naming one is a different sentence.
    """

    refers_to: str = ""
    """
    What a parameter that names something else is naming.

    Empty for an ordinary value. Otherwise this parameter does not carry a
    value at all — it carries the name of a group the ability bound earlier,
    or of a value it stored — and this says which, and of what kind. The
    engine draws exactly one distinction between kinds, so this has exactly
    the words for it and no more.
    """

    @property
    def checkable(self) -> bool:
        return self.kind != UNCHECKED

    LISTABLE = 12
    """
    How many allowed values are worth naming before a list stops helping.

    Nine stats read as a choice. Sixty-six event names read as a wall, and
    a message somebody scrolls past is a message that did not say anything.
    """

    def __post_init__(self) -> None:
        """
        Work out the role when nobody said, which is nearly always.

        Four of the seven follow from what a parameter accepts, so requiring
        anybody to write them down would be requiring them to repeat
        themselves — and a thing people have to repeat is a thing that drifts.
        What cannot be worked out is a value this layer is unable to judge:
        that is either the effect's own nested data or something a game hands
        over, and only whoever wrote the effect knows which.
        """
        if not self.written_as:
            object.__setattr__(self, "written_as", _written_as_for(self))

        if self.role:
            return

        object.__setattr__(self, "role", _role_for(self))

    def wants(self) -> str:
        """
        What this parameter takes, in the words an error message needs.
        """
        if self.values:
            if len(self.values) > self.LISTABLE:
                return f"one of the {len(self.values)} {self.name}s the engine knows"

            return " or ".join(repr(value) for value in self.values)

        if self.least is not None:
            return f"{self.kind} of at least {self.least}"

        return self.kind


@dataclass(frozen=True, slots=True)
class EffectShape:
    """
    What one effect takes, as far as a card file is concerned.
    """

    name: str

    params: Mapping[str, ParamShape] = field(
        default_factory=lambda: MappingProxyType({})
    )

    primary: str | None = None
    """
    The parameter the shorthand form fills.

    ``{"gain_coins": 3}`` means ``amount=3``; the effect says which, so nothing
    reading a card has to guess.
    """

    open_ended: bool = False
    """
    Whether the effect accepts keywords it has not named.

    True for the two dozen that work only on their targets. Nothing may be
    refused for them, because they would accept it.
    """

    literal: frozenset[str] = frozenset()
    """
    Parameters handed to the effect exactly as the card wrote them.

    Their values are the effect's own structured data, so nothing here may
    judge them.
    """


def _written_as_for(parameter: ParamShape) -> str:
    """
    How a card writes this parameter, read off what it names.

    Only the two a target or a condition can say. An effect that names a
    player or a card is told at registration, because for an effect the answer
    depends on the engine handing it the thing rather than on the parameter.
    """
    if not parameter.refers_to:
        return ""

    return BY_STORED if parameter.refers_to == VALUES else BY_NAME


def _role_for(parameter: ParamShape) -> str:
    """
    What kind of question a parameter is, read off the rest of it.
    """
    if parameter.defines:
        # It invents a name rather than answering a question.
        return DEFINES

    if parameter.a_list_of:
        # More of the language, listed. Whatever draws one draws them all.
        return BODY

    if parameter.shaped_like:
        # More of the language, once.
        return NESTED

    if parameter.refers_to:
        # It names something the ability chose, which is a question about the
        # card's own shape rather than a value anybody types.
        return WHOM if parameter.refers_to in (PLAYERS, CARDS) else NAMES

    if parameter.kind == UNCHECKED:
        return ""

    if parameter.kind == "true or false":
        return SWITCH

    if parameter.kind == "a whole number":
        return AMOUNT

    if parameter.values or parameter.domain_from:
        # A closed choice either way. That the list is only known once
        # something else is answered makes it no less a choice, and calling it
        # free text would invite anything at all.
        return WHICH

    return NAMES if parameter.kind in ("text", A_LIST) else OPEN


@dataclass(frozen=True, slots=True)
class ConditionShape:
    """
    What one condition takes, as far as a card file is concerned.

    Separate from ``EffectShape`` because the two are not the same question.
    An effect is asked for its result and may be handed a card, a player or a
    target — things only a game can supply. A condition is asked whether
    something is true and is handed a comparison: a number, an operator, the
    name of a counter. Almost all of that can be read before a game exists,
    which is why this has no shorthand key and no literal parameters. There is
    one spelling, and ``normalise`` turns every accepted form into it.
    """

    name: str

    params: Mapping[str, ParamShape] = field(
        default_factory=lambda: MappingProxyType({})
    )

    open_ended: bool = False
    """
    Whether whoever registered this condition declined to say what it takes.

    False for every condition the engine ships. True is not permission — it is
    an absence of information, and this layer refuses nothing it was not told
    about.
    """

    describes: str = ""
    """
    What this condition asks, in a person's words.
    """


PLAYERS = "players"
CARDS = "cards"
MIXED = "mixed"
PASSTHROUGH = "passthrough"
ANY_GROUP = "any"
VALUES = "values"
"""
The words a reference is described with.

``players`` and ``cards`` are the only two kinds the engine tells apart —
everything asking about a kind asks ``isinstance(x, PlayerState)`` — so
``cards`` means "an object on the board that is not a seat", which includes
the stack items that stand for cards.

``mixed`` is a target that hands back both. ``passthrough`` is one that hands
back whatever it was given. Neither can be judged, and neither is refused.

``any`` is a reference that does not care. ``values`` is a reference into the
other namespace entirely — what an ability stored, not what it chose.
"""


@dataclass(frozen=True, slots=True)
class TargetShape:
    """
    What one target takes, as far as a card file is concerned.

    Separate from the other two for the reason they are separate from each
    other: the questions differ. An effect may be handed a card or a player
    that only a game can supply. A condition is handed a comparison. A target
    is handed a description of what to look for — a deck, a role, a family, a
    number of options — and almost all of that can be read before a game
    exists.

    What cannot is a parameter that names a group the ability bound earlier.
    Those carry ``UNCHECKED``: answering would mean resolving an ability's
    alias graph, which is a question of its own and is not asked here.
    """

    name: str

    params: Mapping[str, ParamShape] = field(
        default_factory=lambda: MappingProxyType({})
    )

    open_ended: bool = False
    """
    Whether whoever registered this target declined to say what it takes.

    False for every target the engine ships. True is an absence of
    information, not permission.
    """

    describes: str = ""
    """
    What this target picks out, in a person's words.
    """

    yields: str = ""
    """
    What kind of thing this target hands back.

    One of ``players``, ``cards``, ``mixed`` or ``passthrough``; empty when
    whoever registered it did not say, which is not judged either way.
    """


@dataclass(frozen=True, slots=True)
class NodeShape:
    """
    What one piece of the DSL that is not an effect may be written with.

    An ability, a static, a control node. Unlike an effect or a target, these
    have no name inside them to look up — they *are* the structure — so what
    they accept is a closed set of keys, and a key outside it is a mistake
    rather than a field a later engine will read.

    Which is the opposite of the rule at the top level of a card, and
    deliberately: there, an unknown field is kept, because a set may carry an
    artist credit or something this engine has not learned yet. Inside the DSL
    there is nothing to be forward compatible with — the interpreter reads
    these keys and hands nothing else on.
    """

    name: str

    params: Mapping[str, ParamShape] = field(
        default_factory=lambda: MappingProxyType({})
    )

    bodies: tuple[str, ...] = ()
    """
    The keys this node keeps the things it does under, if it does anything.

    Empty for a node with no body — an ability, a static, `stop`. Otherwise a
    node with every one of these empty expands to nothing at all, which reads
    exactly like one that works and is not a card anybody meant to write.
    """


@dataclass(frozen=True, slots=True)
class Vocabulary:
    """
    Every name the engine answers to.
    """

    effects: frozenset[str] = frozenset()
    triggers: frozenset[str] = frozenset()
    conditions: frozenset[str] = frozenset()
    targets: frozenset[str] = frozenset()

    condition_shapes: Mapping[str, ConditionShape] = field(
        default_factory=lambda: MappingProxyType({})
    )
    """
    What each condition takes, on the same terms as ``shapes`` below.
    """

    target_shapes: Mapping[str, TargetShape] = field(
        default_factory=lambda: MappingProxyType({})
    )
    """
    What each target takes, on the same terms.
    """

    node_shapes: Mapping[str, NodeShape] = field(
        default_factory=lambda: MappingProxyType({})
    )
    """
    What an ability, a static and each control node may be written with.
    """

    trigger_scopes: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )
    """
    What an ability listening for each trigger listens to, when it does not say.

    An ability leaving its scope out does not get "no scope": it gets one the
    engine works out from the trigger, and for all but a handful of triggers
    that answer is the whole table. A card meaning "when *you* take damage" and
    written without a scope means "when anybody does", and nothing says so.

    So the derivation is published rather than left to be rediscovered. This is
    the engine's own answer for each trigger, not a second table — whoever
    builds a vocabulary asks the engine once and writes down what it said.
    """

    shapes: Mapping[str, EffectShape] = field(
        default_factory=lambda: MappingProxyType({})
    )
    """
    What each effect takes, when whoever built this vocabulary knew.

    Plain data, like everything else here, and for the same reason: the
    pipeline runs before a game exists and must never touch one. A vocabulary
    that names the effects but describes none of them still checks spelling,
    which is why the shapes are not counted by ``is_empty`` — calling such a
    vocabulary empty would turn off the checks it can still do.
    """

    @classmethod
    def of(
        cls,
        *,
        effects: Collection[str] = (),
        triggers: Collection[str] = (),
        conditions: Collection[str] = (),
        targets: Collection[str] = (),
        shapes: Mapping[str, EffectShape] | None = None,
        condition_shapes: Mapping[str, ConditionShape] | None = None,
        target_shapes: Mapping[str, TargetShape] | None = None,
        node_shapes: Mapping[str, NodeShape] | None = None,
        trigger_scopes: Mapping[str, str] | None = None,
    ) -> Vocabulary:
        """
        Build a vocabulary from any collections of names.
        """
        return cls(
            effects=frozenset(effects),
            triggers=frozenset(triggers),
            conditions=frozenset(conditions),
            targets=frozenset(targets),
            shapes=MappingProxyType(dict(shapes or {})),
            condition_shapes=MappingProxyType(dict(condition_shapes or {})),
            target_shapes=MappingProxyType(dict(target_shapes or {})),
            node_shapes=MappingProxyType(dict(node_shapes or {})),
            trigger_scopes=MappingProxyType(dict(trigger_scopes or {})),
        )

    def shape(self, effect: str) -> EffectShape | None:
        """
        What one effect takes, or ``None`` when this vocabulary does not say.
        """
        return self.shapes.get(effect)

    def condition_shape(self, condition: str) -> ConditionShape | None:
        """
        What one condition takes, or ``None`` when this vocabulary does not say.
        """
        return self.condition_shapes.get(condition)

    def node_shape(self, node: str) -> NodeShape | None:
        """
        What one DSL node may be written with, or ``None`` when unknown.
        """
        return self.node_shapes.get(node)

    def target_shape(self, target: str) -> TargetShape | None:
        """
        What one target takes, or ``None`` when this vocabulary does not say.
        """
        return self.target_shapes.get(target)

    @property
    def is_empty(self) -> bool:
        """
        True when nothing can be checked against this vocabulary.

        An empty vocabulary means schema validation only: structure is still
        enforced, meaning is not.
        """
        return not (self.effects or self.triggers or self.conditions or self.targets)
