"""
The monster deck is not only monsters.

COMPREHENSIVE_RULES.md §2 and §9 put the events and curses into it: they are
shuffled in with the monsters, a game is laid out with monsters alone in the
slots and the others put under the deck, and from then on whatever is revealed
where a monster would be is played — an event happens, a curse attaches.

Every game here is dealt and played the ordinary way. Nothing is put on top of
a deck by hand: each seed is one whose shuffle turns the card up by itself,
which is the point — these are the cards a real game meets. The seeds are
examples, not a definition; if the deal ever moves, the same kind of search
finds others.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pytest

import fsme.rules
from fsme.cards import CardInstance, CardType
from fsme.commands import Command, CommandType
from fsme.content import ContentLibrary, ContentLoader
from fsme.events import EventType
from fsme.game import Game
from fsme.lab.simulation import play_one
from fsme.runtime.vocabulary import engine_vocabulary
from fsme.state import GamePhase

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"

PLAYERS = ["Ann", "Bo"]

DECK_KINDS = (CardType.MONSTER, CardType.EVENT, CardType.CURSE)

BURIES_THREE = 9
"""A deal whose top cards hold three non-monsters before the slots are full."""

REFILL_REVEALS_AN_EVENT = 7
"""A deal with Chest on top of the monster deck once the game has started."""

REFILL_REVEALS_A_CURSE = 0
"""A deal with Curse of the Blind on top of the monster deck."""

ATTACK_REVEALS_AN_EVENT = 26
"""A deal with an event on top of the monster deck in the first action phase."""

A_WHOLE_GAME = 1
"""A game in which events are played and a curse is attached."""


@pytest.fixture(scope="module")
def base_game() -> ContentLibrary:
    library = ContentLoader(engine_vocabulary()).load_root(CONTENT_ROOT)

    only = ContentLibrary()
    only.add(library.get("base_game"))

    return only


def started(library: ContentLibrary, seed: int) -> tuple[Game, list[Any]]:
    """
    Deal and start a game, keeping every card that was played.
    """
    game = Game.from_content(library, PLAYERS, seed=seed, rng_model="2")

    played: list[Any] = []
    game.subscribe(EventType.ON_PLAY, played.append)

    game.start()

    assert game.runtime.awaiting_decision is None

    return game, played


def in_the_slots(game_or_state: Any) -> list[CardInstance]:
    state = getattr(game_or_state, "state", game_or_state)

    return [card for slot in state.monster_area for card in slot.cards]


def top_of_the_deck(game: Game) -> CardInstance:
    return game.state.monster_deck.cards[-1]


def next_monster_under(deck: list[CardInstance], card: CardInstance) -> CardInstance:
    """
    The first monster below a card, reading the deck from the top down.
    """
    below = deck[: deck.index(card)]

    return next(
        candidate
        for candidate in reversed(below)
        if candidate.definition.type is CardType.MONSTER
    )


def clear_a_slot(game: Game) -> CardInstance:
    """
    Discard the last monster standing, so the rules refill its slot.
    """
    monster = game.state.active_monsters.cards[-1]

    game.runtime.context.apply("discard_monsters", [monster])
    game.runtime.run()

    return monster


@pytest.mark.parametrize("seed", range(5))
def test_every_monster_event_and_curse_is_dealt_into_the_monster_deck(
    base_game: ContentLibrary, seed: int
) -> None:
    state = fsme.rules.new_game(base_game, PLAYERS, seed=seed, rng_model="2")

    printed = Counter(
        definition.id
        for definition in base_game.definitions()
        if definition.type in DECK_KINDS
    )

    dealt = Counter(
        card.definition.id
        for card in [*state.monster_deck.cards, *in_the_slots(state)]
    )

    assert dealt == printed
    assert any(card.definition.type is CardType.EVENT for card in state.monster_deck.cards)
    assert any(card.definition.type is CardType.CURSE for card in state.monster_deck.cards)

    # Laying out is not a turn: nothing has been played and nobody is cursed.
    assert not state.monster_discard.cards
    assert all(not player.curses.cards for player in state.players)


def test_the_slots_are_dealt_monsters_and_the_rest_goes_under_the_deck(
    base_game: ContentLibrary,
) -> None:
    """
    §2: the slots are filled from the top, and an event or curse turned over
    while filling them goes to the bottom of the deck.

    A deal with no slots turns nothing over, so it is the deck as shuffled; the
    same seed with slots is the same shuffle, laid out.
    """
    shuffled = fsme.rules.new_game(
        base_game, PLAYERS, seed=BURIES_THREE, rng_model="2", monster_slots=0
    )
    dealt = fsme.rules.new_game(base_game, PLAYERS, seed=BURIES_THREE, rng_model="2")

    slots = dealt.monster_slots

    from_the_top = list(reversed(shuffled.monster_deck.cards))

    monsters: list[str] = []
    buried: list[str] = []
    turned = 0

    for card in from_the_top:
        if len(monsters) == slots:
            break

        turned += 1

        if card.definition.type is CardType.MONSTER:
            monsters.append(card.instance_id)
        else:
            buried.append(card.instance_id)

    assert len(buried) == 3, "the seed still turns three non-monsters over"

    standing = in_the_slots(dealt)

    assert all(card.definition.type is CardType.MONSTER for card in standing)
    assert [card.instance_id for card in standing] == monsters

    deck = [card.instance_id for card in dealt.monster_deck.cards]
    untouched = [card.instance_id for card in reversed(from_the_top[turned:])]

    assert set(deck[: len(buried)]) == set(buried), "they went under the deck"
    assert deck[len(buried) :] == untouched, "the rest of the deck kept its order"


def test_a_refill_that_reveals_an_event_plays_it_and_fills_the_slot(
    base_game: ContentLibrary,
) -> None:
    game, played = started(base_game, REFILL_REVEALS_AN_EVENT)
    state = game.state

    event = top_of_the_deck(game)

    assert event.definition.type is CardType.EVENT

    deck = list(state.monster_deck.cards)
    replacement = next_monster_under(deck, event)
    active = state.turn.active_player

    clear_a_slot(game)

    assert [(each.source, each.controller) for each in played] == [(event, active)]
    assert event in state.monster_discard.cards
    assert event not in state.monster_deck.cards
    assert event not in in_the_slots(state)

    assert replacement in state.active_monsters.cards
    assert len(state.active_monsters) == state.monster_slots
    assert all(
        card.definition.type is CardType.MONSTER
        for card in state.active_monsters.cards
    )


def test_a_refill_that_reveals_a_curse_puts_it_on_the_active_player(
    base_game: ContentLibrary,
) -> None:
    """
    The rules do not say who a curse revealed from the deck goes to; the engine
    gives it to the active player. This pins that behaviour, not a rule.
    """
    game, _ = started(base_game, REFILL_REVEALS_A_CURSE)
    state = game.state

    curse = top_of_the_deck(game)

    assert curse.definition.type is CardType.CURSE

    deck = list(state.monster_deck.cards)
    replacement = next_monster_under(deck, curse)
    active = state.turn.active_player

    clear_a_slot(game)

    assert curse in state.player(active).curses.cards
    assert all(
        curse not in player.curses.cards
        for player in state.players
        if player.player_id != active
    )
    assert curse not in state.monster_deck.cards
    assert curse not in state.monster_discard.cards
    assert curse not in in_the_slots(state)

    assert replacement in state.active_monsters.cards
    assert len(state.active_monsters) == state.monster_slots


def test_attacking_the_deck_into_an_event_plays_it_and_ends_the_attack(
    base_game: ContentLibrary,
) -> None:
    """
    §7: the top card is revealed, and anything that is not a monster is played
    instead of fought; the attack is over and spent.
    """
    game, played = started(base_game, ATTACK_REVEALS_AN_EVENT)
    state = game.state

    active = state.turn.active_player

    assert game.submit(Command(type=CommandType.END_PHASE, player=active)).accepted
    assert state.turn.phase is GamePhase.ACTION

    event = top_of_the_deck(game)

    assert event.definition.type is CardType.EVENT

    standing = list(state.active_monsters.cards)
    played.clear()

    assert game.submit(
        Command(type=CommandType.ATTACK, player=active, payload={"source": "deck"})
    ).accepted

    assert [(each.source, each.controller) for each in played] == [(event, active)]
    assert event in state.monster_discard.cards
    assert event not in in_the_slots(state)

    assert state.combat.active is False
    assert state.player(active).can_attack() is False, "the attack was spent"
    assert state.active_monsters.cards == standing, "nothing joined the fight"


def test_a_whole_game_plays_the_events_and_curses_it_reveals(
    base_game: ContentLibrary,
) -> None:
    journal, game = play_one(base_game, A_WHOLE_GAME, 2, rng_model="2")

    kinds = {definition.id: definition.type for definition in base_game.definitions()}

    seen = Counter(
        (happening.type, kinds.get(happening.source_id))
        for entry in journal.entries
        for happening in entry.events
    )

    events_played = seen[("on_play", CardType.EVENT)]

    assert game.state.game_over
    assert events_played > 0
    assert seen[("stack_resolve", CardType.EVENT)] == events_played
    assert seen[("on_enter", CardType.CURSE)] > 0
