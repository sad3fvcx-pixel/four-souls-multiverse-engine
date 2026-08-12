# src/fsme/cards/validator.py

"""
Card content validation for Four Souls Multiverse Engine.

Validation happens before gameplay: ENGINE_INVARIANTS.md requires that invalid
content never reaches GameState, so the loader rejects a whole file rather than
letting a half-valid card into a game.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
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
) -> list[str]:
    """
    Return every problem found in one raw card.

    An empty list means the card is loadable. Effect and trigger vocabularies
    are passed in as plain names so that content validation stays independent
    of the effect implementations themselves.
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
) -> list[str]:
    location = f"{card_id}: ability {index}"

    if not isinstance(ability, Mapping):
        return [f"{location}: must be an object"]

    errors: list[str] = []

    trigger = ability.get("trigger")

    if not trigger:
        errors.append(f"{location}: missing 'trigger'")
    elif known_triggers is not None and trigger not in known_triggers:
        errors.append(f"{location}: unknown trigger '{trigger}'")

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
                    errors.append(f"{location}: unknown effect '{name}'")

    conditions = ability.get("conditions", ())

    if known_conditions is not None and isinstance(conditions, (list, tuple)):
        for name in _node_names(conditions, _BOOLEAN_NAMES):
            if name not in known_conditions and name not in _BOOLEAN_NAMES:
                errors.append(f"{location}: unknown condition '{name}'")

    if known_targets is not None:
        for name in _target_names(ability):
            if name not in known_targets:
                errors.append(f"{location}: unknown target '{name}'")

    return errors


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

        for key in ("for_each", "of"):
            value = node.get(key)

            if isinstance(value, str):
                names.append(value)

        for branch in _BRANCH_KEYS:
            names.extend(_inline_targets(node.get(branch, ())))

    return names


_CONTROL_NAMES = frozenset(
    {"sequence", "if", "repeat", "for_each", "stop"}
)

_MODIFIER_KEYS = frozenset(
    {"effect", "target", "targets", "optional", "description", "params"}
)

_BRANCH_KEYS = ("effects", "then", "else")


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

    return names


def validate_cards(
    cards: Any,
    *,
    known_effects: Collection[str] | None = None,
    known_triggers: Collection[str] | None = None,
    known_conditions: Collection[str] | None = None,
    known_targets: Collection[str] | None = None,
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
            )
        )

        if isinstance(card, Mapping) and "id" in card:
            card_id = str(card["id"])

            if card_id in seen:
                errors.append(f"{card_id}: duplicate card identifier")

            seen.add(card_id)

    return errors
