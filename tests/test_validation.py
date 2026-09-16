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

import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from fsme.api import load_content
from fsme.cards import validate_card
from fsme.content import UNCHECKED, ContentLoader, Vocabulary
from fsme.content.errors import InvalidContentError
from fsme.content.vocabulary import BY_PLAYER_OF
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
        if not parameter.required or name in extra:
            continue

        node[name] = _something(parameter)

    node.update(extra)

    return node


def _something(parameter: Any) -> Any:
    """
    A value of the right shape, whatever shape the parameter says it takes.
    """
    if parameter.values:
        return parameter.values[0]

    if parameter.kind == "a list":
        return []

    if parameter.kind == "a set of named values":
        return {}

    return "x"


def complaints(vocabulary: Vocabulary, *effects: Any) -> list[str]:
    return validate_card(
        a_card(*effects),
        known_effects=vocabulary.effects,
        known_triggers=vocabulary.triggers,
        known_conditions=vocabulary.conditions,
        known_targets=vocabulary.targets,
        shapes=vocabulary.shapes,
    )


def wholly(vocabulary: Vocabulary, *effects: Any) -> list[str]:
    """
    `complaints`, plus what the engine says about the shape of a node itself.

    The loader and the desk both hand these over; the checks that read a
    node's own description are the ones that need them.
    """
    return validate_card(
        a_card(*effects),
        known_effects=vocabulary.effects,
        known_triggers=vocabulary.triggers,
        known_conditions=vocabulary.conditions,
        known_targets=vocabulary.targets,
        shapes=vocabulary.shapes,
        condition_shapes=vocabulary.condition_shapes,
        target_shapes=vocabulary.target_shapes,
        node_shapes=vocabulary.node_shapes,
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
    them — the effect's own structured data, whose contents nothing here may
    read. Its outer shape is a different question and has its own test below.
    """
    from fsme.cards.validator import _BRANCH_KEYS, CONDITION_KEYS

    pairs = sorted(
        (name, key)
        for name in vocabulary.effects
        if vocabulary.shape(name) is not None
        for key in vocabulary.shape(name).literal
        # Two of them have a second meaning. `watch_for` keeps its `conditions`
        # and its `effects` as written, and they really are conditions and
        # effects: the runtime hands them to the same evaluator and the same
        # interpreter an ability's are handed to, and the checker walks into
        # both. Sampling one of those would be sampling the exception.
        if key not in CONDITION_KEYS and key not in _BRANCH_KEYS
    )

    assert pairs, "some effect keeps a parameter as written"

    for name, key in pairs:
        assert complaints(
            vocabulary,
            _minimally(vocabulary, name, {key: {"anything": ["at", "all"]}}),
        ) == [], f"{name}.{key}"


def test_the_shape_a_kept_parameter_is_kept_in_is_judged(
    vocabulary: Vocabulary,
) -> None:
    """
    Not what is inside — whether there is an inside at all.

    ``{"effects": "gain_coins"}`` is a card that meant a list of things to do
    and wrote the name of one. It used to load, and then fail the first time
    somebody played it, which is the worst place to find out. The handler has
    always raised on it; the effect now says so where a card file can be told.
    """
    outer = sorted(
        (name, key, parameter.kind)
        for name in vocabulary.effects
        if vocabulary.shape(name) is not None
        for key, parameter in vocabulary.shape(name).params.items()
        if key in vocabulary.shape(name).literal
        and parameter.kind in ("a list", "a set of named values")
    )

    assert [(name, key) for name, key, _ in outer] == [
        ("promise", "changes"),
        ("promise", "when"),
        ("watch_for", "conditions"),
        ("watch_for", "effects"),
    ]

    for name, key, _ in outer:
        assert complaints(
            vocabulary, _minimally(vocabulary, name, {key: "gain_coins"})
        ), f"{name}.{key} took a sentence where a structure belongs"


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
    from fsme.cards.validator import CONDITION_KEYS

    open_ones = sorted(
        (name, parameter.name)
        for name in vocabulary.effects
        if vocabulary.shape(name)
        for parameter in vocabulary.shape(name).params.values()
        # Not the ones that name somebody. Those are unjudgeable as *values*
        # and perfectly judgeable as sentences, and there is a test below for
        # what they accept. Nor the ones holding conditions, which are
        # conditions and checked as conditions.
        if parameter.kind == UNCHECKED
        and not parameter.written_as
        and parameter.name not in CONDITION_KEYS
    )

    assert open_ones, "some parameters are judged only during a game"

    for name, parameter in open_ones:
        assert complaints(
            vocabulary,
            _minimally(vocabulary, name, {parameter: "anything at all"}),
        ) == [], f"{name}.{parameter}"

    from fsme.effects.builtin.decks import DECKS

    assert "spaghetti" not in DECKS, "the runtime guard still knows the decks"


def test_naming_somebody_is_checked_even_though_the_value_is_not(
    vocabulary: Vocabulary,
) -> None:
    """
    A parameter that names a player takes a name, not a sentence.

    "Unjudgeable" was doing two jobs. A card the engine hands over cannot be
    checked before a game exists — but *how a card names one* can, and the
    engine says how. Written down, ``{"who": "the loser"}`` used to load and
    then fail the moment somebody played the card, which is the worst place to
    find out.
    """
    naming = sorted(
        (name, parameter.name, parameter.written_as)
        for name in vocabulary.effects
        if vocabulary.shape(name)
        for parameter in vocabulary.shape(name).params.values()
        if parameter.written_as
    )

    assert naming, "some effects take somebody the ability picked out"

    for name, parameter, _ in naming:
        said = complaints(
            vocabulary, _minimally(vocabulary, name, {parameter: "the loser"})
        )

        assert said, f"{name}.{parameter} took a sentence where a name belongs"

    for name, parameter, written in naming:
        if written != BY_PLAYER_OF:
            continue

        assert complaints(
            vocabulary,
            _minimally(vocabulary, name, {parameter: {BY_PLAYER_OF: "chosen"}}),
        ) == [], f"{name}.{parameter}"


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
# Every body, checked the same
# ----------------------------------------------------------------------
#
# A control node keeps what it does under a key, and there are seven such keys.
# The walkers that look for unknown effects, mistyped arguments and undeclared
# names used to walk by four of them, because the list they walked by was the
# one that answers a different question — which keys are *not* an effect name.
# So `{"sequence": [...]}` was a body nothing looked inside: the checker passed
# the card and the runtime raised on it. These say every body is walked, that
# the list is still the whole list, and that `sequence` groups steps without
# putting a wall around the names bound in it.


UNKNOWN = {"effect": "summon_a_dragon"}
"""A step naming an effect the engine has never heard of."""

MISTYPED = {"effect": "gain_coins", "amount": "lots"}
"""A step giving an effect text where it takes a number."""

BINDS = {
    "effect": "deal_damage",
    "amount": 1,
    "targets": [{"target_player": {"as": "victim"}}],
    "target": "victim",
}
"""A step that binds a name."""

USES = {"effect": "deal_damage", "amount": 1, "target": "victim"}
"""A step that reads one."""


def holding(*steps: Any) -> dict[str, dict[str, Any]]:
    """
    One well-formed node of every control kind, each holding the given steps.

    Written out rather than generated so that a node whose shape changes fails
    here as a wrong expectation instead of quietly becoming a different probe.
    Both spellings appear wherever the interpreter reads two.
    """
    body = list(steps)

    return {
        "sequence": {"sequence": body},
        "if.then": {"if": [{"condition": "has_coins", "amount": 1}], "then": body},
        "if.else": {"if": [{"condition": "has_coins", "amount": 1}],
                    "then": [{"effect": "gain_coins", "amount": 1}], "else": body},
        "may": {"may": body, "prompt": "Well?"},
        "choose.modes": {"modes": [{"description": "A", "effects": body}]},
        "choose.choose": {"choose": [{"description": "A", "effects": body}]},
        "repeat": {"repeat": 2, "effects": body},
        "for_each": {"for_each": "all_players", "effects": body},
    }


@pytest.mark.parametrize("wrong", [UNKNOWN, MISTYPED], ids=["unknown", "mistyped"])
def test_every_control_body_is_looked_inside(
    vocabulary: Vocabulary, wrong: dict
) -> None:
    """
    The same mistake, once under each key a control node keeps steps under.

    `sequence` is the one that used to pass. The other seven are here so that
    walking by a wider list cannot quietly stop walking by part of it.
    """
    missed = [
        where
        for where, node in holding(wrong).items()
        if not complaints(vocabulary, node)
    ]

    assert missed == [], missed


@pytest.mark.parametrize("wrong", [UNKNOWN, MISTYPED], ids=["unknown", "mistyped"])
def test_a_mistake_is_found_however_deep_the_bodies_go(
    vocabulary: Vocabulary, wrong: dict
) -> None:
    """
    Nested both ways round: everything inside a sequence, a sequence inside
    everything. A walker that stops one level down passes the test above and
    fails this one.
    """
    missed: list[str] = []

    for where, node in holding(wrong).items():
        # The mistake is already inside `node`; putting `node` in a sequence
        # adds a level above it.
        if not complaints(vocabulary, {"sequence": [node]}):
            missed.append(f"{where} inside a sequence")

        # And the other way round: a sequence carrying the mistake, inside
        # each control node in turn.
        if not complaints(vocabulary, holding({"sequence": [wrong]})[where]):
            missed.append(f"a sequence inside {where}")

    assert missed == [], missed


def test_a_sequence_does_not_wall_off_the_names_bound_in_it(
    vocabulary: Vocabulary,
) -> None:
    """
    `sequence` groups steps and asks nothing, so it always runs, so a name
    bound inside one is still bound after it — which is what the runtime does
    and what the reference checker has always done. Looking inside a body must
    not have turned looking into fencing.
    """
    assert complaints(vocabulary, {"sequence": [BINDS]}, USES) == []
    assert complaints(vocabulary, BINDS, {"sequence": [USES]}) == []
    assert complaints(vocabulary, {"sequence": [BINDS, USES]}) == []


def test_a_name_that_was_never_bound_is_still_refused_inside_a_sequence(
    vocabulary: Vocabulary,
) -> None:
    """
    The other half of the rule above: sharing the context is not accepting
    anything.
    """
    assert complaints(vocabulary, {"sequence": [USES]}) != []


def test_the_bodies_walked_are_the_bodies_there_are() -> None:
    """
    The list the validator walks by against the table read off the expanders.

    `CONTROL_BODIES` is where the interpreter says what each control node keeps
    its contents under, and it is the only place that knows. This module is
    handed what an engine knows as plain data and never imports one, so the
    two cannot be one object — but they can be required to agree, which is the
    part that was missing when `sequence` was left out of one of them.
    """
    from fsme.cards.validator import _BODY_KEYS, _MODE_KEYS
    from fsme.runtime.interpreter import CONTROL_BODIES

    every = {key for keys in CONTROL_BODIES.values() for key in keys}

    assert set(_BODY_KEYS) | set(_MODE_KEYS) == every


def test_what_is_not_an_effect_name_is_asked_separately() -> None:
    """
    Two questions that happen to have similar answers.

    `_BRANCH_KEYS` says which keys on a node are a body rather than the name of
    an effect, so that `{"may": [...], "prompt": "..."}` is one misspelling and
    not two complaints. `_BODY_KEYS` says which keys to walk. Reading the first
    as the second is what left `sequence` unwalked, and widening the first to
    fix it would change what counts as a mistyped effect.
    """
    from fsme.cards.validator import _BODY_KEYS, _BRANCH_KEYS

    assert _BRANCH_KEYS != _BODY_KEYS
    assert set(_BRANCH_KEYS) < set(_BODY_KEYS)


# ----------------------------------------------------------------------
# A body key with no head is not a node
# ----------------------------------------------------------------------
#
# A node is named by `effect`, by a control head, or by its one remaining key.
# A body key is none of those: it is where a head keeps what it does, and the
# head is what reads it. Written on its own it names nothing that can run, and
# the interpreter says so — `unknown effect 'then'` — but only once somebody
# plays the card. The checker used to pass it, because the key it would have
# been named after is one the name-finder steps over on the way past.
#
# It steps over it for a good reason, which is why the fix is not to stop:
# beside a head the same key is a body, and on a node written the short way it
# is a parameter. Only when nothing else named the node is the key all there is.


HEADLESS = ("effects", "then", "else")
"""The body keys that are not also a control head. `modes` is the fourth."""


@pytest.mark.parametrize("key", HEADLESS)
@pytest.mark.parametrize("held", [[{"gain_coins": 1}], []], ids=["holding", "empty"])
def test_a_body_key_written_without_a_head_is_refused(
    vocabulary: Vocabulary, key: str, held: list
) -> None:
    """
    Full or empty makes no difference: there is no head to read either.
    """
    said = complaints(vocabulary, {key: held})

    assert any(f"unknown effect '{key}'" in one for one in said), (key, said)


def test_a_body_key_with_no_head_is_refused_like_modes_always_was(
    vocabulary: Vocabulary,
) -> None:
    """
    `modes` is the one of the four that was always refused — it is not in the
    list the name-finder steps over. The other three now read the same way.
    """
    for key in (*HEADLESS, "modes"):
        said = complaints(vocabulary, {key: [{"gain_coins": 1}]})

        assert any(f"unknown effect '{key}'" in one for one in said), key


@pytest.mark.parametrize(
    "node",
    [
        {"effects": [{"gain_coins": 1}], "draw_loot": 3},
        {"draw_loot": 3, "effects": [{"gain_coins": 1}]},
    ],
    ids=["body first", "effect first"],
)
def test_a_short_node_carrying_a_body_key_is_still_named_by_its_effect(
    vocabulary: Vocabulary, node: dict
) -> None:
    """
    Whichever order it is written in.

    This is what the name-finder steps over a body key *for*, and it is why
    the three above are answered by asking again afterwards rather than by
    taking those keys out of the list it steps over.
    """
    assert complaints(vocabulary, node) == [], complaints(vocabulary, node)


def test_the_effects_an_effect_takes_are_still_its_own(
    vocabulary: Vocabulary,
) -> None:
    """
    `effects` is a control body and also a parameter of a real effect.

    `watch_for` keeps what it will do under that name, and fourteen shipped
    nodes are written that way. Such a node says `effect`, so it is named
    before any of this is reached — but it is the case a rule about body keys
    would break first, so it is pinned here.

    `promise` is the other effect that runs something later; it keeps its own
    answer under `changes` rather than `effects`, so it is not a case of this.
    """
    assert complaints(
        vocabulary,
        {
            "effect": "watch_for",
            "event": "after_roll",
            "conditions": [{"dice_equals": 1}],
            "effects": [{"draw_loot": 1}],
        },
    ) == []


def test_a_head_with_a_misspelled_key_is_still_one_complaint(
    vocabulary: Vocabulary,
) -> None:
    """
    `{"may": [...], "promt": "..."}` is a `may` with a typo, not a `may` and an
    effect called `promt`. A node with a head never reaches the new question.
    """
    said = complaints(vocabulary, {"may": [{"gain_coins": 1}], "promt": "x"})

    assert not [one for one in said if "unknown effect" in one], said


@pytest.mark.parametrize(
    "node",
    [
        {"if": ["first_turn"], "then": [{"gain_coins": 1}]},
        {"if": ["first_turn"], "then": [{"gain_coins": 1}],
         "else": [{"gain_coins": 2}]},
        {"may": [{"gain_coins": 1}], "prompt": "Well?"},
        {"sequence": [{"gain_coins": 1}]},
        {"repeat": 2, "effects": [{"gain_coins": 1}]},
        {"for_each": "all_players", "effects": [{"gain_coins": 1}]},
        {"choose": [{"description": "A", "effects": [{"gain_coins": 1}]}]},
    ],
)
def test_a_body_beside_its_head_is_a_body(
    vocabulary: Vocabulary, node: dict
) -> None:
    """
    Every control node as a card may write it. None is a headless anything,
    and none of them changed.
    """
    assert complaints(vocabulary, node) == [], complaints(vocabulary, node)


@pytest.mark.parametrize(
    "node",
    [
        {"conditions": ["first_turn"], "then": [{"gain_coins": 1}]},
        {"times": 2, "effects": [{"gain_coins": 1}]},
        {"of": "all_players", "effects": [{"gain_coins": 1}]},
    ],
    ids=["conditions", "times", "of"],
)
def test_a_second_spelling_is_not_a_head_either(
    vocabulary: Vocabulary, node: dict
) -> None:
    """
    `conditions`, `times` and `of` are the other name for a key a head reads,
    not another name for the head. A node written with one and no head names
    nothing, and the interpreter says the same — `effect node must name exactly
    one effect`. Refusing it is older than this rule and is pinned here because
    a rule about what names a node is exactly what could stop it happening.
    """
    said = complaints(vocabulary, node)

    assert any("unknown effect" in one for one in said), said


def test_nothing_here_knows_the_name_of_a_card_or_an_effect() -> None:
    """
    The rule is about what names a node, so it is written in the words the
    language already has for that: the keys a head keeps its contents under.
    A list of effects that are special would be a second copy of the engine.
    """
    from fsme.cards import validator

    said = inspect.getsource(validator._effect_names)
    said = "\n".join(line.split("#")[0] for line in said.splitlines())

    for named in ("gain_coins", "draw_loot", "watch_for", "promise",
                  "then", "else", "modes"):
        assert f'"{named}"' not in said, named
        assert f"'{named}'" not in said, named

    # Which keys are bodies is asked of the list that says so, not spelled
    # again here: a body the language gains is covered without this changing.
    assert "_BODY_KEYS" in said


# ----------------------------------------------------------------------
# A list says what is in it
# ----------------------------------------------------------------------
#
# A node is found by a key that names its shape. An element of a list has no
# such key — it is found by where it is — so the walker that goes by keys steps
# straight past it, and `a_list_of` was an answer written down and never read.
#
# A choice is the one place in the language that holds such a list today. Its
# options could be the word "A", or an empty object, and the card checked clean,
# loaded into a game, offered the choice to a player and only then stopped:
# `InterpreterError: invalid mode: 'A'`, after somebody had already answered.


def a_mode(**fields: Any) -> dict:
    """One option of a choice, with whatever this probe wants to say about it."""
    return {"description": "Take a coin", "effects": [{"gain_coins": 1}], **fields}


def test_a_choice_made_of_proper_options_is_left_alone(
    vocabulary: Vocabulary,
) -> None:
    """
    One, several, and under either spelling of the key that holds them.
    """
    one, two = a_mode(), a_mode(description="Heal instead")

    assert wholly(vocabulary, {"choose": [one]}) == []
    assert wholly(vocabulary, {"choose": [one, two]}) == []
    assert wholly(vocabulary, {"choose": True, "modes": [one, two]}) == []


@pytest.mark.parametrize(
    "option",
    ["A", 1, None, ["A"], 2.5],
    ids=["text", "number", "nothing", "a list", "a fraction"],
)
def test_an_option_that_is_not_an_option_is_refused(
    vocabulary: Vocabulary, option: Any
) -> None:
    """
    Whatever it is, it is not a mode, and the engine cannot be handed it.
    """
    said = wholly(vocabulary, {"choose": [option]})

    assert len(said) == 1, said
    assert "this is a mode" in said[0], said


def test_only_the_option_that_is_wrong_is_named(vocabulary: Vocabulary) -> None:
    """
    A list with one bad option in it is one complaint, at the right index.
    """
    said = wholly(vocabulary, {"choose": ["A", a_mode()]})

    assert len(said) == 1, said
    assert "choose[0]" in said[0], said


def test_an_option_with_nothing_to_offer_is_refused(
    vocabulary: Vocabulary,
) -> None:
    """
    The words of an option are what a player is shown. Without them the engine
    offers "mode 1", which is not what anybody wrote, and the metadata has
    always said the description is required — nothing read it.
    """
    for option in ({}, {"effects": [{"gain_coins": 1}]}, a_mode(description="")):
        said = wholly(vocabulary, {"choose": [option]})

        assert len(said) == 1, (option, said)
        assert "needs 'description'" in said[0], (option, said)


@pytest.mark.parametrize("wrong", [0, False, None, [], {}], ids=str)
def test_an_option_whose_words_are_not_words_is_one_complaint(
    vocabulary: Vocabulary, wrong: Any
) -> None:
    """
    Holding the wrong sort of thing is a different mistake from holding
    nothing, and is already named as one. Saying it is missing as well would
    be one violation and two complaints.
    """
    said = wholly(vocabulary, {"choose": [a_mode(description=wrong)]})

    assert len(said) == 1, said
    assert "takes text" in said[0], said


def test_an_option_is_checked_against_its_whole_shape(
    vocabulary: Vocabulary,
) -> None:
    """
    Not only that it is an object — everything the shape says about one.
    """
    said = wholly(vocabulary, {"choose": [a_mode(efffects=[])]})

    assert len(said) == 1, said
    assert "not part of a mode" in said[0], said


def test_what_a_list_holds_is_asked_of_the_metadata() -> None:
    """
    Only where the named kind is a shape this layer has.

    `a_list_of: "step"` names a catalogue, and what is in such a list is walked
    by whatever walks that kind; asking again here would say one thing twice.
    Which lists are which is the metadata's answer, so a list the language
    gains of either sort is covered without this changing.
    """
    from fsme.cards import validator

    # What it does, not what it says about itself: the prose may name a kind
    # as an example, and does.
    said = inspect.getsource(validator._each_one)
    said = said.split('"""')[2]
    said = "\n".join(line.split("#")[0] for line in said.splitlines())

    for named in ("choose", "modes", "mode", "step", "condition", "target"):
        assert f'"{named}"' not in said, named
        assert f"'{named}'" not in said, named

    assert "a_list_of" in said


def test_the_lists_a_card_walks_itself_are_not_walked_twice(
    vocabulary: Vocabulary,
) -> None:
    """
    `abilities` and `statics` are lists of a named shape too, and they are
    walked by name from the top of the card rather than found in a node. They
    reach that walk without passing this one — the card's own shape is never
    applied as a node — so an ability with no trigger is still told so once.
    """
    said = validate_card(
        {
            "id": "example_expansion-loot-dark_coin",
            "name": "Dark Coin",
            "type": "loot",
            "expansion": EXPANSION,
            "schema_version": "1",
            "abilities": [{"effects": [{"gain_coins": 1}]}],
        },
        known_effects=vocabulary.effects,
        known_triggers=vocabulary.triggers,
        known_conditions=vocabulary.conditions,
        known_targets=vocabulary.targets,
        shapes=vocabulary.shapes,
        node_shapes=vocabulary.node_shapes,
    )

    assert [one for one in said if "trigger" in one] == [
        "example_expansion-loot-dark_coin: ability 0: missing 'trigger'"
    ], said


def test_an_effect_that_keeps_its_own_list_is_untouched(
    vocabulary: Vocabulary,
) -> None:
    """
    `watch_for` keeps what it will do under `effects` and `promise` keeps its
    changes under `changes`. Both are lists or sets of their own, neither is a
    list of a named node shape, and both were clean before this and stay clean.
    """
    assert complaints(
        vocabulary,
        {
            "effect": "watch_for",
            "event": "after_roll",
            "conditions": [{"dice_equals": 1}],
            "effects": [{"draw_loot": 1}],
        },
    ) == []

    assert complaints(
        vocabulary,
        {
            "effect": "promise",
            "event": "roll_modified",
            "when": {"attack": True},
            "changes": {"value": {"flip": 7}},
        },
    ) == []


def test_a_body_key_with_no_head_is_still_refused(vocabulary: Vocabulary) -> None:
    """
    The rule the commit before this one added, unchanged by this one.
    """
    for key in ("effects", "then", "else", "modes"):
        said = wholly(vocabulary, {key: [{"gain_coins": 1}]})

        assert any(f"unknown effect '{key}'" in one for one in said), key


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
