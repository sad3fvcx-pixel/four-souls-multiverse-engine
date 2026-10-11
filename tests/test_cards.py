"""
Cards are immutable data, validated before they ever reach a game.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import make_definition

from fsme.cards import (
    CardDefinition,
    CardLoader,
    CardRegistry,
    CardType,
    DuplicateCardError,
    InvalidCardError,
    UnknownCardError,
    validate_card,
)
from fsme.effects import builtin_registry

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "cards"


def test_definition_cannot_be_modified() -> None:
    definition = make_definition()

    with pytest.raises(AttributeError):
        definition.name = "changed"  # type: ignore[misc]


def test_nested_content_is_frozen() -> None:
    """
    Freezing has to reach inside abilities, or two copies of a card could
    diverge mid-game.
    """
    definition = CardDefinition.from_data(
        {
            "id": "test.frozen",
            "name": "Frozen",
            "type": "treasure",
            "expansion": "test",
            "abilities": [
                {"trigger": "on_activate", "effects": [{"gain_coins": 1}]}
            ],
            "metadata": {"artist": "someone"},
        }
    )

    ability = definition.abilities[0]

    assert isinstance(ability.effects, tuple)

    with pytest.raises(TypeError):
        ability.effects[0]["gain_coins"] = 99  # type: ignore[index]

    with pytest.raises(TypeError):
        definition.metadata["artist"] = "someone else"  # type: ignore[index]


def test_validator_reports_every_missing_field() -> None:
    errors = validate_card({"id": "broken.card"})

    assert any("name" in error for error in errors)
    assert any("type" in error for error in errors)
    assert any("expansion" in error for error in errors)
    assert any("abilities" in error for error in errors)


def test_validator_rejects_unknown_card_type() -> None:
    errors = validate_card(
        {
            "id": "broken.type",
            "name": "Broken",
            "type": "spaceship",
            "expansion": "test",
            "abilities": [],
        }
    )

    assert any("unknown card type" in error for error in errors)


def test_validator_rejects_unknown_effect_names() -> None:
    errors = validate_card(
        {
            "id": "broken.effect",
            "name": "Broken",
            "type": "treasure",
            "expansion": "test",
            "abilities": [
                {"trigger": "on_activate", "effects": [{"summon_dragon": 1}]}
            ],
        },
        known_effects=builtin_registry().names(),
    )

    assert any("unknown effect 'summon_dragon'" in error for error in errors)


def test_validator_accepts_control_flow() -> None:
    errors = validate_card(
        {
            "id": "good.card",
            "name": "Good",
            "type": "treasure",
            "expansion": "test",
            "abilities": [
                {
                    "trigger": "on_activate",
                    "effects": [
                        {"roll_dice": 6},
                        {
                            "if": [{"dice_greater": 3}],
                            "then": [{"gain_coins": 2}],
                            "else": [{"gain_coins": 1}],
                        },
                    ],
                }
            ],
        },
        known_effects=builtin_registry().names(),
    )

    assert errors == []


def test_registry_rejects_duplicate_identifiers() -> None:
    registry = CardRegistry([make_definition("test.one")])

    with pytest.raises(DuplicateCardError):
        registry.register(make_definition("test.one"))


def test_registry_reports_unknown_identifiers() -> None:
    registry = CardRegistry()

    with pytest.raises(UnknownCardError):
        registry.get("test.missing")


def test_loader_reads_the_example_expansion() -> None:
    loader = CardLoader(known_effects=builtin_registry().names())
    definitions = loader.load_directory(EXAMPLES)

    registry = CardRegistry(definitions)

    assert "example.penny_pincher" in registry
    assert registry.get("example.gaper").type is CardType.MONSTER
    assert registry.get("example.gaper").health == 2
    assert registry.by_type(CardType.TREASURE)


def test_loader_rejects_a_whole_file_on_one_bad_card() -> None:
    """
    Invalid content never reaches GameState, not even the valid half of it.
    """
    loader = CardLoader()

    with pytest.raises(InvalidCardError):
        loader.load_data(
            [
                {
                    "id": "good.card",
                    "name": "Good",
                    "type": "treasure",
                    "expansion": "test",
                    "abilities": [],
                },
                {"id": "bad.card"},
            ]
        )


def test_loader_rejects_duplicate_identifiers_within_content() -> None:
    loader = CardLoader()

    with pytest.raises(InvalidCardError):
        loader.load_data(
            [
                {
                    "id": "same.id",
                    "name": "A",
                    "type": "loot",
                    "expansion": "test",
                    "abilities": [],
                },
                {
                    "id": "same.id",
                    "name": "B",
                    "type": "loot",
                    "expansion": "test",
                    "abilities": [],
                },
            ]
        )
