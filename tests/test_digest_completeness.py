"""
The fingerprint that covers what the rules read.

`state_digest` hashes the version 1 fingerprint, and every journal and
recording holds one. It leaves out things the rules read — how long an attack
has gone without a hit, what a stack object carries, whether it can be
cancelled, the counters on a card — so two different positions can share a
digest. `state_fingerprint_v2` leaves out only what is written down here as
left out, and this file holds it to that before anything is built on it.

Three things are checked against something other than the code under test:

- version 2 against a reference written here, which walks the field tables the
  slow, general way the fingerprint was first written, without the hand-written
  paths that make the real one fast enough;
- version 1 against a copy of it kept here, because records already written are
  checked against it and it must not move;
- the field tables against the dataclasses, so a field nobody has decided about
  is a failure rather than a silent omission.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
from collections import Counter
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pytest
from conftest import (
    loot_definition,
    make_instance,
    make_state,
    monster_definition,
    treasure_definition,
)

import fsme.journal.keeper as keeper
from fsme.api import load_content
from fsme.cards import CardDefinition, CardInstance, SoulToken
from fsme.content import ContentLibrary
from fsme.lab.simulation.runner import play_one
from fsme.replay import digest
from fsme.stack import StackItem, StackItemType
from fsme.state import CardModifier, GameState, PendingDecision, PlayerState
from fsme.state.decision import DecisionKind
from fsme.state.modifiers import Duration

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"

V1_OF_THE_FIXED_POSITION = "20d72a48edc7f3cbf68401219131844c"
"""What version 1 made of `a_fixed_position` before version 2 existed."""

SEEDS = range(20)
"""The games the replay gate's benchmark plays: four players, every seat thinking."""


# ----------------------------------------------------------------------
# Version 1, as it was
# ----------------------------------------------------------------------


def _frozen_card(card: Any) -> tuple[Any, ...]:
    return (
        getattr(card, "instance_id", ""),
        getattr(card, "id", ""),
        getattr(card, "hp", None),
        getattr(card, "alive", None),
        getattr(card, "tapped", None),
        getattr(card, "owner", None),
        getattr(card, "controller", None),
    )


def frozen_v1(state: GameState) -> str:
    """Version 1 of the digest, copied here so that it cannot move unnoticed."""
    def zone(cards: Any) -> tuple[Any, ...]:
        return tuple(_frozen_card(card) for card in cards)

    players = tuple(
        (
            player.player_id,
            player.hp,
            player.max_hp,
            player.pennies,
            player.alive,
            tuple(sorted(player.counters.items())),
            player.attacks_left,
            player.purchases_left,
            player.additional_loot_plays,
            zone(player.hand.cards),
            zone(player.treasures.cards),
            len(player.souls),
        )
        for player in state.players
    )

    fingerprint = (
        state.started,
        state.game_over,
        state.winner,
        state.turn.turn_number,
        state.turn.active_player,
        str(state.turn.phase),
        state.turn.loot_played,
        state.turn.attacks_declared,
        players,
        zone(state.active_monsters.cards),
        zone(state.treasure_shop.cards),
        len(state.loot_deck),
        len(state.loot_discard),
        len(state.monster_deck),
        len(state.monster_discard),
        len(state.treasure_deck),
        len(state.treasure_discard),
        len(state.stack),
        len(state.events),
        state.ids.counter,
        state.combat.attacker,
        state.combat.round_number,
        state.combat.active,
        state.priority.holder,
        state.priority.passes,
        state.priority.is_open,
        state.pending_decision.decision_id if state.pending_decision else "",
        repr(state.rng_state),
    )

    return hashlib.sha256(repr(fingerprint).encode("utf-8")).hexdigest()[:32]


# ----------------------------------------------------------------------
# Version 2, the slow general way
# ----------------------------------------------------------------------

HIDDEN = (
    "loot_deck",
    "loot_discard",
    "monster_deck",
    "monster_discard",
    "treasure_deck",
    "treasure_discard",
    "room_deck",
    "room_discard",
)
"""The piles whose untouched cards are written by identifier alone."""

FRESH = {
    field.name: (
        field.default_factory()  # type: ignore[misc]
        if field.default_factory is not dataclasses.MISSING
        else field.default
    )
    for field in dataclasses.fields(CardInstance)
    if field.name in digest.INCLUDED[CardInstance]
    and field.name not in ("instance_id", "definition", "hp")
}
"""How every included field of a card just made reads, health and identity aside."""


def reference_canon(value: Any) -> Any:
    kind = type(value)

    if value is None or kind in (str, int, bool, float):
        return value

    if isinstance(value, CardInstance):
        return ("card", value.instance_id)

    if isinstance(value, PlayerState):
        return ("player", value.player_id)

    if isinstance(value, StackItem):
        return ("stack", value.stack_id)

    if isinstance(value, SoulToken):
        return ("token", value.token_id)

    if isinstance(value, CardDefinition):
        return ("definition", value.id)

    if isinstance(value, enum.Enum):
        return reference_canon(value.value)

    for plain in (bool, str, int, float):
        if isinstance(value, plain):
            return plain(value)

    if isinstance(value, Mapping):
        pairs = [(reference_canon(key), reference_canon(item)) for key, item in value.items()]

        return ("map", tuple(sorted(pairs, key=lambda pair: repr(pair[0]))))

    if isinstance(value, (list, tuple)):
        return tuple(reference_canon(item) for item in value)

    if isinstance(value, (set, frozenset)):
        return ("set", tuple(sorted((reference_canon(item) for item in value), key=repr)))

    if kind in digest.INCLUDED:
        return reference_record(value)

    if (
        dataclasses.is_dataclass(value)
        and not isinstance(value, type)
        and kind.__dataclass_params__.frozen
    ):
        return (kind.__name__,) + tuple(
            reference_canon(getattr(value, field.name))
            for field in dataclasses.fields(value)
        )

    raise TypeError(kind.__name__)


def reference_card(card: Any) -> Any:
    return reference_record(card) if isinstance(card, CardInstance) else reference_canon(card)


def reference_cards(cards: Any) -> tuple[Any, ...]:
    return tuple(reference_card(card) for card in cards)


def untouched(card: Any) -> bool:
    return (
        isinstance(card, CardInstance)
        and card.hp == card.definition.health
        and all(getattr(card, name) == fresh for name, fresh in FRESH.items())
    )


def reference_pile(zone: Any) -> tuple[Any, ...]:
    return tuple(
        card.instance_id if untouched(card) else reference_card(card) for card in zone.cards
    )


OWNED: dict[tuple[type, str], Callable[[Any], Any]] = {
    (GameState, "players"): lambda players: tuple(reference_record(one) for one in players),
    (GameState, "monster_area"): lambda slots: tuple(
        reference_cards(slot.cards) for slot in slots
    ),
    (GameState, "treasure_shop"): lambda zone: reference_cards(zone.cards),
    (GameState, "bonus_souls"): lambda zone: reference_cards(zone.cards),
    (GameState, "room_area"): lambda zone: reference_cards(zone.cards),
    **{(GameState, name): reference_pile for name in HIDDEN},
    (GameState, "stack"): lambda stack: tuple(reference_record(item) for item in stack),
    (GameState, "events"): lambda events: tuple(reference_record(one) for one in events),
    (GameState, "ids"): lambda ids: ids.counter,
    (GameState, "rng_state"): lambda value: (
        value if value is None or type(value) is tuple else reference_canon(value)
    ),
    (PlayerState, "character"): reference_card,
    (PlayerState, "hand"): lambda zone: reference_cards(zone.cards),
    (PlayerState, "treasures"): lambda zone: reference_cards(zone.cards),
    (PlayerState, "souls"): lambda zone: reference_cards(zone.cards),
    (PlayerState, "curses"): lambda zone: reference_cards(zone.cards),
    (StackItem, "event"): lambda event: None if event is None else reference_record(event),
}
"""The fields that hold what they name: written in full, never as a pointer."""


def reference_record(value: Any) -> tuple[Any, ...]:
    kind = type(value)

    return (kind.__name__,) + tuple(
        (
            OWNED[(kind, name)](getattr(value, name))
            if (kind, name) in OWNED
            else reference_canon(getattr(value, name))
        )
        for name in digest.INCLUDED[kind]
    )


def reference_v2(state: GameState) -> tuple[Any, ...]:
    return (2,) + reference_record(state)


# ----------------------------------------------------------------------
# Every position of the benchmark's games
# ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


@pytest.fixture(scope="module")
def corpus(everything: ContentLibrary) -> Counter[str]:
    """
    Every position the keeper digests in the benchmark's games, each checked
    as it stands: positions change as a game goes on, so they are not kept.
    """
    seen: Counter[str] = Counter()
    keeping = keeper.state_digest

    def checked(state: GameState) -> str:
        made = repr(digest.state_fingerprint_v2(state))

        seen["positions"] += 1
        seen["v2 differs from the reference"] += made != repr(reference_v2(state))
        seen["v2 differs when made again"] += made != repr(digest.state_fingerprint_v2(state))
        seen["v1 moved"] += digest.state_digest(state) != frozen_v1(state)

        return keeping(state)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(keeper, "state_digest", checked)

        for seed in SEEDS:
            play_one(everything, seed, 4, steps=20000, thinking_seats=(0, 1, 2, 3))

    return seen


def test_the_benchmark_s_games_hold_thousands_of_positions(corpus: Counter[str]) -> None:
    assert corpus["positions"] > 5000


def test_version_2_is_what_the_reference_makes_at_every_position(
    corpus: Counter[str],
) -> None:
    assert corpus["v2 differs from the reference"] == 0, corpus


def test_version_2_is_the_same_when_made_again(corpus: Counter[str]) -> None:
    assert corpus["v2 differs when made again"] == 0, corpus


def test_version_1_has_not_moved_at_any_position(corpus: Counter[str]) -> None:
    assert corpus["v1 moved"] == 0, corpus


# ----------------------------------------------------------------------
# Version 1 is frozen
# ----------------------------------------------------------------------


def a_fixed_position() -> GameState:
    state = make_state(3, seed=7)
    state.started = True
    state.turn.turn_number = 4
    state.turn.active_player = 1
    state.turn.loot_played = 1
    state.turn.attacks_declared = 1

    first = state.player(0)
    first.pennies = 5
    first.hp = 1
    first.counters["poison"] = 2

    item = make_instance(treasure_definition(), instance_id="item:1")
    item.tapped = True
    first.treasures.add_top(item)

    state.player(1).hand.add_top(
        make_instance(loot_definition(), instance_id="loot:2", controller=1, owner=1)
    )

    monster = make_instance(
        monster_definition(), instance_id="monster:3", controller=None, owner=None
    )
    monster.hp = 1
    state.active_monsters.add_top(monster)

    for number in (4, 5):
        state.loot_deck.add_top(
            make_instance(
                loot_definition(), instance_id=f"loot:{number}", controller=None, owner=None
            )
        )

    state.ids.restore(10)
    state.combat.attacker = 0
    state.combat.round_number = 2
    state.combat.active = True
    state.priority.holder = 1
    state.priority.passes = 1
    state.priority.is_open = True
    state.rng_state = (3, tuple(range(625)), None)

    return state


def test_version_1_of_a_fixed_position_is_what_it_always_was() -> None:
    assert digest.state_digest(a_fixed_position()) == V1_OF_THE_FIXED_POSITION
    assert frozen_v1(a_fixed_position()) == V1_OF_THE_FIXED_POSITION


# ----------------------------------------------------------------------
# What version 1 cannot tell apart
# ----------------------------------------------------------------------


def a_table() -> GameState:
    """A position with a fight on, a stack object, an item in play and a pile."""
    state = make_state(2, seed=3)
    state.started = True
    state.rng_state = (3, tuple(range(625)), None)
    state.combat.attacker = 0
    state.combat.active = True

    state.player(0).treasures.add_top(make_instance(treasure_definition(), instance_id="item:1"))
    state.monster_deck.add_top(
        make_instance(monster_definition(), instance_id="monster:2", controller=None, owner=None)
    )
    state.stack.push(
        StackItem(
            kind=StackItemType.COMBAT,
            label="attack",
            payload={"source": "deck"},
            cancellable=False,
            stack_id="stack:5",
        )
    )

    return state


def the_item(state: GameState) -> CardInstance:
    card = state.player(0).treasures.cards[0]
    assert isinstance(card, CardInstance)

    return card


def the_stack_object(state: GameState) -> StackItem:
    return next(iter(state.stack))


COLLISIONS: dict[str, Callable[[GameState], None]] = {
    "an attack that has gone two rounds without a hit": lambda state: setattr(
        state.combat, "stalled_rounds", 2
    ),
    "a stack object carrying something else": lambda state: the_stack_object(
        state
    ).payload.update(source="slot"),
    "a stack object that can be cancelled": lambda state: setattr(
        the_stack_object(state), "cancellable", True
    ),
    "counters on a card": lambda state: the_item(state).counters.update(charge=1),
    "a modifier on a card": lambda state: the_item(state).modifiers.append(
        CardModifier(stat="attack", amount=1, duration=Duration.GAME)
    ),
}


@pytest.mark.parametrize("difference", sorted(COLLISIONS))
def test_version_2_tells_apart_what_version_1_cannot(difference: str) -> None:
    one, other = a_table(), a_table()
    COLLISIONS[difference](other)

    assert digest.state_digest(one) == digest.state_digest(other)
    assert digest.state_fingerprint_v2(one) != digest.state_fingerprint_v2(other)


# ----------------------------------------------------------------------
# A card in a pile is an identifier until anything about it changes
# ----------------------------------------------------------------------

PILE_AT = 2 + digest.INCLUDED[GameState].index("monster_deck")

CHANGES: dict[str, Callable[[CardInstance], None]] = {
    "hp": lambda card: setattr(card, "hp", 1),
    "owner": lambda card: setattr(card, "owner", 0),
    "controller": lambda card: setattr(card, "controller", 1),
    "tapped": lambda card: setattr(card, "tapped", True),
    "alive": lambda card: setattr(card, "alive", False),
    "counters": lambda card: card.counters.update(charge=1),
    "modifiers": lambda card: card.modifiers.append(
        CardModifier(stat="attack", amount=1, duration=Duration.GAME)
    ),
    "eternal": lambda card: setattr(card, "eternal", True),
    "copy_of": lambda card: setattr(card, "copy_of", loot_definition("test.other")),
    "copy_expires": lambda card: setattr(card, "copy_expires", "end_of_turn"),
    "silenced_while": lambda card: setattr(card, "silenced_while", "poo"),
    "recharge_skipped": lambda card: setattr(card, "recharge_skipped", True),
    "last_damaged_by": lambda card: setattr(card, "last_damaged_by", 1),
}


def a_pile(change: Callable[[CardInstance], None] | None = None) -> GameState:
    state = make_state(2, seed=3)
    state.rng_state = (3, tuple(range(625)), None)

    monster = make_instance(
        monster_definition(health=2), instance_id="monster:7", controller=None, owner=None
    )
    state.monster_deck.add_top(monster)
    state.monster_deck.add_top(
        make_instance(loot_definition(), instance_id="loot:8", controller=None, owner=None)
    )

    if change is not None:
        change(monster)

    return state


def test_every_field_of_a_card_but_its_identity_is_looked_at() -> None:
    looked_at = set(digest.INCLUDED[CardInstance]) - {"instance_id", "definition"}

    assert set(CHANGES) == looked_at


def test_untouched_cards_in_a_pile_are_their_identifiers() -> None:
    assert digest.state_fingerprint_v2(a_pile())[PILE_AT] == ("monster:7", "loot:8")


@pytest.mark.parametrize("field", sorted(CHANGES))
def test_a_card_in_a_pile_changed_in_any_field_is_written_in_full(field: str) -> None:
    untouched_pile = digest.state_fingerprint_v2(a_pile())
    changed = digest.state_fingerprint_v2(a_pile(CHANGES[field]))

    written = changed[PILE_AT]

    assert isinstance(written[0], tuple)
    assert written[0][:2] == ("CardInstance", "monster:7")
    assert written[1] == "loot:8"
    assert changed != untouched_pile
    assert repr(changed) == repr(reference_v2(a_pile(CHANGES[field])))


@pytest.mark.parametrize("field", sorted(CHANGES))
def test_a_card_in_play_changed_in_any_field_changes_the_fingerprint(field: str) -> None:
    one, other = a_table(), a_table()
    the_item(other).owner = None  # so that "owner" below is a change for this card too
    the_item(one).owner = None
    CHANGES[field](the_item(other))

    assert digest.state_fingerprint_v2(one) != digest.state_fingerprint_v2(other)


# ----------------------------------------------------------------------
# Order where it means something, and only there
# ----------------------------------------------------------------------


def test_a_mapping_is_the_same_whatever_order_it_was_filled_in() -> None:
    one, other = a_table(), a_table()
    the_item(one).counters.update(charge=1, poo=2)
    the_item(other).counters.update(poo=2, charge=1)
    one.turn.triggers_fired.update(a=1, b=2)
    other.turn.triggers_fired.update(b=2, a=1)

    assert list(the_item(one).counters) != list(the_item(other).counters)
    assert repr(digest.state_fingerprint_v2(one)) == repr(digest.state_fingerprint_v2(other))


def test_a_set_is_written_in_one_order_whatever_order_it_holds() -> None:
    written = digest._canon({"b", "a", "c"})

    assert written == ("set", ("a", "b", "c"))
    assert digest._canon(frozenset(["c", "a", "b"])) == written


def test_the_order_of_a_pile_is_part_of_the_position() -> None:
    one, other = a_pile(), a_pile()
    other.monster_deck.cards.reverse()

    assert digest.state_fingerprint_v2(one) != digest.state_fingerprint_v2(other)


def test_a_card_is_its_definition_s_identifier_not_the_definition() -> None:
    one, other = a_table(), a_table()
    printed = the_item(other).definition
    the_item(other).definition = dataclasses.replace(printed, name="Another Name")

    assert the_item(other).definition is not the_item(one).definition
    assert digest.state_fingerprint_v2(one) == digest.state_fingerprint_v2(other)


# ----------------------------------------------------------------------
# Positions a save would refuse, and things nobody said how to write
# ----------------------------------------------------------------------


def test_a_position_waiting_on_a_question_has_a_fingerprint() -> None:
    """A save refuses this position; the fingerprint is taken after every command."""
    one, other = a_table(), a_table()

    for state, options in ((one, [0, 1]), (other, [1])):
        state.pending_decision = PendingDecision(
            decision_id="decision:1",
            player=0,
            kind=DecisionKind.CHOOSE_PLAYER,
            options=list(options),
            prompt="Choose a player.",
        )

    assert digest.state_fingerprint_v2(one) != digest.state_fingerprint_v2(other)

    assert one.pending_decision is not None and other.pending_decision is not None
    other.pending_decision.options = [0, 1]
    other.pending_decision.prompt = "Pick someone."

    assert digest.state_fingerprint_v2(one) == digest.state_fingerprint_v2(other)


class Unwritten:
    """A value nothing has said how to write."""

    def __repr__(self) -> str:
        return "a perfectly good value"


@pytest.mark.parametrize("thing", [object(), Unwritten()], ids=["object", "with a repr"])
def test_a_value_nobody_said_how_to_write_is_refused(thing: Any) -> None:
    state = a_table()
    the_stack_object(state).payload["what"] = thing

    with pytest.raises(TypeError) as refused:
        digest.state_fingerprint_v2(state)

    assert "0x" not in str(refused.value)
    assert "a perfectly good value" not in str(refused.value)


# ----------------------------------------------------------------------
# Every field is decided about
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind", sorted(digest.INCLUDED, key=lambda kind: kind.__name__), ids=lambda kind: kind.__name__
)
def test_every_field_is_either_in_the_fingerprint_or_left_out_for_a_reason(
    kind: type,
) -> None:
    fields = {field.name for field in dataclasses.fields(kind)}
    included = set(digest.INCLUDED[kind])
    excluded = {name for (owner, name) in digest.EXCLUDED if owner is kind}

    assert included | excluded == fields
    assert not included & excluded
    assert len(included) == len(digest.INCLUDED[kind])
    assert all(digest.EXCLUDED[(kind, name)].strip() for name in excluded)


def test_nothing_is_left_out_of_a_type_the_fingerprint_does_not_know() -> None:
    assert {owner for (owner, _) in digest.EXCLUDED} <= set(digest.INCLUDED)
