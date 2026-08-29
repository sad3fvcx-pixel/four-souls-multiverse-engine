# src/fsme/effects/registry.py

"""
Registry of built-in effects for Four Souls Multiverse Engine.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from fsme.content.vocabulary import A_LIST, A_MAPPING

from .context import EffectContext
from .errors import EffectRegistrationError, UnknownEffectError

EffectHandler = Callable[..., Any]

GIVEN = frozenset({"ctx", "context", "targets"})
"""
The parameters the engine fills in, which no card writes.

Every effect is handed a context and its targets. Neither is something a card
says, so neither is something a card can get wrong.
"""


class ParamKind(StrEnum):
    """
    What a card may write for one parameter.

    Deliberately coarse. This is not a type system; it is the handful of
    distinctions somebody writing a card can actually get wrong, and each one
    has to be sayable in a sentence to a person who has never read any Python.
    """

    WHOLE = "a whole number"
    TEXT = "text"
    FLAG = "true or false"

    LIST = A_LIST
    """
    Several values rather than one.

    Never read off a signature — an effect keeping its own structured data
    annotates it ``Any``, because what is inside needs a game. This is the
    outer shape, said at registration beside the guard that enforces it.
    """

    MAPPING = A_MAPPING
    """
    Named values rather than one value. Said the same way and for the reason.
    """

    OPEN = "anything the engine can only judge during a game"
    """
    A parameter this layer deliberately does not check.

    ``Any`` on a handler means the effect takes a card, a player, or a shape
    that only means something once a board exists. It does **not** mean "accept
    whatever". The runtime guard stays exactly where it is and still raises;
    what this says is that load time is the wrong place to ask, because
    answering the question would need a game.
    """


_KINDS: Mapping[str, ParamKind] = MappingProxyType(
    {
        "int": ParamKind.WHOLE,
        "str": ParamKind.TEXT,
        "bool": ParamKind.FLAG,
    }
)


@dataclass(frozen=True, slots=True)
class ParamSpec:
    """
    One parameter of one effect, as a card is allowed to write it.
    """

    name: str
    kind: ParamKind

    required: bool = False
    """
    Whether a card has to give this one. Nearly none are: `gain_coins` with no
    amount gains one.
    """

    default: Any = None
    """
    What the effect does when a card leaves this out.

    Read off the signature like everything else here, and meaningful only when
    ``required`` is false. A form that cannot say what a blank box means is a
    form that makes people guess: "how many cents" left empty is one cent, not
    none, and nothing but the handler knows that.
    """

    nullable: bool = False
    """
    Whether the card may write ``null`` for it.

    True only where the effect's own annotation admits ``None``. Everywhere
    else a written ``null`` is a card that meant to leave the key out.
    """

    values: tuple[Any, ...] = ()
    """
    The values this parameter takes, when there are only a few.

    A type cannot catch ``{"deck": "spaghetti"}`` — text where text was wanted
    — and what is wrong with it is that there are four decks. Named at
    registration from the same constant the runtime checks against, so there is
    never a second list to keep in step.
    """

    least: int | None = None
    """
    The smallest number accepted, where there is a floor.
    """

    asks: str = ""
    """
    What to call this field when a person is filling it in.

    ``amount`` is cents on one effect and damage on another, so the words
    belong to the effect that takes it rather than to the word itself. Empty
    means nobody has said, and whoever is asking should fall back to the name.
    """

    role: str = ""
    """
    What kind of question this parameter is — see `content.vocabulary.ROLES`.

    Declared only where it cannot be worked out from the rest.
    """

    unless: str = ""
    """
    Another parameter that makes this one meaningless.
    """

    unless_when: tuple[Any, ...] = ()
    """
    The values of ``unless`` that actually make this one meaningless.

    Empty means any value at all. Named where the handler reads one particular
    value, because a form that greys out a field the effect would have read is
    as wrong as one that offers a field it will not.
    """

    refers_to: str = ""
    """
    What this parameter names, when it names a player or a card rather than
    carrying a value — ``players`` or ``cards``.

    Declared because nothing else can tell: a handler taking ``to: Any`` and
    one taking ``card: Any`` look the same, and one is a seat number a card
    writes and the other is a card the engine hands over.
    """

    def wants(self) -> str:
        """
        What this parameter takes, in the words an error message needs.
        """
        if self.values:
            return " or ".join(repr(value) for value in self.values)

        if self.least is not None:
            return f"{self.kind} of at least {self.least}"

        return str(self.kind)


def parameters_of(handler: EffectHandler) -> dict[str, ParamSpec]:
    """
    Read an effect's parameters off the function that implements it.

    Derived, never declared, and that is the whole of why it is safe to
    maintain: a second table of what each effect takes is a second table that
    drifts from the effects, and a signature cannot drift from its own
    function.

    An effect written to take only ``**kwargs`` — two dozen do, because they
    work on their targets — describes no parameters. That is a true statement
    about it, and `takes_anything` is what stops it being read as "this effect
    accepts nothing".
    """
    try:
        signature = inspect.signature(handler)
    except (TypeError, ValueError):  # pragma: no cover - unreachable today
        return {}

    described: dict[str, ParamSpec] = {}

    for name, parameter in signature.parameters.items():
        if name in GIVEN:
            continue

        if parameter.kind in (parameter.VAR_KEYWORD, parameter.VAR_POSITIONAL):
            continue

        written = _annotation_of(parameter)

        described[name] = ParamSpec(
            name=name,
            kind=_KINDS.get(written.removesuffix(" | None"), ParamKind.OPEN),
            required=parameter.default is inspect.Parameter.empty,
            default=(
                None
                if parameter.default is inspect.Parameter.empty
                else parameter.default
            ),
            nullable=written.endswith("| None"),
        )

    return described


def _annotation_of(parameter: inspect.Parameter) -> str:
    """
    An annotation as the plain string it was written as.
    """
    if parameter.annotation is inspect.Parameter.empty:
        return ""

    return str(
        getattr(parameter.annotation, "__name__", None) or parameter.annotation
    )


def takes_anything(handler: EffectHandler) -> bool:
    """
    Whether this effect accepts keywords it has not named.

    An effect with ``**kwargs`` has not finished saying what it takes, so
    nothing may be refused on its behalf.
    """
    try:
        signature = inspect.signature(handler)
    except (TypeError, ValueError):  # pragma: no cover - unreachable today
        return True

    return any(
        parameter.kind is parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )


@dataclass(frozen=True, slots=True)
class EffectSpec:
    """
    Immutable description of one registered effect.
    """

    name: str
    handler: EffectHandler

    uses_stack: bool = False
    needs_target: bool = False

    hits: str = ""
    """
    The kind of thing this effect's targets must be.

    ``needs_target`` says an effect acts on something; this says on *what*.
    ``'steal_soul'`` takes a soul from a player and cannot take one from a
    treasure, and until this existed the only statement of that fact was the
    ``isinstance`` check inside the handler — where no form, no checker and no
    author could read it, so all three offered the treasure and the game threw.

    One of the words the reference vocabulary already uses — ``players`` or
    ``cards`` — or empty for an effect that acts on anything handed to it.
    Conservative on purpose: an effect narrower than either word (only stack
    objects, only things with hit points) says the wider one it belongs to, so
    that nothing correct is ever refused.
    """

    replacing: bool = False
    """
    Whether this effect only works inside a replacement ability.

    The sibling of ``hits``. An ability marked ``replacement`` is handed the
    event that is about to happen so it can edit it; three effects reach for
    that event and have nothing to reach for anywhere else. The handlers say so
    by raising, which is the right answer given too late — the form offered
    them on an ordinary ability and the checker agreed, so a card that could
    never work was written, saved and only refused when somebody played it.
    """

    primary: str | None = None
    """
    Parameter filled by the DSL shorthand form.

    ``{"gain_coins": 3}`` means ``amount=3`` while ``{"draw_loot": 2}`` means
    ``count=2``; the effect declares which, so the interpreter never guesses.
    """

    stores: str | None = None
    """
    Ability variable that receives this effect's return value.

    ``roll_dice`` stores ``dice``, which is what lets a later condition read
    ``dice_equals`` without the executor special-casing dice.
    """

    literal: frozenset[str] = frozenset()
    """
    Parameters handed to the effect exactly as the card wrote them.

    Most parameters may name a value the ability learns while running —
    ``{"amount": {"from": "dice"}}`` — and the executor fills those in. An
    effect whose parameter is itself structured data has to say so, or a card
    that promises to change how much loot is drawn would have its ``count``
    read as a question about somebody's hand.
    """

    description: str = ""

    params: Mapping[str, ParamSpec] = field(default_factory=dict)
    """
    What a card may write for this effect, read off the handler.
    """

    open_ended: bool = False
    """
    Whether the handler accepts keywords it has not named.

    True for the two dozen effects that take only their targets. Nothing may be
    refused for them, because they would accept it.
    """


class EffectRegistry:
    """
    Name to implementation mapping for every effect the engine knows.

    Registration is permanent: DEVELOPMENT_GUIDELINES.md requires definitions
    to be immutable once registered, so re-registering a name is an error
    rather than a silent override. A card that needs new behaviour extends the
    registry with a new effect; it never replaces an existing one.
    """

    def __init__(self) -> None:
        self._specs: dict[str, EffectSpec] = {}

    def __contains__(self, name: object) -> bool:
        return name in self._specs

    def __len__(self) -> int:
        return len(self._specs)

    def register(
        self,
        name: str,
        handler: EffectHandler,
        *,
        uses_stack: bool = False,
        needs_target: bool = False,
        hits: str = "",
        replacing: bool = False,
        primary: str | None = None,
        stores: str | None = None,
        literal: frozenset[str] | tuple[str, ...] = (),
        description: str = "",
        values: Mapping[str, Sequence[Any]] | None = None,
        least: Mapping[str, int] | None = None,
        asks: Mapping[str, str] | None = None,
        needs: Sequence[str] = (),
        roles: Mapping[str, str] | None = None,
        picks: Mapping[str, str] | None = None,
        holds: Mapping[str, str] | None = None,
        unless: Mapping[str, str] | None = None,
        unless_when: Mapping[str, Sequence[Any]] | None = None,
    ) -> EffectSpec:
        """
        Register an effect implementation.

        ``values`` and ``least`` name the domains a type cannot express — which
        decks there are, which positions, the counts that cannot go negative.
        They belong here, beside ``primary`` and ``literal``, because this is
        already where the facts about an effect that are not in its signature
        are written down; and they should be given the same constant the
        runtime guard checks against, so that there is one list and not two.
        """
        if not name:
            raise EffectRegistrationError("effect name must not be empty")

        if name in self._specs:
            raise EffectRegistrationError(
                f"effect '{name}' is already registered"
            )

        described = parameters_of(handler)

        for parameter, allowed in (values or {}).items():
            described[parameter] = _narrow(described, parameter, name, values=allowed)

        for parameter, floor in (least or {}).items():
            described[parameter] = _narrow(described, parameter, name, least=floor)

        for parameter in needs:
            # A parameter the handler raises on when it is missing. Its
            # signature gives it a default — every effect parameter has one —
            # so nothing but this can tell a form that leaving it blank makes
            # a card that will not run.
            described[parameter] = _narrow(
                described, parameter, name, required=True
            )

        for parameter, role in (roles or {}).items():
            # Only where it cannot be worked out. A flag is a switch, a number
            # is an amount, a closed set is a choice — those need nobody to say
            # so. What needs saying is whether something the pipeline cannot
            # judge is a card the engine hands over or a word somebody types.
            described[parameter] = _narrow(
                described, parameter, name, role=role
            )

        for parameter, shaped in (holds or {}).items():
            # The outer shape of a parameter the effect keeps as written. What
            # is inside it needs a game; that it is a list, or a set of named
            # values, does not — and the handler raises on anything else, which
            # makes load time the right place to say so.
            described[parameter] = _narrow(
                described, parameter, name, kind=shaped
            )

        for parameter, names in (picks or {}).items():
            # What a parameter naming somebody names. The role follows from it
            # — a parameter that names a player is not a box anybody types in —
            # so this is said once and `role` is left to work itself out.
            described[parameter] = _narrow(
                described, parameter, name, refers_to=names
            )

        for parameter, other in (unless or {}).items():
            described[parameter] = _narrow(
                described, parameter, name, unless=other
            )

        for parameter, moot in (unless_when or {}).items():
            described[parameter] = _narrow(
                described, parameter, name, unless_when=tuple(moot)
            )

        for parameter, question in (asks or {}).items():
            # What to call this field when a person is filling it in. `amount`
            # is cents on one effect and damage on another, so the words
            # belong to the effect rather than to the word.
            described[parameter] = _narrow(
                described, parameter, name, asks=question
            )

        spec = EffectSpec(
            name=name,
            handler=handler,
            uses_stack=uses_stack,
            needs_target=needs_target,
            hits=hits,
            replacing=replacing,
            primary=primary,
            stores=stores,
            literal=frozenset(literal),
            description=description,
            params=MappingProxyType(described),
            open_ended=takes_anything(handler),
        )

        self._specs[name] = spec

        return spec

    def effect(
        self,
        name: str,
        *,
        uses_stack: bool = False,
        needs_target: bool = False,
        primary: str | None = None,
        stores: str | None = None,
        literal: frozenset[str] | tuple[str, ...] = (),
        description: str = "",
        values: Mapping[str, Sequence[Any]] | None = None,
        least: Mapping[str, int] | None = None,
    ) -> Callable[[EffectHandler], EffectHandler]:
        """
        Decorator form of :meth:`register`.
        """

        def decorate(handler: EffectHandler) -> EffectHandler:
            self.register(
                name,
                handler,
                uses_stack=uses_stack,
                needs_target=needs_target,
                primary=primary,
                stores=stores,
                literal=literal,
                description=description,
                values=values,
                least=least,
            )
            return handler

        return decorate

    def spec(self, name: str) -> EffectSpec:
        """
        Return the specification of a registered effect.
        """
        try:
            return self._specs[name]
        except KeyError:
            raise UnknownEffectError(f"unknown effect '{name}'") from None

    def execute(
        self,
        name: str,
        context: EffectContext,
        targets: Sequence[Any],
        **params: Any,
    ) -> Any:
        """
        Run a registered effect.
        """
        return self.spec(name).handler(context, targets, **params)

    def names(self) -> frozenset[str]:
        """
        Return every registered effect name.
        """
        return frozenset(self._specs)


def _narrow(
    described: Mapping[str, ParamSpec],
    parameter: str,
    effect: str,
    *,
    values: Sequence[Any] | None = None,
    least: int | None = None,
    asks: str | None = None,
    required: bool | None = None,
    kind: str | None = None,
    role: str | None = None,
    unless: str | None = None,
    unless_when: tuple[Any, ...] | None = None,
    refers_to: str | None = None,
) -> ParamSpec:
    """
    Add a domain, a floor or a label to a parameter the handler declares.

    Refused for a parameter the effect does not take, because a domain named
    for a parameter that does not exist is a typo in the engine, and the moment
    to find one of those is while it is being written.

    Additive on purpose: each call keeps everything the parameter already had,
    so an effect may say two of these three things about one parameter and get
    both.
    """
    known = described.get(parameter)

    if known is None:
        raise EffectRegistrationError(
            f"effect '{effect}' has no parameter '{parameter}' to constrain"
        )

    return replace(
        known,
        kind=ParamKind(kind) if kind is not None else known.kind,
        values=tuple(values) if values is not None else known.values,
        least=least if least is not None else known.least,
        asks=asks if asks is not None else known.asks,
        required=required if required is not None else known.required,
        role=role if role is not None else known.role,
        unless=unless if unless is not None else known.unless,
        unless_when=(
            unless_when if unless_when is not None else known.unless_when
        ),
        refers_to=refers_to if refers_to is not None else known.refers_to,
    )


def builtin_registry() -> EffectRegistry:
    """
    Build a registry populated with the engine's built-in effects.
    """
    from .builtin import register_builtin_effects

    registry = EffectRegistry()
    register_builtin_effects(registry)

    return registry
