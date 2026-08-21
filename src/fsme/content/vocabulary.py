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

UNCHECKED = "anything the engine can only judge during a game"
"""
The kind given to a parameter this layer deliberately does not check.

It means the effect takes a card, a player, or a shape that only means
something once a board exists — **not** that anything is acceptable. The
runtime guard stays where it is and still raises; what this says is that load
time is the wrong place to ask, because answering would need a game.
"""


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

    def wants(self) -> str:
        """
        What this parameter takes, in the words an error message needs.
        """
        if self.values:
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

    yields: str = ""
    """
    What kind of thing this target hands back.

    One of ``players``, ``cards``, ``mixed`` or ``passthrough``; empty when
    whoever registered it did not say, which is not judged either way.
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
