"""
Published cards, played in a published game.

test_official_content.py checks that the database survived the import. This
file checks the other half: that a card whose behaviour has been written by
hand actually does, in a real base game, what the printed card says.

Every card here is checked against its own English text, which the import kept
in ``metadata["text"]``. A card is only worth a test once somebody has read
that text and written the ability; guessing is how a set comes to look finished
while playing wrong.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fsme.cards import CardInstance
from fsme.commands import Command, CommandType
from fsme.content import ContentLibrary, ContentLoader
from fsme.game import Game
from fsme.runtime.vocabulary import engine_vocabulary
from fsme.state import DecisionKind

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def base_game() -> ContentLibrary:
    library = ContentLoader(engine_vocabulary()).load_root(CONTENT_ROOT)

    only = ContentLibrary()
    only.add(library.get("base_game"))

    return only


def new_game(base_game: ContentLibrary, players: int = 2, seed: int = 1234) -> Game:
    """
    Start a base game and get past the opening draw.
    """
    game = Game.from_content(base_game, ["Ann", "Bo", "Cy"][:players], seed=seed)

    assert game.start().accepted

    return game


def deal(game: Game, card_id: str, player: int = 0) -> CardInstance:
    """
    Put one named published card into a player's hand.

    Drawing until the wanted card turns up would make every test depend on the
    shuffle; naming the card keeps each test about the card.
    """
    definition = game.runtime.cards.get(card_id)

    card = CardInstance(
        definition=definition,
        instance_id=game.state.ids.allocate("loot"),
        controller=player,
        owner=player,
    )

    game.state.player(player).hand.add_top(card)

    return card


def play(game: Game, card: CardInstance, player: int = 0) -> Any:
    """
    Play a card out of the hand it is in.
    """
    index = list(game.state.player(player).hand.cards).index(card)

    return game.submit(
        Command(type=CommandType.PLAY_LOOT, player=player, payload={"index": index})
    )


def choose(game: Game, player: int, *indices: int) -> Any:
    return game.submit(
        Command(
            type=CommandType.CHOOSE_TARGET,
            player=player,
            payload={"choices": list(indices)},
        )
    )


def text_of(game: Game, card_id: str) -> str:
    return str(game.runtime.cards.get(card_id).metadata["text"])


# ----------------------------------------------------------------------
# Coins
# ----------------------------------------------------------------------

COIN_CARDS = (
    ("loot_deck-1-base_game-a_penny", 1),
    ("loot_deck-2-base_game-2_cents", 2),
    ("loot_deck-3-base_game-3_cents", 3),
    ("loot_deck-4-base_game-4_cents", 4),
    ("loot_deck-nickels-base_game-a_nickel", 5),
    ("loot_deck-nickels-base_game-a_dime", 10),
)


@pytest.mark.parametrize(("card_id", "cents"), COIN_CARDS)
def test_a_coin_card_pays_what_it_prints(
    base_game: ContentLibrary, card_id: str, cents: int
) -> None:
    game = new_game(base_game)
    before = game.state.player(0).pennies

    assert play(game, deal(game, card_id)).accepted
    assert game.state.player(0).pennies == before + cents


@pytest.mark.parametrize(("card_id", "cents"), COIN_CARDS)
def test_a_coin_card_pays_what_its_own_text_says(
    base_game: ContentLibrary, card_id: str, cents: int
) -> None:
    """
    The implementation is checked back to the published wording, so that a
    mistyped amount fails here rather than in somebody's game.
    """
    game = new_game(base_game)

    assert f"{cents}" in text_of(game, card_id)


def test_a_played_coin_card_leaves_the_hand(base_game: ContentLibrary) -> None:
    game = new_game(base_game)
    card = deal(game, "loot_deck-1-base_game-a_penny")

    assert play(game, card).accepted
    assert card not in game.state.player(0).hand.cards


# ----------------------------------------------------------------------
# Bombs
# ----------------------------------------------------------------------


def bomb_options(game: Game) -> list[Any]:
    decision = game.runtime.awaiting_decision

    assert decision is not None
    assert decision.kind is DecisionKind.CHOOSE_CARD
    assert decision.player == 0

    return list(decision.options)


@pytest.mark.parametrize(
    ("card_id", "damage"),
    (
        ("loot_deck-bombs-base_game-bomb", 1),
        ("loot_deck-bombs-base_game-gold_bomb", 3),
    ),
)
def test_a_bomb_damages_the_monster_it_is_thrown_at(
    base_game: ContentLibrary, card_id: str, damage: int
) -> None:
    game = new_game(base_game)

    assert play(game, deal(game, card_id)).accepted

    options = bomb_options(game)
    monster = game.state.active_monsters.cards[0]
    before = monster.hp

    assert before > damage, "pick a seed whose monster survives the bomb"

    assert choose(game, 0, options.index(monster)).accepted
    assert monster.hp == before - damage


def test_a_bomb_may_be_thrown_at_a_player(base_game: ContentLibrary) -> None:
    """
    "Deal 1 damage to a monster or player" is one choice on the card, so the
    engine asks once and offers both.
    """
    game = new_game(base_game)

    assert play(game, deal(game, "loot_deck-bombs-base_game-bomb")).accepted

    options = bomb_options(game)
    victim = game.state.player(1)
    before = victim.hp

    assert victim in options
    assert choose(game, 0, options.index(victim)).accepted
    assert victim.hp == before - 1


def test_a_bomb_offers_every_monster_and_every_living_player(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game, players=3)

    assert play(game, deal(game, "loot_deck-bombs-base_game-bomb")).accepted

    options = bomb_options(game)

    for player in game.state.living_players():
        assert player in options

    for monster in game.state.active_monsters.cards:
        assert monster in options


# ----------------------------------------------------------------------
# Batteries
# ----------------------------------------------------------------------


def test_lil_battery_recharges_a_tapped_item(base_game: ContentLibrary) -> None:
    game = new_game(base_game)

    item = game.state.player(0).treasures.cards[0]
    item.tapped = True

    assert play(game, deal(game, "loot_deck-batteries-base_game-lil_battery")).accepted

    decision = game.runtime.awaiting_decision

    assert decision is not None
    assert decision.kind is DecisionKind.CHOOSE_TREASURE

    assert choose(game, 0, list(decision.options).index(item)).accepted
    assert item.tapped is False


def test_lil_battery_may_recharge_an_opponent_s_item(base_game: ContentLibrary) -> None:
    """
    The card says "an item", not "your item", so an opponent's tapped item is
    a legal choice.
    """
    game = new_game(base_game)

    item = game.state.player(1).treasures.cards[0]
    item.tapped = True

    assert play(game, deal(game, "loot_deck-batteries-base_game-lil_battery")).accepted

    decision = game.runtime.awaiting_decision

    assert decision is not None
    assert item in decision.options

    assert choose(game, 0, list(decision.options).index(item)).accepted
    assert item.tapped is False


# ----------------------------------------------------------------------
# The implemented set as a whole
# ----------------------------------------------------------------------


def test_every_implemented_card_keeps_the_text_it_was_written_from(
    base_game: ContentLibrary,
) -> None:
    """
    A hand-written ability without its published wording cannot be reviewed,
    and an unreviewable card is one nobody can trust.
    """
    for definition in base_game.definitions():
        if not definition.abilities and not definition.statics:
            continue

        assert definition.metadata.get("text", "").strip(), definition.id


def test_the_engine_still_deals_the_same_game(base_game: ContentLibrary) -> None:
    """
    Teaching cards what they do must not disturb the deal: the same seed is
    still the same game.
    """

    def opening(seed: int) -> Any:
        state = Game.from_content(base_game, ["Ann", "Bo"], seed=seed).state

        return [card.id for card in state.loot_deck.cards]

    assert opening(2024) == opening(2024)
