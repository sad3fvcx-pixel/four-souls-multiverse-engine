"""
Where the three layers have to agree about the same card.

An Author UI that offers something, a validator that accepts it and a runtime
that refuses it is three layers telling a person three different things, and
the person finds out last. Worse is the silent version: everybody agrees the
card is fine and the game quietly plays a different card from the one written.

These tests are about the contracts, not about the page. They build a card the
way the page builds one, check it with the checker the loader uses, and — where
it matters most — play it in a real game.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fsme.api import load_content
from fsme.content.vocabulary import CARDS, PLAYERS
from fsme.effects import builtin_registry
from fsme.lab.desk import Workbench
from fsme.lab.desk.author import build_card, check_card
from fsme.runtime.target_resolver import TargetResolver

CONTENT = Path(__file__).resolve().parents[1] / "content"

UNPROVABLE = ("mixed", "passthrough", "")
"""
What a target may hand back that says nothing about its kind — the same three
the checker refuses to judge and the page therefore still offers.
"""


@pytest.fixture(scope="module")
def everything() -> Any:
    return load_content(CONTENT)


@pytest.fixture
def bench(everything: Any, tmp_path: Path) -> Workbench:
    return Workbench(everything, CONTENT, tmp_path / "work")


def a_card(effects: list[dict[str, Any]], **card: Any) -> dict[str, Any]:
    return build_card(
        {
            "set": "demo",
            "card": {
                "fields": {
                    "name": "Under Test",
                    "type": "loot",
                    "abilities": [
                        {"fields": {"trigger": "on_play", "effects": effects}}
                    ],
                    **card,
                },
                "groups": {},
            },
        }
    )


def aimed(effect: str, target: str) -> dict[str, Any]:
    return {"id": effect, "fields": {}, "aim": target, "aim_fields": {}}


ROLL = {"id": "roll_dice", "fields": {}}


def _raw(effect: str, target: str) -> dict[str, Any]:
    """
    One aimed effect, written the way a card file writes it.

    Straight to the shape the checker reads, because the loop below runs two
    thousand of these and `build_card` asks the engine what it can do every
    time it is called.
    """
    return {
        "id": "probe",
        "name": "Probe",
        "type": "loot",
        "expansion": "demo",
        "abilities": [
            {
                "trigger": "on_play",
                "effects": [{"effect": effect, "target": target}],
            }
        ],
    }


def _checked(card: dict[str, Any]) -> list[str]:
    """
    `check_card` without rebuilding the whole vocabulary for every card.

    Two thousand cards go through the loop below; asking the engine what it can
    do two thousand times is a minute of the suite spent on one answer.
    """
    from fsme.cards import validate_card

    vocabulary = _vocabulary()

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


_KNOWN: list[Any] = []


def _vocabulary() -> Any:
    from fsme.runtime.vocabulary import engine_vocabulary

    if not _KNOWN:
        _KNOWN.append(engine_vocabulary())

    return _KNOWN[0]


def coins_from(name: str) -> dict[str, Any]:
    return {"id": "gain_coins", "fields": {"amount": {"from": name}}}


# ----------------------------------------------------------------------
# A value the ability never stored
# ----------------------------------------------------------------------


def test_reading_a_value_nothing_stores_is_refused() -> None:
    """
    It used to validate, play, and gain nothing — the worst kind of mistake,
    because the card looked right and said so to nobody.
    """
    said = check_card(a_card([coins_from("dice")]))

    assert said
    assert "'dice' is not a value this ability stores" in said[0]


def test_reading_a_value_before_the_step_that_stores_it_is_refused() -> None:
    said = check_card(a_card([coins_from("dice"), ROLL]))

    assert said, "a value read above the roll that makes it"


def test_reading_a_value_after_the_step_that_stores_it_is_fine() -> None:
    assert check_card(a_card([ROLL, coins_from("dice")])) == []


def test_a_misspelled_value_is_refused_and_the_right_name_offered() -> None:
    (said,) = check_card(a_card([ROLL, coins_from("dcie")]))

    assert "'dcie'" in said
    assert "did you mean 'dice'" in said


def test_a_value_one_ability_stores_is_not_readable_by_another() -> None:
    """
    The engine builds one context per ability and they share nothing, so this
    could never have worked. Nothing said so until now.
    """
    card = build_card(
        {
            "set": "demo",
            "card": {
                "fields": {
                    "name": "Two",
                    "type": "loot",
                    "abilities": [
                        {"fields": {"trigger": "on_play", "effects": [ROLL]}},
                        {
                            "fields": {
                                "trigger": "turn_start",
                                "effects": [coins_from("dice")],
                            }
                        },
                    ],
                },
                "groups": {},
            },
        }
    )

    assert check_card(card), "one ability read what another stored"


def test_naming_a_group_nothing_binds_is_refused() -> None:
    """
    `player_of` names a group the way `from` names a value. It used to reach
    the resolver, which answered nothing, and the arithmetic then raised a
    TypeError at the author.
    """
    said = check_card(
        a_card([{"id": "gain_coins", "fields": {"amount": {"player_of": "nobody"}}}])
    )

    assert said
    assert "'nobody'" in said[0]


def test_a_value_worked_out_without_naming_anything_is_still_fine() -> None:
    """
    Only the heads that name something are references. Counting and reading the
    event name nothing, and refusing them would refuse correct cards.
    """
    for head in ({"count": "coins"}, {"from_event": "amount"}, {"last_result": True}):
        card = a_card([{"id": "gain_coins", "fields": {"amount": head}}])

        assert check_card(card) == [], head


# ----------------------------------------------------------------------
# What an effect acts on
# ----------------------------------------------------------------------


def test_every_effect_that_restricts_its_targets_says_so() -> None:
    """
    The declaration is the point: a guard written inside a handler is an answer
    nothing else can read, which is how a treasure came to be offered to an
    effect that takes players.
    """
    registry = builtin_registry()
    declared = {
        name: registry.spec(name).hits
        for name in registry.names()
        if registry.spec(name).hits
    }

    assert declared, "no effect declares what it acts on"
    assert set(declared.values()) <= {PLAYERS, CARDS}
    assert declared["steal_soul"] == PLAYERS
    assert declared["recharge"] == CARDS

    for name in declared:
        assert registry.spec(name).needs_target, (
            f"{name} says what it acts on and does not act on anything"
        )


def test_a_declared_kind_is_enforced_when_the_card_is_played(
    bench: Workbench,
) -> None:
    """
    End to end, through the path the page uses: build, check, play.
    """
    refused = a_card([aimed("steal_soul", "target_treasure")])

    assert check_card(refused), "a soul stolen from a treasure"

    allowed = a_card([aimed("steal_soul", "target_player")])

    assert check_card(allowed) == []

    bench.show_card(allowed)


def test_an_effect_that_acts_on_cards_refuses_a_player() -> None:
    for effect in ("recharge", "put_into_play", "make_eternal"):
        said = check_card(a_card([aimed(effect, "controller")]))

        assert said, f"{effect} was aimed at a player"
        assert "acts on cards" in said[0], said


def test_an_effect_that_acts_on_players_refuses_a_card() -> None:
    for effect in ("gain_coins", "draw_loot", "skip_next_turn"):
        said = check_card(a_card([aimed(effect, "target_monster")]))

        assert said, f"{effect} was aimed at a card"
        assert "acts on players" in said[0], said


def test_the_engine_itself_refuses_a_target_of_the_wrong_kind() -> None:
    """
    The declaration has to be enforced where the effect actually runs, not only
    where cards are checked. A card file written by hand never goes through the
    Author UI, and a check that lives only in the checker is a check a card can
    walk around.
    """
    from fsme.runtime.effect_executor import _the_right_kind
    from fsme.state import PlayerState

    class ACard:
        name = "a card"

    players = builtin_registry().spec("steal_soul")
    cards = builtin_registry().spec("recharge")
    seat = PlayerState(player_id=0, name="You")

    # The kind each says it acts on goes through without complaint.
    _the_right_kind(players, [seat])
    _the_right_kind(cards, [ACard()])

    # The other kind does not.
    with pytest.raises(Exception) as refused:
        _the_right_kind(players, [ACard()])

    assert "acts on players" in str(refused.value)

    with pytest.raises(Exception) as other:
        _the_right_kind(cards, [seat])

    assert "acts on cards" in str(other.value)


def test_an_effect_that_says_nothing_is_handed_anything() -> None:
    """
    Silence is not a restriction. Ten effects genuinely act on both, and a
    guard that refused them would take away cards that work today.
    """
    from fsme.runtime.effect_executor import _the_right_kind
    from fsme.state import PlayerState

    class ACard:
        name = "a card"

    spec = builtin_registry().spec("destroy_treasure")

    assert not spec.hits

    _the_right_kind(spec, [PlayerState(player_id=0, name="You"), ACard()])


def test_what_an_earlier_step_chose_is_still_offered() -> None:
    """
    A target that hands back whatever it was given cannot be judged before a
    game exists. "Deal damage, then destroy what you damaged" is a real card
    and must not be refused for being unprovable.
    """
    for target in ("previous_target", "group", "most_common"):
        card = a_card([aimed("gain_coins", target)])
        said = [one for one in check_card(card) if "acts on" in one]

        assert said == [], f"{target} was judged"


def test_the_page_offers_exactly_what_the_checker_accepts() -> None:
    """
    The invariant this whole area exists for.

    Whatever the page offers for an effect, the checker must accept — and
    whatever the checker accepts, the page must offer. One rule, read by both:
    the page's `fits` and the checker's `_acts_on` are the same sentence.
    """
    registry = builtin_registry()
    shapes = TargetResolver().shapes()

    for name in sorted(registry.names()):
        spec = registry.spec(name)

        if not spec.needs_target:
            continue

        for target, shape in shapes.items():
            offered = not spec.hits or shape.yields in UNPROVABLE or (
                shape.yields == spec.hits
            )
            complained = [
                one
                for one in _checked(_raw(name, target))
                if "acts on" in one
            ]

            assert offered == (not complained), (
                f"{name} aimed at {target}: page offers={offered}, "
                f"checker complains={bool(complained)}"
            )


def test_the_page_filters_the_aim_by_what_the_effect_acts_on() -> None:
    page = (
        Path(__file__).resolve().parents[1]
        / "src/fsme/lab/desk/static/author.html"
    ).read_text("utf-8")

    assert "fits(t, chosen.hits)" in page
    assert 'const EITHER = ["mixed", "passthrough", ""];' in page


# ----------------------------------------------------------------------
# What the author is told when the engine does refuse
# ----------------------------------------------------------------------


def test_a_refusal_names_the_card_rather_than_printing_it(
    bench: Workbench,
) -> None:
    """
    `deal_damage` is narrower than the two kinds this layer can say — it needs
    something with hit points — so a loot card aimed at itself still reaches
    the engine. What it must not do is answer with eight hundred characters of
    dataclass.
    """
    from fsme.lab.desk.author import said_by_the_engine

    card = a_card([{**aimed("deal_damage", "self"), "fields": {"amount": 1}}])

    assert check_card(card) == []

    with pytest.raises(Exception) as refused:
        bench.show_card(card)

    said = said_by_the_engine(refused.value)

    assert "'Under Test' has no hit points" in said
    assert len(said) < 120, said
    assert "CardDefinition" not in said


# ----------------------------------------------------------------------
# Nothing that already works may stop working
# ----------------------------------------------------------------------


def test_every_shipped_card_still_passes_the_checker(everything: Any) -> None:
    """
    The checks above only ever refuse more than they used to. This is what
    says they refuse nothing that was already right.
    """
    from fsme.cards import validate_card
    from fsme.runtime.vocabulary import engine_vocabulary

    vocabulary = engine_vocabulary()
    broken: list[str] = []

    for definition in everything.definitions():
        raw = {
            "id": definition.id,
            "name": definition.name,
            "type": str(definition.type),
            "expansion": definition.expansion,
            "abilities": [_plain(one) for one in definition.abilities],
        }
        said = validate_card(
            raw,
            known_effects=vocabulary.effects,
            known_triggers=vocabulary.triggers,
            known_conditions=vocabulary.conditions,
            known_targets=vocabulary.targets,
            shapes=vocabulary.shapes,
            condition_shapes=vocabulary.condition_shapes,
            target_shapes=vocabulary.target_shapes,
            node_shapes=vocabulary.node_shapes,
        )

        if said:
            broken.append(f"{definition.id}: {said[0]}")

    assert broken == [], broken[:5]


def _plain(ability: Any) -> dict[str, Any]:
    written: dict[str, Any] = {"trigger": ability.trigger}

    for key in ("conditions", "targets", "effects"):
        value = getattr(ability, key)

        if value:
            written[key] = _unfrozen(value)

    if ability.cost:
        written["cost"] = _unfrozen(ability.cost)

    for key in ("optional", "replacement", "zone", "description"):
        value = getattr(ability, key)

        if value:
            written[key] = value

    if ability.scope:
        written["scope"] = ability.scope

    return written


def _unfrozen(value: Any) -> Any:
    from collections.abc import Mapping

    if isinstance(value, Mapping):
        return {key: _unfrozen(one) for key, one in value.items()}

    if isinstance(value, (list, tuple)):
        return [_unfrozen(one) for one in value]

    return value
