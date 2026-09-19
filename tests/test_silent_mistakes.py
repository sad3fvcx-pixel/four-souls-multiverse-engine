"""
The mistakes that used to load and then change what a card does.

Every check here closes a case where an author wrote something wrong, the
engine accepted it, and the card went on to play by rules nobody had written.
A misspelled `scope` fell through to the branch that means "controller". A
misspelled `stat` matched nothing, so the static contributed silently nothing.
A misspelled key inside an `if` made a branch that never ran.

The rule underneath all of them: the top of a card is **extensible**, because
a set may carry an artist credit or a field a later engine will read. Inside
the DSL it is **strict**, because there is nothing to be forward compatible
with — the interpreter reads a closed set of keys and hands nothing else on.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fsme.api import load_content
from fsme.cards import validate_card
from fsme.content import Vocabulary
from fsme.runtime.vocabulary import engine_vocabulary

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"
KIT = Path(__file__).resolve().parents[1] / "author-kit" / "examples"

COINS = [{"effect": "gain_coins", "amount": 1}]


@pytest.fixture(scope="module")
def vocabulary() -> Vocabulary:
    return engine_vocabulary()


def a_card(
    *,
    ability: dict | None = None,
    statics: Any = None,
    card_type: str = "loot",
    **extra: Any,
) -> dict:
    body: dict[str, Any] = {
        "id": "mine-loot-probe",
        "name": "Probe",
        "type": card_type,
        "expansion": "mine",
        "schema_version": "1",
        "abilities": [dict({"trigger": "on_play", "effects": COINS}, **(ability or {}))],
    }

    if statics is not None:
        body["statics"] = statics

    body.update(extra)

    return body


def complaints(vocabulary: Vocabulary, card: dict) -> list[str]:
    return validate_card(
        card,
        known_effects=vocabulary.effects,
        known_triggers=vocabulary.triggers,
        known_conditions=vocabulary.conditions,
        known_targets=vocabulary.targets,
        shapes=vocabulary.shapes,
        condition_shapes=vocabulary.condition_shapes,
        target_shapes=vocabulary.target_shapes,
        node_shapes=vocabulary.node_shapes,
    )


# ----------------------------------------------------------------------
# The domains come from the branches that read them
# ----------------------------------------------------------------------


def test_the_scope_domains_are_the_ones_the_engine_branches_on(
    vocabulary: Vocabulary,
) -> None:
    from fsme.rules.statics import STATIC_SCOPES
    from fsme.runtime.runtime import ABILITY_SCOPES

    assert vocabulary.node_shape("ability").params["scope"].values == ABILITY_SCOPES
    assert vocabulary.node_shape("static").params["scope"].values == STATIC_SCOPES


def test_the_accepted_keys_are_the_dataclass_fields(vocabulary: Vocabulary) -> None:
    """
    So a key added to the language is accepted the moment it is read, and
    refused until then. Writing the set out by hand is what drifts.
    """
    from dataclasses import fields

    from fsme.cards.definition import Ability, Static

    assert set(vocabulary.node_shape("ability").params) == {
        field.name for field in fields(Ability)
    }
    assert set(vocabulary.node_shape("static").params) == {
        field.name for field in fields(Static)
    }


def test_the_stat_domain_is_the_union_where_the_engine_defers(
    vocabulary: Vocabulary,
) -> None:
    """
    `add_modifier` decides player-or-monster from the target's runtime type,
    so nothing before a game may narrow it further.
    """
    from fsme.state.modifiers import MONSTER_STATS, STATS

    assert set(vocabulary.shape("add_modifier").params["stat"].values) == set(
        STATS
    ) | set(MONSTER_STATS)


# ----------------------------------------------------------------------
# Scope
# ----------------------------------------------------------------------


def test_a_misspelled_ability_scope_is_refused(vocabulary: Vocabulary) -> None:
    (message,) = complaints(vocabulary, a_card(ability={"scope": "contoller"}))

    assert "'contoller' is not one of" in message
    assert "did you mean 'controller'" in message
    assert "abilities[0].scope" in message


def test_a_misspelled_static_scope_is_refused(vocabulary: Vocabulary) -> None:
    (message,) = complaints(
        vocabulary,
        a_card(statics=[{"stat": "attack", "amount": 1, "scope": "contoller"}]),
    )

    assert "statics[0].scope" in message
    assert "'all_monsters'" in message, "and says what the choices are"


# ----------------------------------------------------------------------
# Stat, in the context it is applied
# ----------------------------------------------------------------------


def test_a_misspelled_stat_is_refused(vocabulary: Vocabulary) -> None:
    (message,) = complaints(
        vocabulary,
        a_card(statics=[{"stat": "atack", "amount": 1, "scope": "controller"}]),
    )

    # Which stats are on offer depends on the scope beside it, and the
    # message says so rather than naming a list out of nowhere.
    assert "'atack' is not one of the ones 'scope' allows here" in message
    assert "did you mean 'attack'" in message


def test_a_player_stat_on_a_monster_scope_is_refused(vocabulary: Vocabulary) -> None:
    """
    It loads and then nobody reads it: `monster_value` asks about a monster's
    two numbers and `max_hp` is not one of them.
    """
    (message,) = complaints(
        vocabulary,
        a_card(statics=[{"stat": "max_hp", "amount": 1, "scope": "all_monsters"}]),
    )

    assert "'max_hp' is not one of the ones 'scope' allows here" in message
    assert "'difficulty'" in message


def test_a_monster_stat_on_a_player_scope_is_refused(vocabulary: Vocabulary) -> None:
    (message,) = complaints(
        vocabulary,
        a_card(statics=[{"stat": "difficulty", "amount": 1, "scope": "controller"}]),
    )

    assert "'difficulty' is not one of the ones 'scope' allows here" in message


def test_a_monsters_own_static_may_change_its_difficulty(
    vocabulary: Vocabulary,
) -> None:
    """
    `self` on a monster card reaches the monster, so the monster's stats are
    the right set. Four shipped cards write exactly this.
    """
    assert (
        complaints(
            vocabulary,
            a_card(
                statics=[{"stat": "difficulty", "amount": 1, "scope": "self"}],
                card_type="monster",
            ),
        )
        == []
    )


def test_add_modifier_may_still_name_either_kind(vocabulary: Vocabulary) -> None:
    assert (
        complaints(
            vocabulary,
            a_card(
                ability={
                    "effects": [
                        {
                            "effect": "add_modifier",
                            "stat": "difficulty",
                            "amount": 1,
                            "target": "current_monster",
                        }
                    ]
                }
            ),
        )
        == []
    )


def test_a_misspelled_stat_on_add_modifier_is_refused(vocabulary: Vocabulary) -> None:
    (message,) = complaints(
        vocabulary,
        a_card(
            ability={
                "effects": [
                    {
                        "effect": "add_modifier",
                        "stat": "atack",
                        "amount": 1,
                        "target": "controller",
                    }
                ]
            }
        ),
    )

    assert "'atack'" in message
    assert "did you mean 'attack'" in message


# ----------------------------------------------------------------------
# Strict inside the DSL, extensible at the top of a card
# ----------------------------------------------------------------------


def test_an_unknown_key_on_a_card_is_kept(vocabulary: Vocabulary) -> None:
    """
    The one place forward compatibility is a real argument, and CARD_SCHEMA
    §14 promises it.
    """
    assert complaints(vocabulary, a_card(rarity="epic", artist="somebody")) == []


def test_an_unknown_key_on_an_ability_is_refused(vocabulary: Vocabulary) -> None:
    (message,) = complaints(vocabulary, a_card(ability={"whenever": "always"}))

    assert "'whenever' is not part of an ability" in message


def test_an_unknown_key_on_a_static_is_refused(vocabulary: Vocabulary) -> None:
    (message,) = complaints(
        vocabulary,
        a_card(statics=[{"stat": "attack", "amount": 1, "whenver": True}]),
    )

    assert "'whenver' is not part of a static" in message


@pytest.mark.parametrize(
    ("node", "typo", "meant"),
    [
        ({"if": [{"dice_greater": 3}], "thne": COINS}, "thne", "then"),
        ({"may": COINS, "promt": "Do it?"}, "promt", "prompt"),
        ({"repeat": 2, "efects": COINS}, "efects", "effects"),
    ],
)
def test_an_unknown_key_inside_a_control_node_is_refused(
    vocabulary: Vocabulary, node: dict, typo: str, meant: str
) -> None:
    """
    The quietest of the lot: `thne` makes a branch that never runs, and
    nothing ever says so.
    """
    (message,) = complaints(vocabulary, a_card(ability={"effects": [node]}))

    assert f"'{typo}' is not part of" in message
    assert f"did you mean '{meant}'" in message


def test_a_nested_control_node_is_checked_too(vocabulary: Vocabulary) -> None:
    (message,) = complaints(
        vocabulary,
        a_card(
            ability={
                "effects": [
                    {
                        "may": [
                            {"if": [{"dice_greater": 3}], "then": COINS, "esle": COINS}
                        ],
                        "prompt": "Try?",
                    }
                ]
            }
        ),
    )

    assert "'esle' is not part of an if" in message


# ----------------------------------------------------------------------
# And nothing that already works stops working
# ----------------------------------------------------------------------


def test_all_the_shipped_content_still_loads() -> None:
    assert len(load_content(CONTENT_ROOT).registry()) > 1000


def test_the_author_kit_examples_still_load() -> None:
    assert len(load_content(KIT).registry()) == 5
