"""
Decks that run out.

`COMPREHENSIVE_RULES.md` §9: "A deck that runs out is rebuilt by shuffling its
discard pile. This does not use the queue."

Two things in that sentence are load-bearing and are what this file is about.

*Runs out* is something a deck does — its last card leaves it — and not a state
it sits in. A deck rebuilt at the moment the last card leaves is a deck that is
already full when the next effect looks at it, and the next effect looking at
it is the whole point: a card that puts itself on the bottom of a deck it has
just emptied lands on top of a rebuilt deck, not on an empty table. A deck
rebuilt only when somebody next tries to draw would hand that card back
immediately, for ever.

*A deck* is all four of them. The loot deck used to be the only one that knew
how to come back, which made a rule about decks into a fact about one deck.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import make_definition, make_game, make_instance, make_state

from fsme.api import load_content
from fsme.cards import CardInstance, CardType
from fsme.commands import Command, CommandType
from fsme.content import ContentLibrary
from fsme.effects.builtin.decks import DECKS, deck_zone, discard_zone, draw_from
from fsme.events import EventType
from fsme.rng.rng import RNG
from fsme.runtime import Runtime

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


def card(name: str, kind: CardType = CardType.LOOT) -> CardInstance:
    """
    A card of a given type, with nothing printed on it that could interfere.
    """
    return CardInstance(
        definition=make_definition(f"test.{name}", card_type=kind),
        instance_id=f"card:{name}",
        controller=None,
        owner=None,
    )


KIND = {
    "loot": CardType.LOOT,
    "treasure": CardType.TREASURE,
    "monster": CardType.MONSTER,
    "room": CardType.ROOM,
}


def bare(deck: str, *, in_deck: int, in_discard: int):
    """
    A state with one deck and its discard stocked, and a context to act on it.

    Deliberately not a game: no players acting, no slots refilling, nothing
    that would draw a card out from under the assertion. The deck mechanic is
    what is under test, so the deck mechanic is all that runs.
    """
    state = make_state()
    kind = KIND[deck]

    for index in range(in_deck):
        deck_zone(state, deck).add_top(card(f"{deck}-deck-{index}", kind))

    for index in range(in_discard):
        discard_zone(state, deck).add_top(card(f"{deck}-discard-{index}", kind))

    runtime = Runtime(state, rng=RNG(state.seed))

    return runtime.context, state


# ----------------------------------------------------------------------
# The mechanism, on each of the four decks
# ----------------------------------------------------------------------


def test_the_last_card_out_rebuilds_the_deck_at_once() -> None:
    """
    Deck of one, discard of two: after the draw the deck holds two cards.

    Not "the next draw will find two". The deck is full again the moment the
    draw is over, because that is the moment it ran out.
    """
    for deck in DECKS:
        ctx, state = bare(deck, in_deck=1, in_discard=2)

        drawn = draw_from(ctx, deck)

        assert drawn is not None, deck
        assert len(deck_zone(state, deck).cards) == 2, deck
        assert not discard_zone(state, deck).cards, deck


def test_a_deck_that_is_not_empty_is_left_alone() -> None:
    """
    Drawing from a deck with cards left in it shuffles nothing.
    """
    for deck in DECKS:
        ctx, state = bare(deck, in_deck=3, in_discard=2)

        draw_from(ctx, deck)

        assert len(deck_zone(state, deck).cards) == 2, deck
        assert len(discard_zone(state, deck).cards) == 2, deck


def test_an_empty_deck_with_an_empty_discard_gives_nothing() -> None:
    """
    A legal position, not an error: nobody gets a card.
    """
    for deck in DECKS:
        ctx, state = bare(deck, in_deck=0, in_discard=0)

        assert draw_from(ctx, deck) is None, deck
        assert not deck_zone(state, deck).cards, deck


def test_a_draw_from_a_deck_that_ran_out_earlier_rebuilds_it() -> None:
    """
    The second way a deck comes back.

    A deck can run out while its discard is empty — there is nothing to rebuild
    it from, so it stays out. Cards arrive in the discard afterwards. Somebody
    then needs a card: they shuffle what there is and draw from it.
    """
    for deck in DECKS:
        ctx, state = bare(deck, in_deck=0, in_discard=3)

        drawn = draw_from(ctx, deck)

        assert drawn is not None, deck
        assert len(deck_zone(state, deck).cards) == 2, deck
        assert not discard_zone(state, deck).cards, deck


def test_a_rebuild_is_announced() -> None:
    """
    The order of a deck is most of what a player is guessing at, so the moment
    it is reshuffled is a thing that happened rather than bookkeeping.
    """
    runtime, state = make_game()

    state.loot_deck.cards.clear()
    state.loot_discard.add_top(card("spare"))

    draw_from(runtime.context, "loot")
    runtime.run()

    rebuilt = [
        event for event in runtime.history if event.type is EventType.DECK_REBUILT
    ]

    assert [event.payload.get("deck") for event in rebuilt] == ["loot"]


# ----------------------------------------------------------------------
# What the timing is for
# ----------------------------------------------------------------------


def test_a_card_put_on_the_bottom_of_a_deck_it_emptied_is_not_alone_there() -> None:
    """
    This is the whole reason the timing matters, and it is `XIX. The Sun`.

    "Put this on the bottom of the loot deck" resolves after the card has been
    drawn — and the draw is what emptied the deck. Rebuilt lazily, the deck at
    that moment is empty, the card is the only card in it, and the next loot
    step hands it straight back. Rebuilt when it ran out, the card goes under a
    full deck like any other.
    """
    ctx, state = bare("loot", in_deck=1, in_discard=5)

    sun = draw_from(ctx, "loot")

    assert sun is not None
    assert len(state.loot_deck.cards) == 5, "the deck was rebuilt as it emptied"

    ctx.apply("move_cards", [sun], deck="loot", position="bottom")

    assert state.loot_deck.cards[0] is sun
    assert len(state.loot_deck.cards) == 6
    assert state.loot_deck.cards[-1] is not sun, "it is not also the top card"


def test_taking_the_last_card_out_of_a_deck_rebuilds_it() -> None:
    """
    A deck runs out however its last card leaves — a search that takes it, a
    card that moves it somewhere — and not only when somebody draws.
    """
    ctx, state = bare("treasure", in_deck=1, in_discard=4)

    last = state.treasure_deck.cards[0]

    ctx.apply("take_card", [last], to="treasures", player=0)

    assert last in state.player(0).treasures.cards
    assert len(state.treasure_deck.cards) == 4
    assert not state.treasure_discard.cards


def test_moving_the_last_card_of_a_deck_away_rebuilds_it() -> None:
    """
    Moved to the discard of its own deck, which is the awkward one: the card
    leaves, the deck runs out, and the rebuild sweeps up the card that has just
    arrived in the discard along with everything else.
    """
    ctx, state = bare("monster", in_deck=1, in_discard=3)

    last = state.monster_deck.cards[0]

    ctx.apply("move_cards", [last], deck="monster", position="discard")

    assert len(state.monster_deck.cards) == 4
    assert last in state.monster_deck.cards
    assert not state.monster_discard.cards


def test_shuffling_an_empty_deck_does_not_rebuild_it() -> None:
    """
    Shuffling is not drawing and takes no card out, so nothing has run out.

    An empty deck beside a full discard pile is an ordinary position — it is
    what a deck that ran out with nothing to rebuild from looks like — and a
    shuffle is not the moment to change it.
    """
    ctx, state = bare("loot", in_deck=0, in_discard=4)

    ctx.apply("shuffle_deck", [], deck="loot")

    assert not state.loot_deck.cards
    assert len(state.loot_discard.cards) == 4


def test_revealing_the_top_of_an_empty_deck_does_not_rebuild_it() -> None:
    """
    Revealing shows what is there. When nothing is there it shows nothing.
    """
    ctx, state = bare("loot", in_deck=0, in_discard=4)

    revealed = ctx.apply("reveal_cards", [], deck="loot", count=2)

    assert revealed == []
    assert not state.loot_deck.cards
    assert len(state.loot_discard.cards) == 4


def test_a_card_discarded_beside_an_empty_deck_stays_in_the_discard() -> None:
    """
    A discard pile is not a deck waiting to happen.

    Nothing ran out here — the deck was already empty and no card left it — so
    the card that arrives in the discard stays in the discard. If it did not,
    a monster killed with the monster deck already out would be shuffled up and
    turned straight back over, which is not what anybody does.
    """
    ctx, state = bare("monster", in_deck=0, in_discard=0)

    corpse = card("corpse", CardType.MONSTER)

    ctx.apply("move_cards", [corpse], deck="monster", position="discard")

    assert state.monster_discard.cards == [corpse]
    assert not state.monster_deck.cards


# ----------------------------------------------------------------------
# The decks in a game
# ----------------------------------------------------------------------


def test_the_loot_step_keeps_drawing_after_the_deck_has_turned_over() -> None:
    """
    A loot deck small enough to run out during the game keeps producing cards.
    """
    runtime, state = make_game(loot_cards=3, players=2)

    ctx = runtime.context
    drawn = []

    for _ in range(12):
        card_drawn = draw_from(ctx, "loot")

        assert card_drawn is not None
        drawn.append(card_drawn)

        ctx.apply("move_cards", [card_drawn], deck="loot", position="discard")

    assert len({instance.instance_id for instance in drawn}) == 3


def test_a_treasure_deck_that_runs_out_still_fills_the_shop() -> None:
    """
    §9 again, on the shop: the slot refills, and the deck it refills from is
    rebuilt from the treasure discard when it has none left.
    """
    runtime, state = make_game(shop_items=0)

    state.treasure_deck.cards.clear()

    for index in range(3):
        state.treasure_discard.add_top(
            make_instance(
                make_definition(f"test.spent{index}", card_type=CardType.TREASURE),
                controller=None,
                owner=None,
                instance_id=f"treasure:spent{index}",
            )
        )

    runtime.submit(Command(type=CommandType.START_GAME, player=0))

    assert len(state.treasure_shop) == state.shop_slots


# ----------------------------------------------------------------------
# Whole games
# ----------------------------------------------------------------------

STUCK = (113, 137, 167, 251, 300, 727)
"""
The six seeds in a thousand that used to run for ever.

Every one of them was `XIX. The Sun` — "put this on the bottom of the loot
deck; if you do, take an extra turn" — played onto a loot deck that the draw
for it had just emptied. Lazily rebuilt, the deck held exactly that card, the
extra turn drew it again, and the game made no further progress for 7950 turns
until a step budget stopped it.

They are named here rather than described, because a named seed is a thing
somebody can run.
"""


@pytest.mark.parametrize("seed", STUCK)
def test_a_game_that_used_to_run_for_ever_finishes(
    everything: ContentLibrary, seed: int
) -> None:
    """
    No step budget, no cap on extra turns, no rule about repetition: the deck
    mechanic alone is what ends these.
    """
    from fsme.lab.simulation import play_one

    journal, game = play_one(
        everything, seed=seed, players=4, steps=20000, thinking_seats=(0, 1, 2, 3)
    )

    assert game.is_over, f"seed {seed} did not finish"
    assert len(journal.entries) < 2000, "and it did not take a suspicious while"


@pytest.mark.parametrize("seed", (113, 300))
def test_the_same_seed_still_deals_the_same_game(
    everything: ContentLibrary, seed: int
) -> None:
    """
    Rebuilding a deck shuffles it, and a shuffle is the engine RNG. So the fix
    moves what the RNG is asked for and when — which changes the games dealt,
    and must not change that a seed names one of them.

    Compared command for command and fingerprint for fingerprint, not on the
    winner and the length.
    """
    from fsme.lab.simulation import play_one

    runs = [
        play_one(
            everything, seed=seed, players=4, steps=20000, thinking_seats=(0, 1, 2, 3)
        )[0]
        for _ in range(3)
    ]

    first = runs[0]

    for other in runs[1:]:
        assert len(other.entries) == len(first.entries)

        for left, right in zip(first.entries, other.entries, strict=True):
            assert left.command == right.command
            assert left.player == right.player
            assert left.payload == right.payload
            assert left.digest == right.digest
            assert [event.type for event in left.events] == [
                event.type for event in right.events
            ]
