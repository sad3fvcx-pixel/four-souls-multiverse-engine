"""
The imported card database.

These tests check the import, not the engine: that the published cards are
present, that their printed numbers survived the conversion, and that a real
game can be laid out from them.

They deliberately do not check that cards *do* anything. Importing a card and
implementing it are different jobs, and conflating them is how a set comes to
look finished while playing wrong.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fsme.cards import CardType
from fsme.commands import CommandType
from fsme.content import ContentLibrary, ContentLoader
from fsme.database import ContentIndex
from fsme.game import Game
from fsme.runtime.vocabulary import engine_vocabulary

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def library() -> ContentLibrary:
    return ContentLoader(engine_vocabulary()).load_root(CONTENT_ROOT)


@pytest.fixture(scope="module")
def base_game(library: ContentLibrary) -> ContentLibrary:
    only = ContentLibrary()
    only.add(library.get("base_game"))

    return only


def test_the_whole_database_validates(library: ContentLibrary) -> None:
    assert len(library.definitions()) > 1000


def test_the_base_game_is_present(library: ContentLibrary) -> None:
    index = ContentIndex(library.get("base_game").definitions)

    for card_type in (
        CardType.CHARACTER,
        CardType.STARTING_ITEM,
        CardType.LOOT,
        CardType.TREASURE,
        CardType.MONSTER,
    ):
        assert index.by_type(card_type), card_type


def test_printed_numbers_survived_the_conversion(library: ContentLibrary) -> None:
    """
    Spot-checks against the published cards, chosen because their values are
    easy to look up and hard to get right by accident.
    """
    registry = library.registry()

    monstro = registry.get("monster_deck-bosses-base_game-monstro")

    assert monstro.type is CardType.MONSTER
    assert monstro.health == 4
    assert monstro.roll == 4
    assert monstro.attack == 1
    assert monstro.souls == 1
    assert monstro.rewards["cents"] == 6

    dip = registry.get("monster_deck-basic_enemies-base_game-dip")

    assert dip.health == 1
    assert dip.roll == 4
    assert dip.souls == 0
    assert dip.rewards["cents"] == 1

    isaac = registry.get("characters-base_game-isaac")

    assert isaac.type is CardType.CHARACTER
    assert isaac.health == 2
    assert isaac.metadata["starting_item"] == "starting_items-base_game-the_d6"


def test_the_monster_deck_holds_more_than_monsters(library: ContentLibrary) -> None:
    """
    Events and curses are shuffled into the monster deck and are not creatures
    with hit points, so they are not imported as monsters.
    """
    index = ContentIndex(library.definitions())

    events = index.by_type(CardType.EVENT)
    curses = index.by_type(CardType.CURSE)

    assert events
    assert curses
    assert all(card.health is None for card in events)


def test_eternal_items_are_marked(library: ContentLibrary) -> None:
    registry = library.registry()

    d6 = registry.get("starting_items-base_game-the_d6")

    assert d6.type is CardType.STARTING_ITEM
    assert d6.is_eternal is True
    assert "eternal" in d6.tags


def test_copies_are_counted_rather_than_repeated(library: ContentLibrary) -> None:
    """
    Fifteen printings of one loot card are one card the deck holds fifteen of,
    not fifteen cards.
    """
    registry = library.registry()

    penny = registry.get("loot_deck-1-base_game-a_penny")

    assert penny.metadata["copies"] > 1


def test_cards_that_differ_keep_separate_identities(library: ContentLibrary) -> None:
    """
    Several cards share a database identifier while having different rules
    text. Collapsing them would lose all but one.
    """
    registry = library.registry()

    first = registry.get("loot_deck-pills_runes-base_game-pills")
    second = registry.get("loot_deck-pills_runes-base_game-pills-v2")

    assert first.metadata["text"] != second.metadata["text"]


def test_the_original_card_text_is_kept(library: ContentLibrary) -> None:
    """
    The English text is what an implementation is written against, and what a
    reviewer checks it back to.
    """
    registry = library.registry()

    for card_id in (
        "treasure_deck-active_items-base_game-mr_boom",
        "monster_deck-bosses-base_game-monstro",
    ):
        assert registry.get(card_id).metadata["text"].strip()


def test_a_base_game_can_be_laid_out_and_played(base_game: ContentLibrary) -> None:
    game = Game.from_content(base_game, ["Ann", "Bo", "Cy"], seed=1234)
    state = game.state

    assert [player.character is not None for player in state.players] == [True] * 3
    assert all(player.treasure_count == 1 for player in state.players)
    assert len(state.active_monsters) == 2
    assert len(state.treasure_shop) == 2
    assert state.loot_deck.cards

    assert game.start().accepted
    assert all(player.hand_size == 3 for player in state.players)

    assert game.act(CommandType.END_PHASE, 0).accepted
    assert game.act(CommandType.ATTACK, 0, index=0).accepted


def test_the_same_seed_deals_the_same_official_game(base_game: ContentLibrary) -> None:
    def opening(seed: int):
        state = Game.from_content(base_game, ["Ann", "Bo"], seed=seed).state

        return (
            [player.character.id for player in state.players],
            [card.id for card in state.active_monsters.cards],
            [card.id for card in state.treasure_shop.cards],
        )

    assert opening(77) == opening(77)
    assert opening(77) != opening(78)
