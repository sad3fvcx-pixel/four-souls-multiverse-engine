# src/fsme/cards/references.py

"""
The names an ability gives things, and the places it uses them again.

"Choose a player at random — that player destroys an item they control" is two
steps, and the second reads the first. An ability writes that down by binding a
name and then naming it, and five ways of getting it wrong all used to load
cleanly and then play a game other than the one on the card: a name read before
the target that binds it, the same name bound twice, a name that was never
bound at all, a name of the wrong kind, and a name reached for across a
boundary it cannot cross.

None of it needs a board. Whether a group turns out to be *empty* does — and
that is not a mistake but a rule, so nothing here asks.

Plain data throughout. This runs before a game exists and never touches one:
what it knows about targets arrives as shapes, the same way every other check
in this package gets what it knows.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

from .suggest import did_you_mean

REPLACES_THE_EVENT = "replacement"
"""
Which of an ability's own answers says it was handed the event.

Declared here because here is where it is enforced: an effect that reaches for
the event an ability was handed is refused inside an ability that was not. The
description of the language points at this name through ``ParamShape.allows``,
so the rule and the account of the rule cannot come apart — and the account is
all anything offering effects has to go on. Until it existed, the only way to
find this answer was to know what it is called.
"""

GROUP_READERS = ("of", "chooser", "exclude")
"""
Parameters on a target specification that name a group instead of carrying a
value. Which kind of group each wants is the target's business, not the word's:
``of`` names players on ``target_loot``, cards on ``holder``, and anything at
all on ``group``.
"""

NEW_SCOPE = ("watch_for", "promise")
"""
Effects whose contents run later, against a context of their own.

The runtime builds a fresh ``AbilityContext`` for a watcher when its event
arrives, so nothing this ability bound is there to be found. A name reached for
across that boundary is not a late binding; it is an empty one.
"""

CONDITION_KEYS = ("conditions", "if")
"""
Where conditions are kept. An ability writes ``conditions``; a control node
that only sometimes runs writes ``if``, and the interpreter reads either.
"""

BRANCHES = ("then", "else", "may", "choose", "modes", "effects")
"""
Keys holding effects that may or may not run.

Their contents share the context at run time, but *whether they ran* is not a
fact about the text. So a name bound inside one is visible inside it and after
it there, and not outside — which is the strictest reading, and the one every
shipped card already obeys.
"""

PLAYERS = "players"
CARDS = "cards"
VALUES = "values"

_NOT_A_VALUE = ("targets", "target", "for_each", "store", "effect")
"""
Keys of an effect node that are not one of its parameters.

The interpreter takes these off the node before the effect sees it, so nothing
inside them is a value being worked out.
"""
MIXED = "mixed"
PASSTHROUGH = "passthrough"

UNPROVABLE = (MIXED, PASSTHROUGH, "")
"""
What a target may hand back when nothing can be said about it.

A target that returns both kinds, or whatever it was given, or one whose
author did not say. None of the three is refused: a check that cannot be
proved is skipped rather than guessed.
"""


def validate_references(
    card: Mapping[str, Any],
    *,
    shapes: Mapping[str, Any] | None,
    known_targets: Collection[str] | None,
    card_id: str,
    effects: Mapping[str, Any] | None = None,
    worked_out: Any = None,
) -> list[str]:
    """
    Check every name an ability uses against the names it binds.
    """
    if not shapes:
        return []

    errors: list[str] = []

    for where, ability in _abilities(card):
        errors.extend(
            _Ability(
                shapes=shapes,
                effects=effects or {},
                targets=frozenset(known_targets or ()),
                card_id=card_id,
                worked_out=worked_out,
            ).check(ability, where)
        )

    return errors


def _abilities(card: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    found: list[tuple[str, Mapping[str, Any]]] = []

    for key in ("abilities", "statics"):
        group = card.get(key, ())

        if not isinstance(group, (list, tuple)):
            continue

        found.extend(
            (f"{key}[{index}]", item)
            for index, item in enumerate(group)
            if isinstance(item, Mapping)
        )

    return found


class _Ability:
    """
    One ability's names, while they are being worked out.

    Two namespaces, kept apart on purpose. Groups hold the objects an ability
    chose and are bound by ``as``; values hold what it stored and are bound by
    ``store``. ``of`` reads a group on a target and a value on ``values_equal``,
    which is the whole reason these are not one dictionary.
    """

    def __init__(
        self,
        *,
        shapes: Mapping[str, Any],
        targets: frozenset[str],
        card_id: str,
        effects: Mapping[str, Any] | None = None,
        worked_out: Any = None,
    ) -> None:
        self._shapes = shapes
        self._effects = effects or {}
        # Which keys of a worked-out value name something, and what kind of
        # thing each names. Read off the shape rather than listed here: the
        # executor resolves exactly these, and a list would be a second copy.
        self._heads = {
            name: parameter
            for name, parameter in getattr(worked_out, "params", {}).items()
            if parameter.refers_to
        }
        self._targets = targets
        self._card = card_id
        self._errors: list[str] = []
        self._somewhere: frozenset[str] = frozenset()
        self._replacing = False

    # ------------------------------------------------------------------

    def check(self, ability: Mapping[str, Any], where: str) -> list[str]:
        groups: dict[str, str] = {}
        values: set[str] = set()

        # Every name bound anywhere in this ability, gathered before anything
        # is checked. It settles nothing on its own — a name bound in a branch
        # that may not run is still not visible outside it — but it is the
        # difference between "you have not bound that" and "you have bound
        # that, further down", which are different mistakes to go and fix.
        self._somewhere = _bound_anywhere(ability)
        # Whether this ability is handed the event that is about to happen.
        # Read off the card, because it is the card that says so, and kept for
        # the whole walk: an effect nested three deep is in the same ability.
        self._replacing = ability.get(REPLACES_THE_EVENT) is True

        # An ability's own conditions are asked before its effects run, so
        # they cannot see anything those effects store. Checking them first,
        # against nothing, is the same order the runtime uses.
        self._conditions(
            ability.get("conditions", ()) or (), set(), f"{where}.conditions"
        )

        for index, spec in enumerate(ability.get("targets", ()) or ()):
            self._one_target(spec, groups, f"{where}.targets[{index}]")

        self._walk(ability.get("effects", ()) or (), groups, values, f"{where}.effects")

        return self._errors

    # ------------------------------------------------------------------

    def _one_target(
        self,
        spec: Any,
        groups: dict[str, str],
        path: str,
    ) -> None:
        """
        Read one target specification: what it uses, then what it binds.

        In that order, because a specification cannot name itself.
        """
        name, params = _call(spec)

        if name is None:
            return

        shape = self._shapes.get(name)

        if shape is not None:
            for key, parameter in shape.params.items():
                if not parameter.refers_to or parameter.refers_to == "values":
                    continue

                for named in _names(params.get(key)):
                    self._read_group(named, groups, parameter.refers_to, f"{path}.{key}")

        bound = str(params.get("as", name))

        if bound in groups:
            self._say(f"{path}: '{bound}' is already bound by another target")

            return

        groups[bound] = shape.yields if shape is not None else ""

    def _read_group(
        self,
        named: str,
        groups: dict[str, str],
        wanted: str,
        path: str,
    ) -> None:
        """
        Check one name used where a group belongs.
        """
        if named in self._targets:
            # Naming a target where a group belongs is not a reference at all:
            # it is asking for that target again. `{"of": "all_players"}` is
            # the case the engine itself spells out.
            return

        if named not in groups:
            self._say(f"{path}: {self._unknown(named, groups)}")

            return

        if wanted == "any":
            return

        gives = groups[named]

        if gives in UNPROVABLE or wanted == gives:
            return

        self._say(
            f"{path}: '{named}' holds {gives}, and this wants {wanted}"
        )

    # ------------------------------------------------------------------

    def _walk(
        self,
        node: Any,
        groups: dict[str, str],
        values: set[str],
        path: str,
    ) -> None:
        if isinstance(node, (list, tuple)):
            for index, item in enumerate(node):
                self._walk(item, groups, values, f"{path}[{index}]")

            return

        if not isinstance(node, Mapping):
            return

        if _head(node) in NEW_SCOPE:
            # A fresh context, so a fresh pair of namespaces. What is bound out
            # here will not be there when this runs.
            self._walk(node.get("effects", ()) or (), {}, set(), f"{path}.effects")
            self._conditions(node.get("conditions", ()) or (), set(), f"{path}.conditions")

            return

        for index, spec in enumerate(node.get("targets", ()) or ()):
            self._one_target(spec, groups, f"{path}.targets[{index}]")

        # What this effect acts on, so that a card aiming it at the wrong kind
        # of thing is refused here rather than when somebody plays it.
        wanted = str(getattr(self._effects.get(_head(node)), "hits", "") or "")

        self._only_replacing(_head(node), path)

        self._aimed(node.get("target"), groups, f"{path}.target", wanted)
        self._aimed(node.get("for_each"), groups, f"{path}.for_each")

        # Before anything this node stores, because a value is worked out
        # before the effect runs and so cannot read what that effect keeps.
        self._worked_out(node, groups, values, path)

        stored = node.get("store")

        if isinstance(stored, str):
            values.add(stored)

        # And the name an effect keeps its own result under. `roll_dice` puts
        # the number rolled into the ability's values without being asked to,
        # which is how "if the roll was a 6" reads it back — and the effect is
        # the only thing that knows, so the effect is what is asked.
        for kept in self._keeps(node):
            values.add(kept)

        for key, value in node.items():
            if key in ("targets", "target", "for_each", "store"):
                continue

            if key in CONDITION_KEYS:
                # `if` is where a control node keeps its conditions, and the
                # interpreter reads either spelling.
                self._conditions(value, values, f"{path}.{key}")
            elif key in BRANCHES:
                # A branch keeps what it binds: whether it ran is not a fact
                # about the text.
                self._walk(value, dict(groups), set(values), f"{path}.{key}")
            elif isinstance(value, (list, tuple, Mapping)):
                self._walk(value, groups, values, f"{path}.{key}")

    def _worked_out(
        self,
        node: Mapping[str, Any],
        groups: dict[str, str],
        values: set[str],
        path: str,
    ) -> None:
        """
        The names hidden inside a value the ability works out while it runs.

        ``{"amount": {"from": "dice"}}`` is a card saying "as much as the
        roll", and the name in it is a reference exactly as the one in
        ``values_equal`` is — the same two namespaces, the same ordering rule,
        the same ability boundary. It was the only place a reference was never
        looked at, so a misspelling read as nothing at all and the card said so
        to nobody.

        Which keys are references and what each one names is the ``worked_out``
        shape's own answer. Which parameters may hold one is the effect's:
        ``literal`` marks the ones handed over exactly as written, and those
        are the effect's own data rather than a value to resolve — the same
        line the executor draws.
        """
        if not self._heads:
            return

        shape = self._effects.get(_head(node))
        literal: frozenset[str] = getattr(shape, "literal", frozenset())

        for key, value in node.items():
            if key in _NOT_A_VALUE or key in literal:
                continue

            if not isinstance(value, Mapping):
                continue

            for head, parameter in self._heads.items():
                if head not in value:
                    continue

                where = f"{path}.{key}.{head}"

                for named in _names(value[head]):
                    if parameter.refers_to == VALUES:
                        if named not in values:
                            self._say(
                                f"{where}: '{named}' is not a value this "
                                f"ability stores{did_you_mean(named, values)}"
                            )
                    else:
                        self._read_group(
                            named, groups, parameter.refers_to, where
                        )

    def _keeps(self, node: Mapping[str, Any]) -> list[str]:
        """
        The names an effect keeps its own result under.

        `roll_dice` puts the number rolled into the ability's values without
        being asked to, which is how "if the roll was a 6" reads it back. The
        effect is the only thing that knows, so the effect is what is asked —
        under either spelling a card may call it by.
        """
        called = node.get("effect")
        names = [str(called)] if isinstance(called, str) else [
            str(key) for key in node if key in self._effects
        ]

        return [
            str(kept)
            for name in names
            if (kept := getattr(self._effects.get(name), "stores", ""))
        ]

    def _aimed(
        self,
        spec: Any,
        groups: dict[str, str],
        path: str,
        wanted: str = "",
    ) -> None:
        """
        An effect pointing at something, by name or by specification.
        """
        if isinstance(spec, str):
            if spec.startswith("__"):
                # The interpreter's own bindings, made while a loop runs.
                return

            if spec not in self._targets and spec not in groups:
                self._say(f"{path}: {self._unknown(spec, groups)}")

                return

            self._acts_on(spec, groups, path, wanted)

            return

        if isinstance(spec, Mapping):
            self._one_target(spec, groups, path)

            named, _ = _call(spec)

            if isinstance(named, str):
                self._acts_on(named, groups, path, wanted)

    def _only_replacing(self, named: Any, path: str) -> None:
        """
        Whether an effect that edits an event is somewhere there is one.

        The sibling of ``_acts_on``. Three effects reach for the event an
        ability was handed, and outside a replacement ability there is nothing
        to reach for — which the handlers said by raising, to somebody who had
        already written and saved the card.
        """
        if self._replacing:
            return

        if not getattr(self._effects.get(named), "replacing", False):
            return

        self._say(
            f"{path}: '{named}' edits the event an ability is handed, and this"
            " ability is not a replacement"
        )

    def _acts_on(
        self,
        named: str,
        groups: Mapping[str, str],
        path: str,
        wanted: str,
    ) -> None:
        """
        Whether what an effect is aimed at is the kind of thing it acts on.

        Both halves were already here and never put together: a target says
        what it hands back and an effect now says what it takes. Nothing is
        refused where either is silent — a target that hands back both kinds,
        or whatever it was given, is a question only a game can answer.
        """
        if not wanted:
            return

        shape = self._shapes.get(named)
        gives = shape.yields if shape is not None else groups.get(named, "")

        if gives in UNPROVABLE or gives == wanted:
            return

        self._say(f"{path}: this acts on {wanted} and is aimed at {gives}")

    # ------------------------------------------------------------------

    def _conditions(self, nodes: Any, values: set[str], path: str) -> None:
        """
        The other namespace.

        Only one condition reads it — ``values_equal`` compares things an
        ability stored — and a name it cannot find was never stored.
        """
        if isinstance(nodes, Mapping):
            nodes = [nodes]

        if not isinstance(nodes, (list, tuple)):
            return

        for index, node in enumerate(nodes):
            name, params = _condition(node)

            if name in ("and", "or", "not"):
                self._conditions(params.get("of", ()), values, f"{path}[{index}].{name}")

                continue

            if name != "values_equal":
                continue

            for named in _names(params.get("of")):
                if named not in values:
                    self._say(
                        f"{path}[{index}]: '{named}' is not a value this "
                        f"ability stores{did_you_mean(named, values)}"
                    )

    def _unknown(self, named: str, groups: Mapping[str, str]) -> str:
        """
        Say which of the three things went wrong with a name.
        """
        if named in self._somewhere:
            return (
                f"'{named}' is bound, but not where this can see it — a name "
                f"is visible after the target that binds it, and only inside "
                f"the branch that bound it"
            )

        return (
            f"'{named}' is not a group this ability binds"
            f"{did_you_mean(named, groups)}"
        )

    def _say(self, message: str) -> None:
        self._errors.append(f"{self._card}: {message}")


def _head(node: Mapping[str, Any]) -> str:
    """
    The effect a node names, however it was spelled.
    """
    named = node.get("effect")

    if isinstance(named, str):
        return named

    for key in node:
        if key in NEW_SCOPE:
            return str(key)

    return ""


def _names(value: Any) -> list[str]:
    """
    One name or several, as a card is allowed to write either.
    """
    if isinstance(value, str):
        return [value]

    if isinstance(value, (list, tuple)):
        return [item for item in value if isinstance(item, str)]

    return []


def _call(spec: Any) -> tuple[str | None, dict[str, Any]]:
    """
    A target specification, reduced to a name and parameters.
    """
    if isinstance(spec, str):
        return spec, {}

    if not isinstance(spec, Mapping):
        return None, {}

    if "target" in spec:
        return (
            str(spec["target"]),
            {key: value for key, value in spec.items() if key != "target"},
        )

    if len(spec) != 1:
        return None, {}

    name, value = next(iter(spec.items()))

    return str(name), dict(value) if isinstance(value, Mapping) else {}


def _condition(node: Any) -> tuple[str, dict[str, Any]]:
    """
    A condition node, reduced the same way.
    """
    if isinstance(node, str):
        return node, {}

    if not isinstance(node, Mapping):
        return "", {}

    if "condition" in node:
        return (
            str(node["condition"]),
            {key: value for key, value in node.items() if key != "condition"},
        )

    if len(node) != 1:
        return "", {}

    name, value = next(iter(node.items()))

    if name in ("and", "or", "not"):
        return str(name), {"of": value if isinstance(value, (list, tuple)) else [value]}

    return str(name), dict(value) if isinstance(value, Mapping) else {"value": value}


def _bound_anywhere(node: Any) -> frozenset[str]:
    """
    Every group name an ability binds, wherever it binds it.

    Used only to choose the wording of a complaint, never to accept one: a
    name bound somewhere unreachable is still unreachable.
    """
    found: set[str] = set()

    def walk(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, value in item.items():
                if key == "targets" and isinstance(value, (list, tuple)):
                    for spec in value:
                        name, params = _call(spec)

                        if name is not None:
                            found.add(str(params.get("as", name)))
                elif key == "target" and isinstance(value, Mapping):
                    name, params = _call(value)

                    if name is not None:
                        found.add(str(params.get("as", name)))
                else:
                    walk(value)
        elif isinstance(item, (list, tuple)):
            for value in item:
                walk(value)

    walk(node)

    return frozenset(found)
