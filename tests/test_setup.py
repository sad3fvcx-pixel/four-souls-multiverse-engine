"""
Laying out a game from loaded content.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fsme.cards import CardType
from fsme.commands import CommandType
from fsme.content import ContentLibrary, ContentLoader
from fsme.game import Game
from fsme.rules import SetupError, new_game
from fsme.runtime.vocabulary import engine_vocabulary

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


def library() -> ContentLibrary:
    return ContentLoader(engine_vocabulary()).load_root(CONTENT_ROOT)


def test_setup_deals_characters_and_their_starting_items() -> None:
    state = new_game(library(), ["Ann", "Bo"], seed=7)

    assert len(state.players) == 2

    for player in state.players:
        assert player.character is not None
        assert player.character.definition.type is CardType.CHARACTER
        assert player.hp == player.character.definition.health
        assert player.treasure_count == 1


def test_setup_fills_the_decks_and_the_board() -> None:
    state = new_game(library(), ["Ann", "Bo"], seed=7)

    assert state.loot_deck.cards
    assert state.monster_deck.cards or state.active_monsters.cards
    assert len(state.active_monsters) == 2
    assert len(state.treasure_shop) == 2


def test_the_same_seed_deals_the_same_opening() -> None:
    first = new_game(library(), ["Ann", "Bo"], seed=99)
    second = new_game(library(), ["Ann", "Bo"], seed=99)

    def opening(state):
        return (
            [player.character.id for player in state.players],
            [card.id for card in state.loot_deck.cards],
            [card.id for card in state.active_monsters.cards],
            [card.id for card in state.treasure_shop.cards],
        )

    assert opening(first) == opening(second)


def test_a_different_seed_deals_a_different_opening() -> None:
    first = new_game(library(), ["Ann", "Bo"], seed=1)
    second = new_game(library(), ["Ann", "Bo"], seed=2)

    assert [card.id for card in first.loot_deck.cards] != [
        card.id for card in second.loot_deck.cards
    ]


def test_every_card_instance_has_its_own_identifier() -> None:
    state = new_game(library(), ["Ann", "Bo", "Cy"], seed=3)

    identifiers = [card.instance_id for card in state.loot_deck.cards]
    identifiers += [card.instance_id for card in state.monster_deck.cards]
    identifiers += [card.instance_id for card in state.active_monsters.cards]

    assert len(set(identifiers)) == len(identifiers)


def test_a_game_without_players_is_refused() -> None:
    with pytest.raises(SetupError):
        new_game(library(), [], seed=1)


def test_more_players_than_characters_is_refused() -> None:
    small = ContentLibrary()
    small.add(library().get("engine_demo"))

    characters = len(small.cards_of(CardType.CHARACTER))

    with pytest.raises(SetupError) as error:
        new_game(small, [f"p{index}" for index in range(characters + 1)], seed=1)

    assert "characters" in str(error.value)


def test_content_without_loot_cannot_start_a_game() -> None:
    with pytest.raises(SetupError) as error:
        new_game(ContentLibrary(), ["Ann"], seed=1)

    assert "loot" in str(error.value)


def test_a_game_built_from_content_is_playable() -> None:
    """
    The whole path: a directory of card files becomes a game somebody plays.
    """
    game = Game.from_content(library(), ["Ann", "Bo"], seed=11)

    assert game.start().accepted

    # Three dealt each, and one more for the player whose turn it is.
    assert [player.hand_size for player in game.state.players] == [4, 3]

    assert game.act(CommandType.PLAY_LOOT, 0, index=0).accepted or (
        game.runtime.awaiting_decision is not None
    )


def test_a_content_game_reaches_the_action_phase_and_attacks() -> None:
    game = Game.from_content(library(), ["Ann", "Bo"], seed=5)

    game.start()

    assert game.act(CommandType.END_PHASE, 0).accepted
    assert game.act(CommandType.ATTACK, 0, index=0).accepted

    monster = game.state.active_monsters.cards[0]

    assert monster.hp is not None
