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

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from test_combat import FixedRNG

from fsme.cards import CardInstance
from fsme.commands import Command, CommandType
from fsme.content import ContentLibrary, ContentLoader
from fsme.events import EventType
from fsme.game import Game
from fsme.runtime.vocabulary import engine_vocabulary
from fsme.state import DecisionKind, GamePhase

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def base_game() -> ContentLibrary:
    library = ContentLoader(engine_vocabulary()).load_root(CONTENT_ROOT)

    only = ContentLibrary()
    only.add(library.get("base_game"))

    return only


def new_game(
    base_game: ContentLibrary,
    players: int = 2,
    seed: int = 1234,
    rolls: list[int] | None = None,
) -> Game:
    """
    Start a base game and get past the opening draw.

    ``rolls`` scripts the dice. A card that says "roll" has one behaviour per
    face, and a test that hopes for the face it wants is a test that checks one
    sixth of the card.
    """
    game = Game.from_content(
        base_game,
        ["Ann", "Bo", "Cy"][:players],
        seed=seed,
        rng=FixedRNG(rolls) if rolls is not None else None,
    )

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


@dataclass(frozen=True)
class Snapshot:
    """
    What a player looked like before a card was played.
    """

    hp: int
    pennies: int
    hand_size: int
    treasure_count: int


def snapshot(player: Any) -> Snapshot:
    return Snapshot(
        hp=player.hp,
        pennies=player.pennies,
        hand_size=player.hand_size,
        treasure_count=player.treasure_count,
    )


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
# Treasure and death
# ----------------------------------------------------------------------


def test_the_stars_takes_a_treasure_from_the_deck(base_game: ContentLibrary) -> None:
    game = new_game(base_game)

    before = game.state.player(0).treasure_count
    deck = len(game.state.treasure_deck)

    assert play(game, deal(game, "loot_deck-cards_miscellaneous-base_game-xvii_the_stars")).accepted

    assert game.state.player(0).treasure_count == before + 1
    assert len(game.state.treasure_deck) == deck - 1


def test_death_kills_the_player_it_chooses(base_game: ContentLibrary) -> None:
    game = new_game(base_game, players=3)

    assert play(game, deal(game, "loot_deck-cards_miscellaneous-base_game-xiii_death")).accepted

    decision = game.runtime.awaiting_decision

    assert decision is not None
    assert decision.kind is DecisionKind.CHOOSE_PLAYER

    victim = game.state.player(2)

    assert choose(game, 0, list(decision.options).index(victim)).accepted
    assert victim.hp == 0 or not victim.alive


# ----------------------------------------------------------------------
# Cards that roll
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("roll", "check"),
    (
        (1, lambda game, before: game.state.player(0).pennies == before.pennies + 1),
        (2, lambda game, before: game.state.player(0).hp == before.hp - 2),
        (3, lambda game, before: game.state.player(0).hand_size == before.hand_size + 3),
        (4, lambda game, before: game.state.player(0).pennies == max(0, before.pennies - 4)),
        (5, lambda game, before: game.state.player(0).pennies == before.pennies + 5),
        (
            6,
            lambda game, before: game.state.player(0).treasure_count
            == before.treasure_count + 1,
        ),
    ),
)
def test_the_wheel_of_fortune_has_six_different_faces(
    base_game: ContentLibrary, roll: int, check: Any
) -> None:
    """
    Every face of the die is a different card, so every face is checked.
    """
    game = new_game(base_game, rolls=[roll])
    before = snapshot(game.state.player(0))

    assert play(
        game, deal(game, "loot_deck-cards_miscellaneous-base_game-x_wheel_of_fortune")
    ).accepted

    assert check(game, before)


@pytest.mark.parametrize("roll", (1, 2))
def test_the_tower_hurts_every_player_on_a_low_roll(
    base_game: ContentLibrary, roll: int
) -> None:
    game = new_game(base_game, players=3, rolls=[roll])
    before = [player.hp for player in game.state.players]

    assert play(
        game, deal(game, "loot_deck-cards_miscellaneous-base_game-xvi_the_tower")
    ).accepted

    assert [player.hp for player in game.state.players] == [hp - 1 for hp in before]


@pytest.mark.parametrize("roll", (3, 4))
def test_the_tower_hurts_every_monster_in_the_middle(
    base_game: ContentLibrary, roll: int
) -> None:
    game = new_game(base_game, players=3, rolls=[roll])

    monsters = list(game.state.active_monsters.cards)
    before = [monster.hp for monster in monsters]
    players = [player.hp for player in game.state.players]

    assert play(
        game, deal(game, "loot_deck-cards_miscellaneous-base_game-xvi_the_tower")
    ).accepted

    assert [monster.hp for monster in monsters] == [hp - 1 for hp in before]
    assert [player.hp for player in game.state.players] == players


@pytest.mark.parametrize("roll", (5, 6))
def test_the_tower_hurts_every_player_twice_on_a_high_roll(
    base_game: ContentLibrary, roll: int
) -> None:
    game = new_game(base_game, players=3, rolls=[roll])
    before = [player.hp for player in game.state.players]

    assert play(
        game, deal(game, "loot_deck-cards_miscellaneous-base_game-xvi_the_tower")
    ).accepted

    assert [player.hp for player in game.state.players] == [
        max(0, hp - 2) for hp in before
    ]


@pytest.mark.parametrize(
    ("roll", "coins", "loot", "damage"),
    (
        (1, 1, 0, 0),
        (2, 0, 2, 0),
        (3, 0, 0, 3),
        (4, 4, 0, 0),
        (5, 0, 5, 0),
        (6, 6, 0, 0),
    ),
)
def test_the_blank_rune_treats_every_player_alike(
    base_game: ContentLibrary, roll: int, coins: int, loot: int, damage: int
) -> None:
    game = new_game(base_game, players=3, rolls=[roll])

    before = [snapshot(player) for player in game.state.players]

    assert play(game, deal(game, "loot_deck-pills_runes-base_game-blank_rune")).accepted

    for player, was in zip(game.state.players, before, strict=True):
        assert player.pennies == was.pennies + coins
        assert player.hp == max(0, was.hp - damage)
        assert player.hand_size == was.hand_size + loot


@pytest.mark.parametrize(
    ("roll", "gained", "lost"),
    ((1, 4, 0), (2, 4, 0), (3, 7, 0), (4, 7, 0), (5, 0, 4), (6, 0, 4)),
)
def test_the_first_pills_pay_or_charge(
    base_game: ContentLibrary, roll: int, gained: int, lost: int
) -> None:
    game = new_game(base_game, rolls=[roll])

    game.state.player(0).pennies = 10

    assert play(game, deal(game, "loot_deck-pills_runes-base_game-pills")).accepted
    assert game.state.player(0).pennies == 10 + gained - lost


@pytest.mark.parametrize(("roll", "drawn"), ((1, 1), (2, 1), (3, 3), (4, 3)))
def test_the_second_pills_draw(
    base_game: ContentLibrary, roll: int, drawn: int
) -> None:
    game = new_game(base_game, rolls=[roll])

    before = game.state.player(0).hand_size

    assert play(game, deal(game, "loot_deck-pills_runes-base_game-pills-v2")).accepted

    # The card that was played left the hand it was added to, so the count is
    # measured from before it was dealt.
    assert game.state.player(0).hand_size == before + drawn


@pytest.mark.parametrize("roll", (5, 6))
def test_the_second_pills_make_you_discard_on_a_high_roll(
    base_game: ContentLibrary, roll: int
) -> None:
    game = new_game(base_game, rolls=[roll])

    before = game.state.player(0).hand_size

    assert play(game, deal(game, "loot_deck-pills_runes-base_game-pills-v2")).accepted

    decision = game.runtime.awaiting_decision

    assert decision is not None
    assert decision.kind is DecisionKind.CHOOSE_LOOT

    assert choose(game, 0, 0).accepted
    assert game.state.player(0).hand_size == before - 1


# ----------------------------------------------------------------------
# Bonuses that last until the end of the turn
# ----------------------------------------------------------------------


def bless(game: Game, card_id: str, player: int = 1) -> None:
    """
    Play a card that says "choose a player" and choose one.
    """
    assert play(game, deal(game, card_id)).accepted

    decision = game.runtime.awaiting_decision

    assert decision is not None

    target = game.state.player(player)

    assert choose(game, 0, list(decision.options).index(target)).accepted


def end_turn(game: Game) -> None:
    """
    Play the active player's turn out to its end.
    """
    while game.state.turn.phase is not GamePhase.END:
        assert game.act(CommandType.END_PHASE, game.state.turn.active_player).accepted

    assert game.act(CommandType.END_TURN, game.state.turn.active_player).accepted


def attack_bonus(game: Game, player: int) -> int:
    from fsme.rules import ATTACK, bonus

    return bonus(game.state, ATTACK, player)


def test_the_empress_grants_attack_and_a_better_die(base_game: ContentLibrary) -> None:
    game = new_game(base_game, players=3, rolls=[3])

    bless(game, "loot_deck-cards_miscellaneous-base_game-iii_the_empress")

    assert attack_bonus(game, 1) == 1
    assert attack_bonus(game, 0) == 0

    modifiers = {(m.stat, m.amount, m.player_id) for m in game.state.modifiers}

    assert ("attack", 1, 1) in modifiers
    assert ("roll", 1, 1) in modifiers


def test_a_roll_bonus_is_added_to_the_die_that_is_rolled(
    base_game: ContentLibrary,
) -> None:
    """
    The Empress says "+1 to dice rolls", so the roller's own die comes up one
    higher — which is only visible if the bonus reaches the roll itself.
    """
    game = new_game(base_game, players=2, rolls=[3, 3])

    bless(game, "loot_deck-cards_miscellaneous-base_game-iii_the_empress", player=0)

    # A turn allows one loot card, and the Empress was it. The second card is
    # here to roll a die, not to test the allowance.
    game.state.player(0).additional_loot_plays += 1

    assert play(game, deal(game, "loot_deck-pills_runes-base_game-pills")).accepted

    rolled = [
        event.get("value")
        for event in game.history
        if event.type is EventType.AFTER_ROLL
    ]

    assert rolled[-1] == 4


def test_the_lovers_grant_hit_points_a_hurt_player_can_use(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game, players=3)

    hurt = game.state.player(1)
    hurt.hp = 1

    bless(game, "loot_deck-cards_miscellaneous-base_game-vi_the_lovers")

    assert hurt.hp == 3
    assert hurt.max_hp == 4


def test_the_chariot_grants_one_of_each(base_game: ContentLibrary) -> None:
    game = new_game(base_game, players=3)

    blessed = game.state.player(1)
    before = blessed.max_hp

    bless(game, "loot_deck-cards_miscellaneous-base_game-vii_the_chariot")

    assert attack_bonus(game, 1) == 1
    assert blessed.max_hp == before + 1


def test_strength_allows_another_attack(base_game: ContentLibrary) -> None:
    game = new_game(base_game, players=3)

    blessed = game.state.player(1)
    before = blessed.attacks_left

    bless(game, "loot_deck-cards_miscellaneous-base_game-xi_strength")

    assert attack_bonus(game, 1) == 1
    assert blessed.attacks_left == before + 1


@pytest.mark.parametrize(
    ("roll", "stat"),
    ((1, "attack"), (2, "attack"), (3, "max_hp"), (4, "max_hp")),
)
def test_the_third_pills_grant_a_bonus_to_whoever_swallowed_them(
    base_game: ContentLibrary, roll: int, stat: str
) -> None:
    game = new_game(base_game, rolls=[roll])

    assert play(game, deal(game, "loot_deck-pills_runes-base_game-pills-v3")).accepted

    assert [(m.stat, m.amount, m.player_id) for m in game.state.modifiers] == [
        (stat, 1, 0)
    ]


@pytest.mark.parametrize("roll", (5, 6))
def test_the_third_pills_hurt_on_a_high_roll(
    base_game: ContentLibrary, roll: int
) -> None:
    game = new_game(base_game, rolls=[roll])

    before = game.state.player(0).hp

    assert play(game, deal(game, "loot_deck-pills_runes-base_game-pills-v3")).accepted

    assert game.state.player(0).hp == before - 1
    assert game.state.modifiers == []


def test_a_bonus_till_end_of_turn_ends_with_the_turn(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game, players=3)

    bless(game, "loot_deck-cards_miscellaneous-base_game-vii_the_chariot")

    assert game.state.modifiers

    end_turn(game)

    assert game.state.modifiers == []
    assert attack_bonus(game, 1) == 0


def test_lost_hit_points_are_not_given_back_when_a_bonus_expires(
    base_game: ContentLibrary,
) -> None:
    """
    A player who gains +2 HP, takes two damage and then loses the bonus is a
    player who took two damage. Forgetting the bonus without taking the hit
    points back would heal them for free.
    """
    game = new_game(base_game, players=3)

    blessed = game.state.player(1)

    bless(game, "loot_deck-cards_miscellaneous-base_game-vi_the_lovers")

    assert blessed.hp == 4

    blessed.hp -= 2

    end_turn(game)

    assert blessed.hp == 0 or not blessed.alive


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
