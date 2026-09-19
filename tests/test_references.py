"""
The names an ability gives things, and where it may use them again.

"Choose a player at random — that player destroys an item they control" is two
steps, and the second reads the first. Getting that wrong used to load cleanly
every time: a name read before the target that binds it resolved to nothing, a
name bound twice made the engine skip the second target entirely, and a name
reached for inside a `watch_for` found an empty context, because a watcher runs
later against one of its own.

None of it needs a board, which is the point. What does need one — whether a
group turns out to be empty — is not a mistake at all, and nothing here asks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fsme.api import load_content
from fsme.cards import validate_card
from fsme.content import Vocabulary
from fsme.content.errors import InvalidContentError
from fsme.runtime.target_resolver import TargetResolver
from fsme.runtime.vocabulary import engine_vocabulary

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"

EXPANSION = "example_expansion"

COINS = [{"effect": "gain_coins", "amount": 1}]


@pytest.fixture(scope="module")
def vocabulary() -> Vocabulary:
    return engine_vocabulary()


def a_card(**ability: Any) -> dict:
    body = {"trigger": "on_play", "effects": COINS}
    body.update(ability)

    return {
        "id": "example_expansion-loot-dark_coin",
        "name": "Dark Coin",
        "type": "loot",
        "expansion": EXPANSION,
        "schema_version": "1",
        "abilities": [body],
    }


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
    )


def naming(vocabulary: Vocabulary, **ability: Any) -> list[str]:
    return complaints(vocabulary, a_card(**ability))


# ----------------------------------------------------------------------
# What a target hands back is declared where it is registered
# ----------------------------------------------------------------------


def test_every_target_says_what_it_hands_back() -> None:
    """
    A target that could be registered without saying would make the kinds a
    separate table, and a separate table drifts.
    """
    resolver = TargetResolver()
    shapes = resolver.shapes()

    silent = sorted(name for name in resolver.names() if not shapes[name].yields)

    assert silent == []


def test_the_two_kinds_are_the_two_the_engine_tells_apart(
    vocabulary: Vocabulary,
) -> None:
    """
    Players and cards, and nothing finer, because nothing finer is enforced
    anywhere — every runtime filter asks `isinstance(x, PlayerState)`.
    """
    kinds = {shape.yields for shape in vocabulary.target_shapes.values()}

    assert kinds == {"players", "cards", "mixed", "passthrough"}


def test_one_word_reads_different_namespaces(vocabulary: Vocabulary) -> None:
    """
    `of` names players on `target_loot`, cards on `holder`, anything on
    `group`, and a stored value on `values_equal`. It belongs to the thing
    reading it, never to the word.
    """
    assert vocabulary.target_shape("target_loot").params["of"].refers_to == "players"
    assert vocabulary.target_shape("holder").params["of"].refers_to == "cards"
    assert vocabulary.target_shape("group").params["of"].refers_to == "any"
    assert vocabulary.condition_shape("values_equal").params["of"].refers_to == "values"


# ----------------------------------------------------------------------
# Names that do not resolve
# ----------------------------------------------------------------------


def test_an_unknown_group_is_refused(vocabulary: Vocabulary) -> None:
    (message,) = naming(vocabulary, targets=[{"target_treasure": {"of": "nobody"}}])

    assert "'nobody' is not a group this ability binds" in message


def test_a_name_used_before_it_is_bound_is_refused(vocabulary: Vocabulary) -> None:
    """
    And says which mistake it is. "You have not bound that" and "you have
    bound that, further down" are different things to go and fix.
    """
    (message,) = naming(
        vocabulary,
        targets=[
            {"target_loot": {"of": "later"}},
            {"target_player": {"as": "later"}},
        ],
    )

    assert "'later' is bound, but not where this can see it" in message


def test_a_name_bound_inside_a_branch_is_not_visible_outside_it(
    vocabulary: Vocabulary,
) -> None:
    """
    A branch shares the context at run time, but whether it ran is not a fact
    about the text.
    """
    (message,) = naming(
        vocabulary,
        effects=[
            {
                "may": [
                    {
                        "effect": "recharge",
                        "targets": [{"target_treasure": {"as": "revived"}}],
                    }
                ],
                "prompt": "Recharge an item?",
            },
            {"effect": "destroy_treasure", "target": "revived"},
        ],
    )

    assert "'revived' is bound, but not where this can see it" in message


def test_binding_one_name_twice_is_refused(vocabulary: Vocabulary) -> None:
    """
    The quietest of them. `resolve_all` leaves an already-bound alias alone —
    which is what makes an ability resumable after a player answers — so the
    second target is not merely overwritten, it never runs.
    """
    (message,) = naming(
        vocabulary,
        targets=[
            {"target_player": {"as": "who"}},
            {"target_monster": {"as": "who"}},
        ],
    )

    assert "'who' is already bound by another target" in message


# ----------------------------------------------------------------------
# Names that do resolve
# ----------------------------------------------------------------------


def test_a_name_bound_and_read_inside_one_branch_is_right(
    vocabulary: Vocabulary,
) -> None:
    """
    Eight shipped cards do exactly this, and every one of them reads the name
    inside the same `may` that bound it.
    """
    assert (
        naming(
            vocabulary,
            effects=[
                {
                    "may": [
                        {
                            "effect": "recharge",
                            "targets": [{"target_treasure": {"as": "revived"}}],
                            "target": "revived",
                        }
                    ],
                    "prompt": "Recharge an item?",
                }
            ],
        )
        == []
    )


def test_a_loop_may_name_the_group_it_walks(vocabulary: Vocabulary) -> None:
    assert (
        naming(
            vocabulary,
            targets=[{"all_players": {"as": "everyone"}}],
            effects=[{"for_each": "everyone", "effects": COINS}],
        )
        == []
    )


def test_a_choice_may_bind_within_each_of_its_modes(vocabulary: Vocabulary) -> None:
    assert (
        naming(
            vocabulary,
            effects=[
                {
                    "choose": [
                        {
                            "effects": [
                                {
                                    "effect": "kill",
                                    "targets": [{"target_monster": {"as": "prey"}}],
                                    "target": "prey",
                                }
                            ]
                        },
                        {"effects": COINS},
                    ]
                }
            ],
        )
        == []
    )


def test_naming_a_target_where_a_group_belongs_is_not_a_reference(
    vocabulary: Vocabulary,
) -> None:
    """
    `{"of": "all_players"}` is asking for that target again, which the engine
    spells out itself, and is not a name anybody had to bind.
    """
    assert naming(vocabulary, targets=[{"target_loot": {"of": "all_players"}}]) == []


# ----------------------------------------------------------------------
# A watcher runs in a context of its own
# ----------------------------------------------------------------------


def test_a_watcher_cannot_see_what_the_ability_bound(
    vocabulary: Vocabulary,
) -> None:
    """
    Its effects run when the event arrives, against an `AbilityContext` the
    runtime builds then. Nothing bound out here is there to be found — and the
    card would not fail, it would quietly do nothing.
    """
    (message,) = naming(
        vocabulary,
        targets=[{"target_player": {"as": "who"}}],
        effects=[
            {
                "effect": "watch_for",
                "event": "damage_dealt",
                "effects": [{"effect": "kill", "target": "who"}],
            }
        ],
    )

    assert "'who' is bound, but not where this can see it" in message


def test_a_watcher_may_bind_its_own(vocabulary: Vocabulary) -> None:
    assert (
        naming(
            vocabulary,
            effects=[
                {
                    "effect": "watch_for",
                    "event": "damage_dealt",
                    "effects": [
                        {
                            "effect": "kill",
                            "targets": [{"target_monster": {"as": "beast"}}],
                            "target": "beast",
                        }
                    ],
                }
            ],
        )
        == []
    )


# ----------------------------------------------------------------------
# Kinds, and only the two that are enforced
# ----------------------------------------------------------------------


def test_cards_where_players_are_wanted_is_refused(vocabulary: Vocabulary) -> None:
    (message,) = naming(
        vocabulary,
        targets=[
            {"target_monster": {"as": "beast"}},
            {"target_loot": {"of": "beast"}},
        ],
    )

    assert "'beast' holds cards, and this wants players" in message


def test_players_where_cards_are_wanted_is_refused(vocabulary: Vocabulary) -> None:
    (message,) = naming(
        vocabulary,
        targets=[
            {"target_player": {"as": "who"}},
            {"deck_top": {"exclude": "who"}},
        ],
    )

    assert "'who' holds players, and this wants cards" in message


def test_a_chooser_must_be_somebody(vocabulary: Vocabulary) -> None:
    (message,) = naming(
        vocabulary,
        targets=[
            {"target_monster": {"as": "beast"}},
            {"target_player": {"chooser": "beast"}},
        ],
    )

    assert "'beast' holds cards, and this wants players" in message


def test_a_kind_that_cannot_be_proved_is_not_guessed(vocabulary: Vocabulary) -> None:
    """
    `group` hands back whatever it was given, so nothing can be said about
    what comes out of it — and nothing is. A check that cannot be proved is
    skipped, not invented.
    """
    assert (
        naming(
            vocabulary,
            targets=[
                {"target_monster": {"as": "beast"}},
                {"group": {"of": "beast", "as": "gathered"}},
                {"target_loot": {"of": "gathered"}},
            ],
        )
        == []
    )


# ----------------------------------------------------------------------
# The other namespace
# ----------------------------------------------------------------------


def test_values_equal_reads_what_was_stored(vocabulary: Vocabulary) -> None:
    assert (
        naming(
            vocabulary,
            conditions=[{"values_equal": {"of": ["first", "second"]}}],
            effects=[
                {"roll_dice": 6, "store": "first"},
                {"roll_dice": 6, "store": "second"},
            ],
        )
        != []
    ), "conditions are read before the rolls happen"

    assert (
        naming(
            vocabulary,
            effects=[
                {"roll_dice": 6, "store": "first"},
                {"roll_dice": 6, "store": "second"},
                {
                    "if": [{"values_equal": {"of": ["first", "second"]}}],
                    "then": COINS,
                },
            ],
        )
        == []
    )


def test_values_equal_does_not_see_target_groups(vocabulary: Vocabulary) -> None:
    """
    The two namespaces never meet. A group is not a stored value, however
    good a name it has.
    """
    messages = naming(
        vocabulary,
        targets=[{"target_player": {"as": "who"}}],
        effects=[{"if": [{"values_equal": {"of": ["who", "who"]}}], "then": COINS}],
    )

    assert any("'who' is not a value this ability stores" in m for m in messages)


# ----------------------------------------------------------------------
# Through the loader, and against everything already written
# ----------------------------------------------------------------------


def test_the_loader_refuses_a_set_whose_reference_is_wrong(tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / EXPANSION / "cards").mkdir(parents=True)
    (root / EXPANSION / "manifest.json").write_text(
        json.dumps(
            {
                "id": EXPANSION,
                "name": "Example",
                "version": "1.0.0",
                "schema_version": "1",
            }
        ),
        encoding="utf-8",
    )
    (root / EXPANSION / "cards" / "loot.json").write_text(
        json.dumps(
            {"cards": [a_card(targets=[{"target_treasure": {"of": "nobody"}}])]}
        ),
        encoding="utf-8",
    )

    with pytest.raises(InvalidContentError) as raised:
        load_content(root)

    assert "'nobody'" in str(raised.value)
    assert EXPANSION in str(raised.value)


def test_everything_already_written_still_passes() -> None:
    """
    The test that matters. 1045 cards, every reference written by somebody who
    decided it was right.
    """
    library = load_content(CONTENT_ROOT)

    assert len(library.registry()) > 1000
