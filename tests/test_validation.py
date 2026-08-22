"""
Checking a card before anybody plays it.

The pipeline has always refused a card that names an effect the engine has
never heard of. What it did not do was look at what the card *gave* that
effect, so `{"effect": "gain_coins", "amount": "lots"}` loaded cleanly and then,
four hundred moves into somebody's study, raised

    TypeError: '<' not supported between instances of 'str' and 'int'

naming no card, no file and no field. For content somebody else wrote that is
the difference between a tool and a trap.

The most important test in this file is the last one: the whole of `content/`
still loads. 1045 cards, 352 of them with rules, every one a case a person
already decided was correct — if a check here is wrong, that is where it shows.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from fsme.api import load_content
from fsme.cards import validate_card
from fsme.content import UNCHECKED, ContentLoader, Vocabulary
from fsme.content.errors import InvalidContentError
from fsme.runtime.vocabulary import engine_vocabulary

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"

EXPANSION = "example_expansion"


@pytest.fixture(scope="module")
def vocabulary() -> Vocabulary:
    return engine_vocabulary()


def a_card(*effects: Any, card_id: str = "example_expansion-loot-dark_coin") -> dict:
    return {
        "id": card_id,
        "name": "Dark Coin",
        "type": "loot",
        "expansion": EXPANSION,
        "schema_version": "1",
        "abilities": [{"trigger": "on_play", "effects": list(effects)}],
    }


def _minimally(vocabulary: Vocabulary, effect: str, extra: dict) -> dict:
    """
    An effect node with everything the effect insists on, plus what is asked.

    Some effects refuse to run without a parameter — `promise` needs the event
    it is waiting for. A probe about something else should not have to know
    which, so the required ones are filled from the effect's own description.
    """
    shape = vocabulary.shape(effect)
    node: dict[str, Any] = {"effect": effect}

    for name, parameter in (shape.params if shape else {}).items():
        if parameter.required and name not in extra:
            node[name] = parameter.values[0] if parameter.values else "x"

    node.update(extra)

    return node


def complaints(vocabulary: Vocabulary, *effects: Any) -> list[str]:
    return validate_card(
        a_card(*effects),
        known_effects=vocabulary.effects,
        known_triggers=vocabulary.triggers,
        known_conditions=vocabulary.conditions,
        known_targets=vocabulary.targets,
        shapes=vocabulary.shapes,
    )


def a_set(tmp_path: Path, *cards: dict) -> Path:
    """
    A one-set content tree, built where a test may write.
    """
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
# Good content is left alone
# ----------------------------------------------------------------------


def test_a_good_card_passes(vocabulary: Vocabulary) -> None:
    assert complaints(vocabulary, {"effect": "gain_coins", "amount": 3}) == []


def test_the_shorthand_form_passes(vocabulary: Vocabulary) -> None:
    assert complaints(vocabulary, {"gain_coins": 3}) == []
    assert complaints(vocabulary, {"draw_loot": {"count": 2}}) == []


def test_a_value_the_ability_works_out_passes(vocabulary: Vocabulary) -> None:
    """
    The five heads the executor knows are all legal where a number belongs.
    """
    for head in ("from", "from_event", "last_result"):
        assert complaints(
            vocabulary,
            {"roll_dice": 6},
            {"effect": "gain_coins", "amount": {head: "dice"}},
        ) == [], head


def test_an_effect_that_only_takes_targets_is_not_second_guessed(
    vocabulary: Vocabulary,
) -> None:
    """
    Two dozen effects are written with `**kwargs` and work on their targets.
    They would accept anything, so nothing may be refused on their behalf.
    """
    assert complaints(vocabulary, {"effect": "kill", "target": "current_monster"}) == []
    assert complaints(vocabulary, {"effect": "kill", "whatever": 3}) == []


def test_a_parameter_the_effect_keeps_as_written_is_not_judged(
    vocabulary: Vocabulary,
) -> None:
    """
    `EffectSpec.literal` names parameters handed over exactly as the card wrote
    them — the effect's own structured data, which nothing here may read.
    """
    from fsme.cards.validator import CONDITION_KEYS

    pairs = sorted(
        (name, key)
        for name in vocabulary.effects
        if vocabulary.shape(name) is not None
        for key in vocabulary.shape(name).literal
        # `watch_for` keeps its `conditions` as written, and they really are
        # conditions: the runtime hands them to the same evaluator an ability's
        # are handed to. So they are checked, and checking them is right —
        # see the test below. Sampling one here would be sampling the one
        # literal parameter that has a second meaning.
        if key not in CONDITION_KEYS
    )

    assert pairs, "some effect keeps a parameter as written"

    for name, key in pairs:
        assert complaints(
            vocabulary, _minimally(vocabulary, name, {key: {"anything": ["at", "all"]}})
        ) == [], f"{name}.{key}"


def test_conditions_an_effect_keeps_as_written_are_still_conditions(
    vocabulary: Vocabulary,
) -> None:
    """
    The one literal parameter that is not opaque.

    `watch_for` records an ability to run when an event arrives, and the
    runtime evaluates its `conditions` with the same evaluator it uses for an
    ability's own. A condition the engine has never heard of therefore stops
    the game when the watched event happens — which may be many turns after
    the card was played, and is exactly the kind of delay validation exists to
    remove.
    """
    watching = {
        "effect": "watch_for",
        "event": "damage_dealt",
        "conditions": [{"player_hpp": 1}],
        "effects": [{"effect": "gain_coins", "amount": 1}],
    }

    (message,) = complaints(vocabulary, watching)

    assert "unknown condition 'player_hpp'" in message


# ----------------------------------------------------------------------
# The mistakes, each with what it must say
# ----------------------------------------------------------------------


def test_an_unknown_effect_is_still_refused(vocabulary: Vocabulary) -> None:
    said = complaints(vocabulary, {"effect": "summon_a_dragon"})

    assert any("unknown effect 'summon_a_dragon'" in one for one in said)


def test_the_wrong_kind_of_value_is_refused(vocabulary: Vocabulary) -> None:
    said = complaints(vocabulary, {"effect": "gain_coins", "amount": "lots"})

    assert len(said) == 1

    only = said[0]

    assert "effects[0].amount" in only
    assert "gain_coins" in only
    assert "whole number" in only
    assert "text" in only
    assert "'lots'" in only


def test_true_is_not_a_number(vocabulary: Vocabulary) -> None:
    """
    In Python `True` is 1. A card that writes it where a count belongs has made
    a mistake worth naming rather than rounding off.
    """
    said = complaints(vocabulary, {"effect": "draw_loot", "count": True})

    assert said and "true or false" in said[0]


def test_a_value_outside_the_deck_names_the_decks(vocabulary: Vocabulary) -> None:
    said = complaints(vocabulary, {"effect": "shuffle_deck", "deck": "spaghetti"})

    assert len(said) == 1
    assert "'loot'" in said[0] and "'room'" in said[0]
    assert "spaghetti" in said[0]


def test_a_number_below_the_floor_is_refused(vocabulary: Vocabulary) -> None:
    said = complaints(vocabulary, {"effect": "draw_loot", "count": -3})

    assert len(said) == 1
    assert "at least 0" in said[0]


def test_a_misspelled_dynamic_head_is_refused(vocabulary: Vocabulary) -> None:
    """
    The executor knows five ways to name a value worked out while an ability
    runs and hands anything else straight to the effect — so a misspelling is
    a dictionary arriving where a number was expected.
    """
    said = complaints(
        vocabulary,
        {"roll_dice": 6},
        {"effect": "gain_coins", "amount": {"frmo": "dice"}},
    )

    assert len(said) == 1
    assert "'frmo'" in said[0]
    assert "from_event" in said[0] and "last_result" in said[0]


def test_a_parameter_the_effect_does_not_take_is_refused(
    vocabulary: Vocabulary,
) -> None:
    said = complaints(vocabulary, {"effect": "gain_coins", "amount": 2, "amonut": 3})

    assert len(said) == 1
    assert "takes no parameter called 'amonut'" in said[0]
    assert "did you mean 'amount'" in said[0]


def test_writing_nothing_is_refused(vocabulary: Vocabulary) -> None:
    said = complaints(vocabulary, {"effect": "gain_coins", "amount": None})

    assert len(said) == 1
    assert "leave the key out" in said[0]


def test_a_mistake_inside_a_branch_is_found_and_placed(
    vocabulary: Vocabulary,
) -> None:
    said = complaints(
        vocabulary,
        {"if": ["dice_even"], "then": [{"effect": "gain_coins", "amount": "lots"}]},
    )

    assert len(said) == 1
    assert "effects[0].then[0].amount" in said[0]


def test_a_mistake_inside_a_choice_is_found(vocabulary: Vocabulary) -> None:
    said = complaints(
        vocabulary,
        {
            "choose": [
                {"description": "one", "effects": [{"gain_coins": 1}]},
                {"description": "two", "effects": [{"effect": "draw_loot", "count": "many"}]},
            ]
        },
    )

    assert len(said) == 1
    assert "modes[1].effects[0].count" in said[0]


def test_every_mistake_is_reported_at_once(vocabulary: Vocabulary) -> None:
    said = complaints(
        vocabulary,
        {"effect": "gain_coins", "amount": "lots"},
        {"effect": "shuffle_deck", "deck": "spaghetti"},
        {"effect": "draw_loot", "count": -3},
    )

    assert len(said) == 3


# ----------------------------------------------------------------------
# Through the loader, where an author actually meets it
# ----------------------------------------------------------------------


def test_a_broken_set_is_refused_with_its_expansion_file_and_card(
    tmp_path: Path,
) -> None:
    root = a_set(tmp_path, a_card({"effect": "gain_coins", "amount": "lots"}))

    with pytest.raises(InvalidContentError) as raised:
        load_content(root)

    said = str(raised.value)

    assert EXPANSION in said
    assert "loot.json" in said
    assert "example_expansion-loot-dark_coin" in said
    assert "ability 0: effects[0].amount" in said
    assert "whole number" in said and "text" in said


def test_a_good_set_loads_and_plays(tmp_path: Path) -> None:
    root = a_set(tmp_path, a_card({"effect": "gain_coins", "amount": 7}))

    library = load_content(root)

    assert len(library.definitions()) == 1


def test_several_broken_cards_are_all_named(tmp_path: Path) -> None:
    root = a_set(
        tmp_path,
        a_card({"effect": "gain_coins", "amount": "lots"}),
        a_card({"effect": "draw_loot", "count": -1}, card_id="example_expansion-loot-two"),
        a_card({"effect": "shuffle_deck", "deck": "nope"}, card_id="example_expansion-loot-three"),
    )

    with pytest.raises(InvalidContentError) as raised:
        load_content(root)

    said = str(raised.value)

    assert said.count("[semantic]") == 3


# ----------------------------------------------------------------------
# The seam, and the promise to callers who have no engine
# ----------------------------------------------------------------------


def test_a_vocabulary_without_shapes_checks_names_only(tmp_path: Path) -> None:
    """
    A caller with no engine gets structure and spelling, and no argument
    checking — which is what every caller got before this existed.
    """
    root = a_set(tmp_path, a_card({"effect": "gain_coins", "amount": "lots"}))

    plain = Vocabulary.of(
        effects=engine_vocabulary().effects,
        triggers=engine_vocabulary().triggers,
    )

    library = ContentLoader(plain).load_root(root)

    assert len(library.definitions()) == 1


def test_an_empty_vocabulary_is_still_empty() -> None:
    assert Vocabulary().is_empty


def test_a_vocabulary_with_names_is_not_empty_even_without_shapes() -> None:
    """
    Naming the effects is enough to check spelling, so such a vocabulary must
    not be treated as having nothing to say.
    """
    assert not Vocabulary.of(effects=("gain_coins",)).is_empty


def test_the_descriptions_carry_no_engine(vocabulary: Vocabulary) -> None:
    """
    The pipeline may not hold a live effect. What crosses is names and kinds.
    """
    for shape in vocabulary.shapes.values():
        assert not callable(shape)

        for parameter in shape.params.values():
            for field in (
                parameter.name,
                parameter.kind,
                parameter.required,
                parameter.nullable,
                parameter.values,
                parameter.least,
            ):
                assert isinstance(
                    field, (str, bool, tuple, int, type(None))
                ), field


def test_every_effect_can_describe_itself(vocabulary: Vocabulary) -> None:
    """
    A newly registered effect cannot quietly opt out of being described.
    """
    from fsme.effects import builtin_registry

    registry = builtin_registry()

    for name in registry.names():
        shape = vocabulary.shape(name)

        assert shape is not None, name
        assert shape.name == name


def test_anything_means_not_checked_here_and_not_anything_goes(
    vocabulary: Vocabulary,
) -> None:
    """
    `Any` on a handler means the effect takes a card, a player or a shape that
    only means something once a board exists. The runtime guard stays.
    """
    open_ones = [
        (name, parameter.name)
        for name in vocabulary.effects
        if vocabulary.shape(name)
        for parameter in vocabulary.shape(name).params.values()
        if parameter.kind == UNCHECKED
    ]

    assert open_ones, "some parameters are judged only during a game"

    name, parameter = open_ones[0]

    assert complaints(
        vocabulary, _minimally(vocabulary, name, {parameter: "anything at all"})
    ) == []

    from fsme.effects.builtin.decks import DECKS

    assert "spaghetti" not in DECKS, "the runtime guard still knows the decks"


def test_a_domain_named_for_a_parameter_that_does_not_exist_is_refused() -> None:
    """
    A typo in the engine, caught while it is being written.
    """
    from fsme.effects import EffectRegistry
    from fsme.effects.errors import EffectRegistrationError

    registry = EffectRegistry()

    def handler(ctx: object, targets: object, amount: int = 1) -> int:
        return amount

    with pytest.raises(EffectRegistrationError) as raised:
        registry.register("example", handler, values={"amonut": (1, 2)})

    assert "no parameter 'amonut'" in str(raised.value)


# ----------------------------------------------------------------------
# The one that decides whether the design was right
# ----------------------------------------------------------------------


def test_the_whole_of_the_official_content_still_loads() -> None:
    """
    1045 cards, 352 of them with rules, every one a case somebody already
    decided was correct. If a check here is wrong, this is where it shows.
    """
    library = load_content(CONTENT_ROOT)

    assert len(library.definitions()) == 1045
    assert len(library) == 24
