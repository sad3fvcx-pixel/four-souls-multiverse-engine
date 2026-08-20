# src/fsme/cards/validator.py

"""
Card content validation for Four Souls Multiverse Engine.

Validation happens before gameplay: ENGINE_INVARIANTS.md requires that invalid
content never reaches GameState, so the loader rejects a whole file rather than
letting a half-valid card into a game.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from difflib import get_close_matches
from typing import Any

from .types import CardType

REQUIRED_FIELDS = ("id", "name", "type", "expansion", "abilities")

_OPTIONAL_INT_FIELDS = ("health", "attack", "roll", "cost", "souls")


def validate_card(
    data: Any,
    *,
    known_effects: Collection[str] | None = None,
    known_triggers: Collection[str] | None = None,
    known_conditions: Collection[str] | None = None,
    known_targets: Collection[str] | None = None,
    shapes: Mapping[str, Any] | None = None,
) -> list[str]:
    """
    Return every problem found in one raw card.

    An empty list means the card is loadable. Effect and trigger vocabularies
    are passed in as plain names so that content validation stays independent
    of the effect implementations themselves.

    ``shapes`` says what each effect *takes*, in the same spirit and under the
    same rule: plain data, handed over by whoever owns a live engine, never
    imported from one. Without it the names are checked and the arguments are
    not — which is what a caller with no engine gets, and is exactly what
    happened to every card until this existed.
    """
    errors: list[str] = []

    if not isinstance(data, Mapping):
        return [f"card must be an object, got {type(data).__name__}"]

    card_id = data.get("id", "<no id>")

    for field_name in REQUIRED_FIELDS:
        if field_name not in data:
            errors.append(f"{card_id}: missing required field '{field_name}'")

    if "type" in data:
        try:
            CardType(data["type"])
        except ValueError:
            errors.append(f"{card_id}: unknown card type '{data['type']}'")

    for field_name in _OPTIONAL_INT_FIELDS:
        value = data.get(field_name)

        if value is not None and not isinstance(value, int):
            errors.append(
                f"{card_id}: field '{field_name}' must be an integer"
            )

    rewards = data.get("rewards")

    if rewards is not None:
        if not isinstance(rewards, Mapping):
            errors.append(f"{card_id}: 'rewards' must be an object")
        else:
            for key, value in rewards.items():
                if not isinstance(value, int):
                    errors.append(
                        f"{card_id}: reward '{key}' must be an integer"
                    )

    abilities = data.get("abilities", ())

    if not isinstance(abilities, (list, tuple)):
        errors.append(f"{card_id}: 'abilities' must be a list")
        return errors

    for index, ability in enumerate(abilities):
        errors.extend(
            _validate_ability(
                ability,
                card_id=str(card_id),
                index=index,
                known_effects=known_effects,
                known_triggers=known_triggers,
                known_conditions=known_conditions,
                known_targets=known_targets,
                shapes=shapes,
            )
        )

    return errors


def _validate_ability(
    ability: Any,
    *,
    card_id: str,
    index: int,
    known_effects: Collection[str] | None,
    known_triggers: Collection[str] | None,
    known_conditions: Collection[str] | None = None,
    known_targets: Collection[str] | None = None,
    shapes: Mapping[str, Any] | None = None,
) -> list[str]:
    location = f"{card_id}: ability {index}"

    if not isinstance(ability, Mapping):
        return [f"{location}: must be an object"]

    errors: list[str] = []

    trigger = ability.get("trigger")

    if not trigger:
        errors.append(f"{location}: missing 'trigger'")
    elif known_triggers is not None and trigger not in known_triggers:
        errors.append(
            f"{location}: unknown trigger '{trigger}'"
            f"{did_you_mean(str(trigger), known_triggers)}"
        )

    for key in ("conditions", "targets", "effects"):
        value = ability.get(key, ())

        if not isinstance(value, (list, tuple)):
            errors.append(f"{location}: '{key}' must be a list")

    effects = ability.get("effects", ())

    if isinstance(effects, (list, tuple)):
        if not effects:
            errors.append(f"{location}: needs at least one effect")

        if known_effects is not None:
            for name in _effect_names(effects):
                if name not in known_effects and name not in _CONTROL_NAMES:
                    errors.append(
                        f"{location}: unknown effect '{name}'"
                        f"{did_you_mean(name, known_effects)}"
                    )

    conditions = ability.get("conditions", ())

    if known_conditions is not None and isinstance(conditions, (list, tuple)):
        for name in _node_names(conditions, _BOOLEAN_NAMES):
            if name not in known_conditions and name not in _BOOLEAN_NAMES:
                errors.append(
                    f"{location}: unknown condition '{name}'"
                    f"{did_you_mean(name, known_conditions)}"
                )

    if shapes and isinstance(effects, (list, tuple)):
        errors.extend(
            _validate_arguments(effects, shapes=shapes, location=location)
        )

    if known_targets is not None:
        declared = _declared_target_names(ability) | _effect_aliases(
            ability.get("effects", ())
        )

        for name in _target_names(ability):
            if name not in known_targets and name not in declared:
                errors.append(
                    f"{location}: unknown target '{name}'"
                    f"{did_you_mean(name, known_targets)}"
                )

    return errors


DYNAMIC_HEADS = frozenset(
    {"from", "count", "from_event", "last_result", "player_of"}
)
"""
The five ways a card names a number it cannot know when it is written.

``{"amount": {"from": "dice"}}`` is a card saying "as much as the roll". The
executor knows these five and hands anything else straight to the effect, so a
misspelled one — ``{"frmo": "dice"}`` — is not a rejected typo but a dictionary
arriving where a number was expected. That is the mistake this set exists to
catch.
"""

WRITTEN_BY_THE_ENGINE = frozenset({"effect", "target", "targets", "store"})
"""
Keys the interpreter takes out of a node before the effect ever sees it.

Exactly these four, and the list has to match `runtime.interpreter.normalise`
and `_operation`: anything else written beside an effect is handed to it as a
parameter, so anything else is the card's to get right.
"""

WHOLE = "a whole number"
TEXT = "text"
FLAG = "true or false"


def _validate_arguments(
    nodes: Any,
    *,
    shapes: Mapping[str, Any],
    location: str,
    path: str = "effects",
) -> list[str]:
    """
    Check what a card gives each effect against what that effect takes.

    Walks the same shape `_effect_names` does, and for the same reason keeps a
    path while it goes: an author with a mistake three branches deep needs to
    be told where it is, not merely that it exists.
    """
    errors: list[str] = []

    for position, node in enumerate(nodes):
        here = f"{path}[{position}]"

        if not isinstance(node, Mapping):
            continue

        name, params = _effect_call(node, shapes)

        if name is not None:
            errors.extend(
                _validate_call(name, params, shapes[name], location, here)
            )

        for branch in _BRANCH_KEYS:
            inside = node.get(branch)

            if isinstance(inside, (list, tuple)):
                errors.extend(
                    _validate_arguments(
                        inside, shapes=shapes, location=location,
                        path=f"{here}.{branch}",
                    )
                )

        for number, mode in enumerate(_modes(node)):
            inside = mode.get("effects", ())

            if isinstance(inside, (list, tuple)):
                errors.extend(
                    _validate_arguments(
                        inside, shapes=shapes, location=location,
                        path=f"{here}.modes[{number}].effects",
                    )
                )

    return errors


def _effect_call(
    node: Mapping[str, Any],
    shapes: Mapping[str, Any],
) -> tuple[str | None, dict[str, Any]]:
    """
    The effect this node calls and the parameters it passes, or nothing.

    Two written forms, both of which the interpreter accepts, so both of which
    have to be read the same way here::

        {"effect": "gain_coins", "amount": 3}
        {"gain_coins": 3}
        {"draw_loot": {"count": 2}}

    A node naming a control word, or an effect this vocabulary has never heard
    of, is somebody else's complaint — the name check has already made it.
    """
    if "effect" in node:
        name = str(node["effect"])

        if name not in shapes:
            return None, {}

        return name, {
            key: value
            for key, value in node.items()
            if key not in WRITTEN_BY_THE_ENGINE
        }

    named = [
        key
        for key in node
        if key not in _MODIFIER_KEYS and key not in _BRANCH_KEYS
    ]

    if len(named) != 1 or named[0] not in shapes:
        return None, {}

    name = named[0]
    value = node[name]

    if isinstance(value, Mapping):
        return name, {
            key: item
            for key, item in value.items()
            if key not in WRITTEN_BY_THE_ENGINE
        }

    primary = shapes[name].primary

    return (name, {primary: value}) if primary else (None, {})


def _validate_call(
    name: str,
    params: Mapping[str, Any],
    shape: Any,
    location: str,
    path: str,
) -> list[str]:
    """
    One effect call, against what that effect takes.
    """
    errors: list[str] = []

    for key, value in params.items():
        if key in shape.literal:
            # The effect's own structured data. Nothing here may judge it.
            continue

        parameter = shape.params.get(key)

        if parameter is None:
            if not shape.open_ended:
                errors.append(
                    f"{location}: {path}.{key}: '{name}' takes no parameter "
                    f"called '{key}'"
                    f"{did_you_mean(key, list(shape.params))}"
                )

            continue

        errors.extend(_validate_value(name, parameter, value, location, path))

    for key, parameter in shape.params.items():
        if parameter.required and key not in params:
            errors.append(
                f"{location}: {path}: '{name}' needs '{key}' "
                f"({parameter.wants()}), and the card does not give it"
            )

    return errors


def _validate_value(
    name: str,
    parameter: Any,
    value: Any,
    location: str,
    path: str,
) -> list[str]:
    """
    One value, against the one parameter it was written for.
    """
    where = f"{location}: {path}.{parameter.name}"

    if value is None:
        if parameter.nullable:
            return []

        return [
            f"{where}: '{name}' takes {parameter.wants()} here, and the card "
            f"writes nothing; leave the key out instead"
        ]

    if isinstance(value, Mapping):
        head = DYNAMIC_HEADS & set(value)

        if not head:
            return [
                f"{where}: this asks for a value the ability works out while "
                f"it runs, and names it "
                f"{', '.join(repr(key) for key in sorted(value))}; the ways to "
                f"do that are {', '.join(sorted(DYNAMIC_HEADS))}"
            ]

        if not parameter.checkable or parameter.kind == WHOLE:
            return []

        return [
            f"{where}: '{name}' takes {parameter.wants()} here, and a value "
            f"worked out while the ability runs is always a whole number"
        ]

    if not parameter.checkable:
        return []

    written = _kind_written(value)

    if written != parameter.kind:
        return [
            f"{where}: '{name}' takes {parameter.wants()} here, "
            f"and the card gives {written} ({value!r})"
        ]

    if parameter.values and value not in parameter.values:
        return [
            f"{where}: '{name}' takes {parameter.wants()} here, "
            f"and the card gives {value!r}"
            f"{did_you_mean(str(value), [str(one) for one in parameter.values])}"
        ]

    if (
        parameter.least is not None
        and isinstance(value, int)
        and value < parameter.least
    ):
        return [
            f"{where}: '{name}' takes {parameter.wants()} here, "
            f"and the card gives {value!r}"
        ]

    return []


def _kind_written(value: Any) -> str:
    """
    What a card actually wrote, in the same words the parameters use.
    """
    if isinstance(value, bool):
        # Before int: in Python True is 1, and a card that writes true where a
        # count belongs has made a mistake worth naming rather than rounding.
        return FLAG

    if isinstance(value, int):
        return WHOLE

    if isinstance(value, str):
        return TEXT

    if isinstance(value, (list, tuple)):
        return "a list"

    return type(value).__name__


SUGGESTIONS = 3
"""How many near misses are worth offering."""

CLOSE_ENOUGH = 0.7
"""
How alike two names must be before one is offered for the other.

High on purpose. "Did you mean X?" is worth a great deal when it is right and
worse than silence when it is wrong, because a wrong suggestion sends somebody
to read about an effect that was never going to help them.
"""


def did_you_mean(name: str, known: Collection[str]) -> str:
    """
    Offer the nearest names the engine does know, when any are near.

    The most common content mistake is not a misunderstanding, it is a typo or
    a plural — ``gain_coinz`` for ``gain_coins``, ``draw_loots`` for
    ``draw_loot`` — and the engine holds the whole vocabulary already. Making
    somebody grep the source for the right spelling is a self-inflicted wound.
    """
    close = get_close_matches(name, sorted(known), n=SUGGESTIONS, cutoff=CLOSE_ENOUGH)

    if not close:
        return ""

    return " — did you mean " + " or ".join(f"'{one}'" for one in close) + "?"


_BOOLEAN_NAMES = frozenset({"and", "or", "not"})


def _node_names(nodes: Any, nested: Collection[str]) -> list[str]:
    """
    Collect the names used by a list of condition nodes, including nested ones.
    """
    names: list[str] = []

    if not isinstance(nodes, (list, tuple)):
        return names

    for node in nodes:
        if isinstance(node, str):
            names.append(node)
            continue

        if not isinstance(node, Mapping):
            continue

        if "condition" in node:
            names.append(str(node["condition"]))
            continue

        for key, value in node.items():
            names.append(str(key))

            if key in nested:
                names.extend(_node_names(value, nested))

            break

    return names


def _effect_aliases(nodes: Any) -> set[str]:
    """
    Names bound by targets written on individual effects.
    """
    names: set[str] = set()

    if not isinstance(nodes, (list, tuple)):
        return names

    for node in nodes:
        if not isinstance(node, Mapping):
            continue

        for spec in node.get("targets", ()) or ():
            if isinstance(spec, Mapping):
                names |= _declared_target_names({"targets": [spec]})

        target = node.get("target")

        if isinstance(target, Mapping):
            names |= _declared_target_names({"targets": [target]})

        for branch in _BRANCH_KEYS:
            names |= _effect_aliases(node.get(branch, ()))

        for mode in _modes(node):
            names |= _effect_aliases(mode.get("effects", ()))

    return names


def _declared_target_names(ability: Mapping[str, Any]) -> set[str]:
    """
    Collect the names an ability binds its own target groups under.

    An ability that declares ``{"target_player": {"as": "victim"}}`` may then
    point an effect at ``victim``. That name is not part of the engine's
    vocabulary and never will be — it belongs to this one card — so it has to
    be gathered from the ability rather than looked up.
    """
    names: set[str] = set()

    declared = ability.get("targets", ())

    if not isinstance(declared, (list, tuple)):
        return names

    for spec in declared:
        if isinstance(spec, str):
            names.add(spec)
            continue

        if not isinstance(spec, Mapping):
            continue

        if "as" in spec:
            names.add(str(spec["as"]))
            continue

        for value in spec.values():
            if isinstance(value, Mapping) and "as" in value:
                names.add(str(value["as"]))

    return names


def _target_names(ability: Mapping[str, Any]) -> list[str]:
    """
    Collect every target named by an ability, declared or used inline.
    """
    names: list[str] = []

    declared = ability.get("targets", ())

    if isinstance(declared, (list, tuple)):
        for spec in declared:
            if isinstance(spec, str):
                names.append(spec)
            elif isinstance(spec, Mapping):
                if "target" in spec:
                    names.append(str(spec["target"]))
                else:
                    for key in spec:
                        if key != "as":
                            names.append(str(key))
                            break

    names.extend(_inline_targets(ability.get("effects", ())))

    return names


def _inline_targets(nodes: Any) -> list[str]:
    """
    Collect targets written on individual effects.
    """
    names: list[str] = []

    if not isinstance(nodes, (list, tuple)):
        return names

    for node in nodes:
        if not isinstance(node, Mapping):
            continue

        target = node.get("target")

        if isinstance(target, str) and not target.startswith("__"):
            names.append(target)
        elif isinstance(target, Mapping):
            names.extend(_spec_names(target))

        asks = node.get("targets")

        if isinstance(asks, (list, tuple)):
            for spec in asks:
                if isinstance(spec, Mapping):
                    names.extend(_spec_names(spec))
                elif isinstance(spec, str):
                    names.append(spec)

        for key in ("for_each", "of"):
            value = node.get(key)

            if isinstance(value, str):
                names.append(value)

        for branch in _BRANCH_KEYS:
            names.extend(_inline_targets(node.get(branch, ())))

        for mode in _modes(node):
            names.extend(_inline_targets(mode.get("effects", ())))

    return names


_CONTROL_NAMES = frozenset(
    {"sequence", "if", "repeat", "for_each", "stop", "may", "choose"}
)

_MODIFIER_KEYS = frozenset(
    {
        "effect",
        "target",
        "targets",
        "optional",
        "description",
        "params",
        "as",
        "prompt",
        "store",
    }
)

_BRANCH_KEYS = ("effects", "then", "else", "may")


def _effect_names(nodes: Any) -> list[str]:
    """
    Collect every effect name used by a DSL fragment, including nested ones.
    """
    names: list[str] = []

    for node in nodes:
        if isinstance(node, str):
            names.append(node)
            continue

        if not isinstance(node, Mapping):
            continue

        if "effect" in node:
            names.append(str(node["effect"]))
        else:
            for key in node:
                if key not in _MODIFIER_KEYS and key not in _BRANCH_KEYS:
                    names.append(str(key))
                    break

        for branch in _BRANCH_KEYS:
            branch_value = node.get(branch)

            if isinstance(branch_value, (list, tuple)):
                names.extend(_effect_names(branch_value))

        for mode in _modes(node):
            names.extend(_effect_names(mode.get("effects", ())))

    return names


def _spec_names(spec: Mapping[str, Any]) -> list[str]:
    """
    Name the target a written-out specification asks for.
    """
    if "target" in spec:
        return [str(spec["target"])]

    for key in spec:
        if key not in ("as", "prompt"):
            return [str(key)]

    return []


_MODE_KEYS = ("modes", "choose")


def _modes(node: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """
    Return the modes of a "choose one" node.

    Each mode carries its own effects, and they are content like any other:
    a mode nobody picks in testing is still a mode that has to be valid.
    """
    for key in _MODE_KEYS:
        value = node.get(key)

        if isinstance(value, (list, tuple)):
            return [mode for mode in value if isinstance(mode, Mapping)]

    return []


def validate_cards(
    cards: Any,
    *,
    known_effects: Collection[str] | None = None,
    known_triggers: Collection[str] | None = None,
    known_conditions: Collection[str] | None = None,
    known_targets: Collection[str] | None = None,
    shapes: Mapping[str, Any] | None = None,
) -> list[str]:
    """
    Validate a collection of raw cards and report duplicate identifiers.
    """
    if not isinstance(cards, (list, tuple)):
        return [f"expected a list of cards, got {type(cards).__name__}"]

    errors: list[str] = []
    seen: set[str] = set()

    for card in cards:
        errors.extend(
            validate_card(
                card,
                known_effects=known_effects,
                known_triggers=known_triggers,
                known_conditions=known_conditions,
                known_targets=known_targets,
                shapes=shapes,
            )
        )

        if isinstance(card, Mapping) and "id" in card:
            card_id = str(card["id"])

            if card_id in seen:
                errors.append(f"{card_id}: duplicate card identifier")

            seen.add(card_id)

    return errors
