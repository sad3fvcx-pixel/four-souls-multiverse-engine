"""
Checking where a card looks before it looks there.

Targets are the third and last vocabulary a card writes in. Their names have
been checked for some time — including the hard part, that a specification may
name a group the ability bound earlier with `as`, which belongs to one card
and is in no registry. What was never checked is the inside of one.

Eleven deliberately wrong targets were put through the loader before this
existed. All eleven loaded. Six then stopped the game somewhere in the middle
of a study, naming no card and no file; five never complained at all, and the
card simply did something other than what it says for as long as anybody
played it. Two of those five were shipped cards.

Two parameters keep the same word for different questions, which is why the
descriptions belong to targets rather than to parameter names: `owner` on an
item means one of two roles, `owner` on a curse means the one the code tests
for, and `count` is how many to choose for a chooser and how many cards for a
deck.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fsme.api import load_content
from fsme.cards import validate_card
from fsme.content import ContentLoader, Vocabulary
from fsme.content.errors import InvalidContentError
from fsme.runtime.target_resolver import TargetResolver
from fsme.runtime.vocabulary import engine_vocabulary

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"

EXPANSION = "example_expansion"


@pytest.fixture(scope="module")
def vocabulary() -> Vocabulary:
    return engine_vocabulary()


def a_card(
    *targets: Any,
    statics: Any = None,
    effects: Any = None,
    card_id: str = "example_expansion-loot-dark_coin",
) -> dict:
    card: dict[str, Any] = {
        "id": card_id,
        "name": "Dark Coin",
        "type": "loot",
        "expansion": EXPANSION,
        "schema_version": "1",
        "abilities": [
            {
                "trigger": "on_play",
                "targets": list(targets),
                "effects": effects
                if effects is not None
                else [{"effect": "gain_coins", "amount": 1}],
            }
        ],
    }

    if statics is not None:
        card["statics"] = statics

    return card


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


def aiming(vocabulary: Vocabulary, *targets: Any) -> list[str]:
    return complaints(vocabulary, a_card(*targets))


def a_set(tmp_path: Path, *cards: dict) -> Path:
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
        json.dumps({"cards": list(cards)}), encoding="utf-8"
    )

    return root


# ----------------------------------------------------------------------
# The description stays beside the implementation
# ----------------------------------------------------------------------


def test_every_target_the_engine_ships_says_what_it_takes() -> None:
    """
    A target that could be added undescribed would make the descriptions a
    separate table again, and a separate table drifts. That is not a guess:
    `of` had one meaning and two implementations, and the third place that
    needed it never heard of it.
    """
    resolver = TargetResolver()
    shapes = resolver.shapes()

    undescribed = sorted(name for name in resolver.names() if shapes[name].open_ended)

    assert undescribed == []


def test_the_domains_are_read_from_the_code_that_enforces_them(
    vocabulary: Vocabulary,
) -> None:
    """
    Not written out a second time. A thing the engine cannot count and a thing
    validation refuses have to be the same set, or one of them is wrong.
    """
    from fsme.cards.types import CardType
    from fsme.runtime.target_resolver import _COUNTABLE

    most = vocabulary.target_shape("target_player")
    searching = vocabulary.target_shape("target_deck_card")

    assert most is not None and searching is not None
    assert set(most.params["most"].values) == set(_COUNTABLE)
    assert set(searching.params["card_type"].values) == {
        str(kind) for kind in CardType
    }


def test_the_decks_are_read_off_the_state_the_lookup_uses() -> None:
    """
    `_target_deck_card` finds its zone by building an attribute name out of
    the two words a card wrote. The words that work are therefore the
    attributes that exist, and both come from the same place.
    """
    from fsme.runtime.target_resolver import DECKS, PILES
    from fsme.state import GameState

    for deck in DECKS:
        for pile in PILES:
            assert hasattr(GameState, f"{deck}_{pile}") or any(
                field == f"{deck}_{pile}"
                for field in GameState.__dataclass_fields__
            ), f"{deck}_{pile}"


def test_a_target_registered_without_a_description_is_not_judged() -> None:
    """
    Saying nothing is not permission. Nobody outside a game may refuse a
    parameter of a target whose author did not describe it — and nothing here
    reads that silence as consent either.
    """
    resolver = TargetResolver()
    resolver.register("the_nearest_window", lambda state, context, params, rng: [])

    shape = resolver.shapes()["the_nearest_window"]

    assert shape.open_ended
    # Even undescribed, it still takes what every target takes.
    assert set(shape.params) == {"as"}


def test_every_target_takes_the_name_it_binds_under(vocabulary: Vocabulary) -> None:
    """
    `as` is the resolver's own rather than any helper's: `resolve` reads it
    before the target is looked up, and `resolve_all` reads it again to bind
    the answer. Attributing it to the helper that asks questions was tried,
    and forty-one shipped cards said otherwise.
    """
    missing = sorted(
        name
        for name, shape in vocabulary.target_shapes.items()
        if "as" not in shape.params
    )

    assert missing == []


# ----------------------------------------------------------------------
# Good cards are left alone
# ----------------------------------------------------------------------


def test_the_forms_a_card_may_use_all_pass(vocabulary: Vocabulary) -> None:
    assert aiming(vocabulary, "all_players") == []
    assert aiming(vocabulary, {"player": 2}) == []
    assert aiming(vocabulary, {"random_player": {"exclude_controller": True}}) == []
    assert (
        aiming(vocabulary, {"target": "target_deck_card", "deck": "treasure"}) == []
    )


def test_a_group_the_ability_bound_is_not_looked_up(vocabulary: Vocabulary) -> None:
    """
    103 specifications in the shipped cards name a group rather than a target.
    """
    card = a_card(
        {"random_player": {"as": "unlucky"}},
        {"target_treasure": {"of": "unlucky", "as": "doomed"}},
        effects=[{"effect": "destroy_treasure", "target": "doomed"}],
    )

    assert complaints(vocabulary, card) == []


def test_a_reference_is_not_judged_as_a_value(vocabulary: Vocabulary) -> None:
    """
    `of`, `chooser` and `exclude` carry a name rather than a value, so this
    layer says nothing about what is written in them — a name is neither a
    number nor a member of any domain.

    Whether the name resolves is a different question, asked by the reference
    layer and not here. `tests/test_references.py` covers that; what this
    pins is that the two do not overlap, which they did not when this file
    was written and must not begin to.
    """
    for spec in (
        {"target_treasure": {"of": "whoever"}},
        {"target_player": {"chooser": "whoever"}},
        {"deck_top": {"exclude": "whatever"}},
    ):
        (message,) = aiming(vocabulary, spec)

        assert "is not a group this ability binds" in message, message


# ----------------------------------------------------------------------
# Bad cards are refused
# ----------------------------------------------------------------------


def test_a_deck_that_does_not_exist_is_refused(vocabulary: Vocabulary) -> None:
    """
    The worst of them. Today this loads, and the game stops when a player
    finally searches — hundreds of moves in, naming no card.
    """
    (deck,) = aiming(vocabulary, {"target_deck_card": {"deck": "tresure"}})
    (pile,) = aiming(vocabulary, {"target_deck_card": {"pile": "graveyard"}})
    (top,) = aiming(vocabulary, {"deck_top": {"deck": "loots"}})

    assert "'tresure'" in deck and "'treasure'" in deck
    assert "'graveyard'" in pile and "'discard'" in pile
    assert "'loots'" in top


def test_a_thing_the_engine_cannot_count_is_refused(vocabulary: Vocabulary) -> None:
    (message,) = aiming(vocabulary, {"target_player": {"most": "fingers"}})

    assert "'fingers'" in message
    assert "'souls'" in message


def test_a_parameter_of_the_wrong_kind_is_refused(vocabulary: Vocabulary) -> None:
    (count,) = aiming(vocabulary, {"target_player": {"count": "two"}})
    (flag,) = aiming(vocabulary, {"all_players": {"include_dead": "yes"}})
    (seat,) = aiming(vocabulary, {"player": {"value": "one"}})

    assert "wants a whole number" in count
    assert "wants true or false" in flag
    assert "wants a whole number" in seat


def test_a_number_outside_what_the_target_can_mean_is_refused(
    vocabulary: Vocabulary,
) -> None:
    """
    Looking at the top nothing of a deck is not a search.
    """
    (message,) = aiming(vocabulary, {"target_deck_card": {"from_top": 0}})

    assert "at least 1" in message


def test_a_parameter_the_target_would_drop_is_refused(
    vocabulary: Vocabulary,
) -> None:
    """
    The quiet one, and not hypothetical: `of` on an item target was dropped in
    silence for as long as anybody played the two shipped cards that wrote it.
    """
    (message,) = aiming(vocabulary, {"target_player": {"exclude_dead": True}})

    assert "takes no 'exclude_dead'" in message


def test_one_word_may_mean_different_things_to_different_targets(
    vocabulary: Vocabulary,
) -> None:
    """
    `_all_treasures` reads `controller` and `opponents`. `_target_curse` tests
    for `controller` and treats everything else as the whole table, so
    `opponents` there would be accepted and ignored.
    """
    assert aiming(vocabulary, {"target_treasure": {"owner": "opponents"}}) == []

    (message,) = aiming(vocabulary, {"target_curse": {"owner": "opponents"}})

    assert "wants 'controller'" in message


def test_a_list_is_checked_item_by_item(vocabulary: Vocabulary) -> None:
    assert aiming(vocabulary, {"target_stack_item": {"triggers": ["on_play"]}}) == []

    (message,) = aiming(vocabulary, {"target_stack_item": {"triggers": ["on_ply"]}})

    assert "'on_ply'" in message


# ----------------------------------------------------------------------
# Everywhere a card may write a target
# ----------------------------------------------------------------------


def test_a_target_on_a_static_is_checked(vocabulary: Vocabulary) -> None:
    card = a_card(
        statics=[
            {
                "stat": "attack",
                "amount": 1,
                "targets": [{"target_deck_card": {"deck": "tresure"}}],
            }
        ]
    )

    (message,) = complaints(vocabulary, card)

    assert "statics[0].targets[0]" in message


def test_a_target_written_on_one_effect_is_checked(vocabulary: Vocabulary) -> None:
    aimed = {"target_monster": {"exclude_attacked": 1}}
    card = a_card(effects=[{"may": [{"effect": "kill", "target": aimed}]}])

    (message,) = complaints(vocabulary, card)

    assert "effects[0].may[0].target" in message
    assert "wants true or false" in message


def test_every_problem_in_a_card_is_reported_at_once(vocabulary: Vocabulary) -> None:
    messages = aiming(
        vocabulary,
        {"target_deck_card": {"deck": "tresure"}},
        {"target_player": {"most": "fingers"}},
        {"all_players": {"include_dead": "yes"}},
    )

    assert len(messages) == 3


# ----------------------------------------------------------------------
# Through the loader, and against everything already written
# ----------------------------------------------------------------------


def test_the_loader_refuses_a_set_whose_target_is_wrong(tmp_path: Path) -> None:
    root = a_set(tmp_path, a_card({"target_deck_card": {"deck": "tresure"}}))

    with pytest.raises(InvalidContentError) as raised:
        load_content(root)

    assert "'tresure'" in str(raised.value)
    assert EXPANSION in str(raised.value)


def test_a_set_whose_targets_are_right_loads(tmp_path: Path) -> None:
    root = a_set(tmp_path, a_card({"target_deck_card": {"deck": "treasure"}}))

    library = load_content(root)

    assert library.registry().get("example_expansion-loot-dark_coin") is not None


def test_a_vocabulary_without_target_shapes_checks_names_only(
    tmp_path: Path,
) -> None:
    engine = engine_vocabulary()
    names_only = Vocabulary.of(
        effects=engine.effects,
        triggers=engine.triggers,
        conditions=engine.conditions,
        targets=engine.targets,
    )

    root = a_set(tmp_path, a_card({"target_deck_card": {"deck": "tresure"}}))

    library = ContentLoader(names_only).load_root(root)

    assert library.registry().get("example_expansion-loot-dark_coin") is not None


def test_everything_already_written_still_passes() -> None:
    """
    922 target specifications, every one written by somebody who decided it
    was right. If a description above is wrong, it shows here.
    """
    library = load_content(CONTENT_ROOT)

    assert len(library.registry()) > 1000
