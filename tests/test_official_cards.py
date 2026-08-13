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

from fsme.cards import CardInstance, CardType
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


def toughen(game: Game, player: Any, amount: int = 6) -> None:
    """
    Give a player enough hit points for the damage a test is about.

    Writing max_hp by hand does not work and should not: the engine recomputes
    it from the character card and clamps hit points to it, so a bonus has to
    be granted the way a card grants one.
    """
    game.runtime.context.apply("add_modifier", [player], stat="max_hp", amount=amount)
    game.runtime.run()


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
# Cards that look through a deck
# ----------------------------------------------------------------------


def deck_of(game: Game, name: str) -> list[Any]:
    """
    A deck from the top down, which is the order a player thinks in.
    """
    return list(reversed(getattr(game.state, f"{name}_deck").cards))


@pytest.mark.parametrize(
    ("card_id", "deck"),
    (
        ("loot_deck-cards_miscellaneous-base_game-iv_the_emperor", "monster"),
        ("loot_deck-cards_miscellaneous-base_game-ix_the_hermit", "treasure"),
        ("loot_deck-cards_miscellaneous-base_game-xviii_the_moon", "loot"),
    ),
)
def test_a_seeing_card_offers_the_top_five_and_no_more(
    base_game: ContentLibrary, card_id: str, deck: str
) -> None:
    game = new_game(base_game)

    top_five = deck_of(game, deck)[:5]

    assert play(game, deal(game, card_id)).accepted

    decision = game.runtime.awaiting_decision

    assert decision is not None
    assert list(decision.options) == top_five


@pytest.mark.parametrize(
    ("card_id", "deck"),
    (
        ("loot_deck-cards_miscellaneous-base_game-iv_the_emperor", "monster"),
        ("loot_deck-cards_miscellaneous-base_game-ix_the_hermit", "treasure"),
        ("loot_deck-cards_miscellaneous-base_game-xviii_the_moon", "loot"),
    ),
)
def test_the_kept_card_ends_on_top_and_the_rest_underneath(
    base_game: ContentLibrary, card_id: str, deck: str
) -> None:
    """
    "Put 1 on top and the rest on the bottom" is one instruction about order,
    and order is the whole point of the card.
    """
    game = new_game(base_game)

    before = deck_of(game, deck)
    top_five = before[:5]
    below = before[5:]

    assert play(game, deal(game, card_id)).accepted

    decision = game.runtime.awaiting_decision

    assert decision is not None

    kept = top_five[3]
    rest = [card for card in top_five if card is not kept]

    assert choose(game, 0, list(decision.options).index(kept)).accepted

    after = deck_of(game, deck)

    assert after[0] is kept
    assert after[1 : 1 + len(below)] == below
    assert after[-len(rest):] == rest


def test_the_hanged_man_shows_three_cards_and_buries_the_ones_you_say(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    tops = {name: deck_of(game, name)[0] for name in ("loot", "treasure", "monster")}
    hand = game.state.player(0).hand_size

    assert play(
        game, deal(game, "loot_deck-cards_miscellaneous-base_game-xii_the_hanged_man")
    ).accepted

    # Bury the loot card, keep the treasure, bury the monster.
    for answer in ("yes", "no", "yes"):
        decision = game.runtime.awaiting_decision

        assert decision is not None
        assert decision.kind is DecisionKind.CHOOSE_OPTION
        assert list(decision.options) == ["yes", "no"]

        assert choose(game, 0, list(decision.options).index(answer)).accepted

    assert deck_of(game, "loot")[-1] is tops["loot"]
    assert deck_of(game, "treasure")[0] is tops["treasure"]
    assert deck_of(game, "monster")[-1] is tops["monster"]

    assert game.state.player(0).hand_size == hand + 2

    # The card says "look", so each top card was announced. Events reach the
    # log when the ability finishes, which is why this is checked at the end.
    revealed = [
        event.get("cards")[0]
        for event in game.history
        if event.type is EventType.REVEALED
    ]

    assert revealed == [tops["loot"], tops["treasure"], tops["monster"]]


def test_the_hanged_man_may_be_answered_with_three_refusals(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    before = {name: deck_of(game, name) for name in ("loot", "treasure", "monster")}

    assert play(
        game, deal(game, "loot_deck-cards_miscellaneous-base_game-xii_the_hanged_man")
    ).accepted

    for _ in range(3):
        decision = game.runtime.awaiting_decision

        assert decision is not None
        assert choose(game, 0, list(decision.options).index("no")).accepted

    for name in ("treasure", "monster"):
        assert deck_of(game, name) == before[name]

    # Two loot cards were drawn, so the loot deck is shorter by exactly those.
    assert deck_of(game, "loot") == before["loot"][2:]


# ----------------------------------------------------------------------
# Trinkets
# ----------------------------------------------------------------------

TRINKETS = (
    "loot_deck-trinkets-base_game-swallowed_penny",
    "loot_deck-trinkets-base_game-bloody_penny",
    "loot_deck-trinkets-base_game-counterfeit_penny",
    "loot_deck-trinkets-base_game-guppy_s_hairball",
    "loot_deck-trinkets-base_game-curved_horn",
    "loot_deck-trinkets-base_game-cain_s_eye",
    "loot_deck-trinkets-base_game-golden_horseshoe",
    "loot_deck-trinkets-base_game-purple_heart",
)


@pytest.mark.parametrize("card_id", TRINKETS)
def test_a_trinket_stays_in_play_instead_of_being_discarded(
    base_game: ContentLibrary, card_id: str
) -> None:
    """
    A trinket becomes an item when it resolves, so the rule that discards a
    played loot card must leave it where it put itself.
    """
    game = new_game(base_game)

    card = deal(game, card_id)

    assert play(game, card).accepted

    assert card in game.state.player(0).treasures.cards
    assert card not in game.state.loot_discard.cards
    assert card.controller == 0


def test_the_swallowed_penny_pays_its_holder_for_being_hurt(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    assert play(game, deal(game, "loot_deck-trinkets-base_game-swallowed_penny")).accepted

    coins = game.state.player(0).pennies

    game.runtime.context.apply("deal_damage", [game.state.player(0)], amount=1)
    game.runtime.run()

    assert game.state.player(0).pennies == coins + 1


def test_the_swallowed_penny_pays_nobody_else(base_game: ContentLibrary) -> None:
    """
    "Each time you take damage" is not each time anybody does.
    """
    game = new_game(base_game)

    assert play(game, deal(game, "loot_deck-trinkets-base_game-swallowed_penny")).accepted

    coins = game.state.player(0).pennies

    game.runtime.context.apply("deal_damage", [game.state.player(1)], amount=1)
    game.runtime.run()

    assert game.state.player(0).pennies == coins


def test_the_bloody_penny_pays_when_anybody_dies(base_game: ContentLibrary) -> None:
    """
    The printed card says "each time a player dies, before paying penalties,
    loot 1". The engine has no death penalties yet, so the ordering has nothing
    to be before; the loot itself is what is checked here.
    """
    game = new_game(base_game, players=3)

    assert play(game, deal(game, "loot_deck-trinkets-base_game-bloody_penny")).accepted

    hand = game.state.player(0).hand_size

    game.runtime.context.apply("kill", [game.state.player(2)])
    game.runtime.run()

    assert not game.state.player(2).alive
    assert game.state.player(0).hand_size == hand + 1


def test_the_counterfeit_penny_adds_one_to_every_gain(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    assert play(
        game, deal(game, "loot_deck-trinkets-base_game-counterfeit_penny")
    ).accepted

    coins = game.state.player(0).pennies

    game.state.player(0).additional_loot_plays += 1

    assert play(game, deal(game, "loot_deck-3-base_game-3_cents")).accepted

    assert game.state.player(0).pennies == coins + 4


def test_the_counterfeit_penny_leaves_other_players_alone(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    assert play(
        game, deal(game, "loot_deck-trinkets-base_game-counterfeit_penny")
    ).accepted

    coins = game.state.player(1).pennies

    game.runtime.context.apply("gain_coins", [game.state.player(1)], amount=3)
    game.runtime.run()

    assert game.state.player(1).pennies == coins + 3


@pytest.mark.parametrize(("roll", "damage"), ((6, 1), (5, 2)))
def test_guppys_hairball_prevents_damage_on_a_six(
    base_game: ContentLibrary, roll: int, damage: int
) -> None:
    game = new_game(base_game, rolls=[roll])

    assert play(
        game, deal(game, "loot_deck-trinkets-base_game-guppy_s_hairball")
    ).accepted

    player = game.state.player(0)
    player.hp = player.max_hp

    before = player.hp

    game.runtime.context.apply("deal_damage", [player], amount=2)
    game.runtime.run()

    assert player.hp == before - damage


def test_the_curved_horn_only_helps_the_first_attack_roll(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    assert play(game, deal(game, "loot_deck-trinkets-base_game-curved_horn")).accepted

    assert attack_bonus(game, 0) == 1

    game.state.turn.attack_rolls = 2

    assert attack_bonus(game, 0) == 0
    assert attack_bonus(game, 1) == 0


@pytest.mark.parametrize(
    ("card_id", "deck"),
    (
        ("loot_deck-trinkets-base_game-cain_s_eye", "loot"),
        ("loot_deck-trinkets-base_game-golden_horseshoe", "treasure"),
        ("loot_deck-trinkets-base_game-purple_heart", "monster"),
    ),
)
def test_a_looking_trinket_offers_the_top_card_each_of_its_turns(
    base_game: ContentLibrary, card_id: str, deck: str
) -> None:
    game = new_game(base_game, players=2)

    assert play(game, deal(game, card_id)).accepted

    end_turn(game)

    # The other player's turn: the trinket says "your turn", so it is silent.
    assert game.runtime.awaiting_decision is None

    top = deck_of(game, deck)[0]

    end_turn(game)

    decision = game.runtime.awaiting_decision

    assert decision is not None
    assert decision.player == 0

    assert choose(game, 0, list(decision.options).index("yes")).accepted

    assert deck_of(game, deck)[-1] is top


# ----------------------------------------------------------------------
# Choosing, shielding, and cards that move themselves
# ----------------------------------------------------------------------


def answer(game: Game, label: str, player: int = 0) -> None:
    decision = game.runtime.awaiting_decision

    assert decision is not None
    assert decision.kind is DecisionKind.CHOOSE_OPTION
    assert decision.player == player

    assert choose(game, player, list(decision.options).index(label)).accepted


def test_temperance_offers_two_prices_and_charges_the_one_chosen(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    player = game.state.player(0)
    toughen(game, player)

    before = snapshot(player)

    assert play(
        game, deal(game, "loot_deck-cards_miscellaneous-base_game-xiv_temperance")
    ).accepted

    decision = game.runtime.awaiting_decision

    assert decision is not None
    assert list(decision.options) == [
        "Take 1 damage and gain 4¢.",
        "Take 2 damage and gain 8¢.",
    ]

    answer(game, "Take 2 damage and gain 8¢.")

    assert player.hp == before.hp - 2
    assert player.pennies == before.pennies + 8


def test_temperance_can_be_taken_cheaply(base_game: ContentLibrary) -> None:
    game = new_game(base_game)

    player = game.state.player(0)
    toughen(game, player)

    before = snapshot(player)

    assert play(
        game, deal(game, "loot_deck-cards_miscellaneous-base_game-xiv_temperance")
    ).accepted

    answer(game, "Take 1 damage and gain 4¢.")

    assert player.hp == before.hp - 1
    assert player.pennies == before.pennies + 4


@pytest.mark.parametrize("roll", (1, 4, 6))
def test_the_high_priestess_deals_what_the_die_shows(
    base_game: ContentLibrary, roll: int
) -> None:
    game = new_game(base_game, rolls=[roll])

    victim = game.state.player(1)
    toughen(game, victim)

    hp = victim.hp

    assert play(
        game,
        deal(game, "loot_deck-cards_miscellaneous-base_game-ii_the_high_priestess"),
    ).accepted

    decision = game.runtime.awaiting_decision

    assert decision is not None
    assert choose(game, 0, list(decision.options).index(victim)).accepted

    assert victim.hp == hp - roll


def test_the_hierophant_absorbs_the_next_damage_only(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game, players=3)

    shielded = game.state.player(1)
    toughen(game, shielded)

    hp = shielded.hp

    bless(game, "loot_deck-cards_miscellaneous-base_game-v_the_hierophant")

    assert game.state.shields

    game.runtime.context.apply("deal_damage", [shielded], amount=3)
    game.runtime.run()

    assert shielded.hp == hp - 1
    assert game.state.shields == []

    game.runtime.context.apply("deal_damage", [shielded], amount=3)
    game.runtime.run()

    assert shielded.hp == hp - 4


def test_a_soul_heart_stops_a_single_point(base_game: ContentLibrary) -> None:
    game = new_game(base_game, players=3)

    shielded = game.state.player(1)
    toughen(game, shielded)

    hp = shielded.hp

    bless(game, "loot_deck-dice_shards_soul_hearts-base_game-soul_heart")

    game.runtime.context.apply("deal_damage", [shielded], amount=1)
    game.runtime.run()

    assert shielded.hp == hp


def test_an_unspent_shield_expires_with_the_turn(base_game: ContentLibrary) -> None:
    game = new_game(base_game, players=3)

    bless(game, "loot_deck-dice_shards_soul_hearts-base_game-soul_heart")

    assert game.state.shields

    end_turn(game)

    assert game.state.shields == []


def test_dagaz_can_shield_or_lift_a_curse(base_game: ContentLibrary) -> None:
    game = new_game(base_game, players=3)

    assert play(game, deal(game, "loot_deck-pills_runes-base_game-dagaz")).accepted

    decision = game.runtime.awaiting_decision

    assert decision is not None
    assert len(decision.options) == 2

    answer(game, str(decision.options[1]))

    target = game.runtime.awaiting_decision

    assert target is not None
    assert target.kind is DecisionKind.CHOOSE_PLAYER

    assert choose(game, 0, list(target.options).index(game.state.player(2))).accepted

    assert [shield.player_id for shield in game.state.shields] == [2]


def test_lost_soul_becomes_a_soul_rather_than_a_discard(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    card = deal(game, "loot_deck-lost_soul-base_game-lost_soul")

    souls = game.state.player(0).soul_count

    assert play(game, card).accepted

    assert card in game.state.player(0).souls.cards
    assert card not in game.state.loot_discard.cards
    assert game.state.player(0).soul_count == souls + 1


def test_the_sun_buries_itself_and_buys_another_turn(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game, players=3)

    card = deal(game, "loot_deck-cards_miscellaneous-base_game-xix_the_sun")

    assert play(game, card).accepted

    assert card is game.state.loot_deck.cards[0]
    assert card not in game.state.loot_discard.cards
    assert game.state.turn.extra_turn_for == 0

    end_turn(game)

    assert game.state.turn.active_player == 0
    assert game.state.turn.extra_turn_for is None

    end_turn(game)

    assert game.state.turn.active_player == 1


def test_mega_battery_recharges_everything_one_player_has(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game, players=3)

    theirs = game.state.player(1).treasures.cards
    mine = game.state.player(0).treasures.cards

    for card in list(theirs) + list(mine):
        card.tapped = True

    bless(game, "loot_deck-batteries-base_game-mega_battery")

    assert [card.tapped for card in theirs] == [False] * len(theirs)
    assert [card.tapped for card in mine] == [True] * len(mine)


def test_the_world_shows_every_hand_before_drawing(base_game: ContentLibrary) -> None:
    game = new_game(base_game, players=3)

    hands = [list(player.hand.cards) for player in game.state.players]
    before = game.state.player(0).hand_size

    assert play(
        game, deal(game, "loot_deck-cards_miscellaneous-base_game-xxi_the_world")
    ).accepted

    shown = [
        event.get("cards")
        for event in game.history
        if event.type is EventType.REVEALED and event.get("zone") == "hand"
    ]

    assert len(shown) == 3
    assert shown[1] == hands[1]
    assert game.state.player(0).hand_size == before + 2


def test_judgement_only_offers_the_players_with_the_most_souls(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game, players=3)

    game.runtime.context.apply("gain_soul", [game.state.player(1)], count=2)
    game.runtime.context.apply("gain_soul", [game.state.player(2)], count=2)
    game.runtime.run()

    assert play(
        game, deal(game, "loot_deck-cards_miscellaneous-base_game-xx_judgement")
    ).accepted

    decision = game.runtime.awaiting_decision

    assert decision is not None
    assert list(decision.options) == [game.state.player(1), game.state.player(2)]

    assert choose(game, 0, list(decision.options).index(game.state.player(2))).accepted

    assert game.state.player(2).soul_count == 1
    assert game.state.player(1).soul_count == 2


def test_the_devil_pays_an_item_for_an_item(base_game: ContentLibrary) -> None:
    game = new_game(base_game, players=2)

    # The starting item is eternal and cannot be destroyed, so the Devil needs
    # something else to give up.
    game.runtime.context.apply("gain_treasure", [game.state.player(0)], count=1)
    game.runtime.context.apply("gain_treasure", [game.state.player(1)], count=1)
    game.runtime.run()

    sacrifice = game.state.player(0).treasures.cards[-1]
    theirs = game.state.player(1).treasures.cards[-1]

    assert play(
        game, deal(game, "loot_deck-cards_miscellaneous-base_game-xv_the_devil")
    ).accepted

    decision = game.runtime.awaiting_decision

    assert decision is not None
    assert sacrifice in decision.options
    assert theirs not in decision.options

    assert choose(game, 0, list(decision.options).index(sacrifice)).accepted

    spoils = game.runtime.awaiting_decision

    assert spoils is not None
    assert theirs in spoils.options
    assert all(card in spoils.options for card in game.state.treasure_shop.cards)

    assert choose(game, 0, list(spoils.options).index(theirs)).accepted

    assert sacrifice in game.state.treasure_discard.cards
    assert theirs in game.state.player(0).treasures.cards


# ----------------------------------------------------------------------
# Cards that act on the stack and the board
# ----------------------------------------------------------------------


def test_the_fool_sweeps_the_stack_and_ends_the_turn(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game, players=3)

    # Something slow to interrupt: a bomb waiting for its target is on the
    # stack, and the Fool is played while it waits.
    assert play(game, deal(game, "loot_deck-bombs-base_game-bomb")).accepted

    decision = game.runtime.awaiting_decision

    assert decision is not None
    assert choose(game, 0, 0).accepted

    game.state.player(0).additional_loot_plays += 1

    monsters = [monster.hp for monster in game.state.active_monsters.cards]

    assert play(
        game, deal(game, "loot_deck-cards_miscellaneous-base_game-o_the_fool")
    ).accepted

    assert game.state.stack.is_empty()
    assert game.state.turn.active_player == 1
    assert [monster.hp for monster in game.state.active_monsters.cards] == monsters


def test_butter_bean_cancels_the_card_it_answers(base_game: ContentLibrary) -> None:
    """
    The bean is played in response, so the engine must be letting players
    respond: with priority open, a loot card waits on the stack for an answer.
    """
    game = Game.from_content(
        base_game, ["Ann", "Bo"], seed=1234, interactive_priority=True
    )

    assert game.start().accepted

    coins = game.state.player(0).pennies

    penny = deal(game, "loot_deck-nickels-base_game-a_dime")
    bean = deal(game, "loot_deck-butter_beans-base_game-butter_bean", player=1)

    assert play(game, penny).accepted
    assert not game.state.stack.is_empty()

    # Priority starts with the player who acted, so the bean waits its turn.
    assert game.act(CommandType.PASS_PRIORITY, 0).accepted
    assert game.state.priority.holder == 1

    assert play(game, bean, player=1).accepted

    # The bean sits above the card it answers and resolves first, once
    # everybody has stopped responding. The dime's ability is then the only
    # thing left that a bean may cancel, so the engine takes it rather than
    # interrupting the game to confirm the obvious.
    while game.runtime.awaiting_priority:
        assert game.act(
            CommandType.PASS_PRIORITY, game.state.priority.holder or 0
        ).accepted

    assert game.state.stack.is_empty()
    assert game.state.player(0).pennies == coins

    # Cancelled, not undone: the card was still played and still goes away.
    assert penny in game.state.loot_discard.cards


def test_justice_catches_you_up_with_the_player_you_choose(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game, players=3)

    rival = game.state.player(2)

    game.runtime.context.apply("draw_loot", [rival], count=4)
    game.runtime.context.apply("gain_coins", [rival], amount=9)
    game.runtime.run()

    assert play(
        game, deal(game, "loot_deck-cards_miscellaneous-base_game-viii_justice")
    ).accepted

    decision = game.runtime.awaiting_decision

    assert decision is not None
    assert game.state.player(0) not in decision.options

    assert choose(game, 0, list(decision.options).index(rival)).accepted

    assert game.state.player(0).hand_size == rival.hand_size
    assert game.state.player(0).pennies == rival.pennies


def test_justice_gives_nothing_to_a_player_already_ahead(
    base_game: ContentLibrary,
) -> None:
    """
    "Until you have the same number" is a floor, not a swap: a player who
    already has more keeps what they have.
    """
    game = new_game(base_game, players=3)

    game.runtime.context.apply("draw_loot", [game.state.player(0)], count=5)
    game.runtime.context.apply("gain_coins", [game.state.player(0)], amount=12)
    game.runtime.run()

    before = snapshot(game.state.player(0))

    assert play(
        game, deal(game, "loot_deck-cards_miscellaneous-base_game-viii_justice")
    ).accepted

    decision = game.runtime.awaiting_decision

    assert decision is not None
    assert choose(game, 0, list(decision.options).index(game.state.player(2))).accepted

    assert game.state.player(0).hand_size == before.hand_size
    assert game.state.player(0).pennies == before.pennies


def test_ehwaz_replaces_the_monsters_nobody_is_fighting(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    before = list(game.state.active_monsters.cards)
    waiting = len(game.state.monster_deck)

    assert play(game, deal(game, "loot_deck-pills_runes-base_game-ehwaz")).accepted

    after = list(game.state.active_monsters.cards)

    assert len(after) == len(before)
    assert all(monster not in before for monster in after)
    assert all(monster in game.state.monster_discard.cards for monster in before)
    assert len(game.state.monster_deck) == waiting - len(before)


def test_a_defeated_monster_is_replaced(base_game: ContentLibrary) -> None:
    """
    The slots stay full: the same refill that Ehwaz relies on is the one the
    rules run after a kill.
    """
    game = new_game(base_game)

    monster = game.state.active_monsters.cards[0]

    game.runtime.context.apply("kill", [monster])
    game.runtime.run()

    assert monster not in game.state.active_monsters.cards
    assert len(game.state.active_monsters) == 2


# ----------------------------------------------------------------------
# Treasures
# ----------------------------------------------------------------------


def give(game: Game, card_id: str, player: int = 0) -> CardInstance:
    """
    Put a named published item into a player's play area.
    """
    card = CardInstance(
        definition=game.runtime.cards.get(card_id),
        instance_id=game.state.ids.allocate("treasure"),
        controller=player,
        owner=player,
    )

    game.state.player(player).treasures.add_top(card)
    game.runtime.run()

    return card


def activate(game: Game, card: CardInstance, player: int = 0, ability: int = 0) -> Any:
    index = list(game.state.player(player).treasures.cards).index(card)

    return game.act(
        CommandType.ACTIVATE_TREASURE, player, index=index, ability=ability
    )


def test_a_meal_raises_the_hit_point_maximum(base_game: ContentLibrary) -> None:
    game = new_game(base_game)

    before = game.state.player(0).max_hp

    give(game, "treasure_deck-passive_items-base_game-breakfast")

    assert game.state.player(0).max_hp == before + 1


def test_the_champion_belt_grants_an_attack_and_a_first_swing(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    attacks = game.state.player(0).attacks_left

    give(game, "treasure_deck-passive_items-base_game-champion_belt")

    assert attack_bonus(game, 0) == 1

    game.state.turn.attack_rolls = 2

    assert attack_bonus(game, 0) == 0

    end_turn(game)
    end_turn(game)

    assert game.state.player(0).attacks_left == attacks + 1


@pytest.mark.parametrize(
    "card_id",
    (
        "treasure_deck-passive_items-base_game-meat",
        "treasure_deck-passive_items-base_game-synthoil",
    ),
)
def test_an_attack_roll_bonus_applies_to_attacks_only(
    base_game: ContentLibrary, card_id: str
) -> None:
    game = new_game(base_game, rolls=[3, 3])

    give(game, card_id)

    # An ordinary roll is untouched: the card says "attack rolls".
    assert play(game, deal(game, "loot_deck-pills_runes-base_game-pills")).accepted

    rolls = [
        event.get("value")
        for event in game.history
        if event.type is EventType.AFTER_ROLL
    ]

    assert rolls[-1] == 3

    assert game.act(CommandType.END_PHASE, 0).accepted
    assert game.act(CommandType.ATTACK, 0, index=0).accepted

    attacks = [
        event.get("value")
        for event in game.history
        if event.type is EventType.AFTER_ATTACK_ROLL
    ]

    assert attacks[0] == 4


def test_the_relic_pays_whoever_holds_it_when_anyone_rolls_a_one(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game, players=2, rolls=[1])

    give(game, "treasure_deck-passive_items-base_game-the_relic", player=1)

    hand = game.state.player(1).hand_size

    assert play(game, deal(game, "loot_deck-pills_runes-base_game-pills")).accepted

    assert game.state.player(1).hand_size == hand + 1


def test_moms_razor_hurts_the_player_who_rolled(base_game: ContentLibrary) -> None:
    game = new_game(base_game, players=2, rolls=[6])

    give(game, "treasure_deck-passive_items-base_game-mom_s_razor", player=1)

    hp = game.state.player(0).hp

    assert play(game, deal(game, "loot_deck-pills_runes-base_game-pills")).accepted

    answer(game, "yes", player=1)

    assert game.state.player(0).hp == hp - 1


def test_a_dry_baby_reduces_every_hit_to_one(base_game: ContentLibrary) -> None:
    game = new_game(base_game)

    give(game, "treasure_deck-passive_items-base_game-dry_baby")

    player = game.state.player(0)
    toughen(game, player)

    hp = player.hp

    game.runtime.context.apply("deal_damage", [player], amount=4)
    game.runtime.run()

    assert player.hp == hp - 1


def test_edens_blessing_pays_a_player_with_nothing(base_game: ContentLibrary) -> None:
    game = new_game(base_game)

    give(game, "treasure_deck-passive_items-base_game-eden_s_blessing")

    game.state.player(0).pennies = 0

    end_turn(game)

    assert game.state.player(0).pennies == 6


def test_edens_blessing_pays_nothing_to_a_player_with_coins(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    give(game, "treasure_deck-passive_items-base_game-eden_s_blessing")

    game.state.player(0).pennies = 2

    end_turn(game)

    assert game.state.player(0).pennies == 2


def test_mr_boom_is_activated_by_tapping(base_game: ContentLibrary) -> None:
    game = new_game(base_game)

    card = give(game, "treasure_deck-active_items-base_game-mr_boom")

    assert game.act(CommandType.END_PHASE, 0).accepted

    monster = game.state.active_monsters.cards[0]
    hp = monster.hp

    assert activate(game, card).accepted

    decision = game.runtime.awaiting_decision

    if decision is not None:
        assert choose(game, 0, list(decision.options).index(monster)).accepted

        assert monster.hp == hp - 1
    else:
        assert game.state.active_monsters.cards[0].hp < hp

    assert card.tapped is True
    assert activate(game, card).rejected


def test_the_battery_recharges_something_other_than_itself(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    battery = give(game, "treasure_deck-active_items-base_game-the_battery")

    starting = game.state.player(0).treasures.cards[0]
    starting.tapped = True

    assert activate(game, battery).accepted

    decision = game.runtime.awaiting_decision

    if decision is not None:
        assert battery not in decision.options

        assert choose(game, 0, list(decision.options).index(starting)).accepted

    assert starting.tapped is False
    assert battery.tapped is True


def test_a_paid_item_charges_cents_and_stays_untapped(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    bum = give(game, "treasure_deck-paid_items-base_game-battery_bum")

    starting = game.state.player(0).treasures.cards[0]
    starting.tapped = True

    assert activate(game, bum).rejected, "nobody can pay 4¢ from nothing"

    game.state.player(0).pennies = 4

    assert activate(game, bum).accepted

    decision = game.runtime.awaiting_decision

    if decision is not None:
        assert choose(game, 0, list(decision.options).index(starting)).accepted

    assert starting.tapped is False
    assert bum.tapped is False, "a paid ability does not tap the item"
    assert game.state.player(0).pennies == 0


def test_the_smelter_charges_a_card_from_hand(base_game: ContentLibrary) -> None:
    game = new_game(base_game)

    smelter = give(game, "treasure_deck-paid_items-base_game-smelter")

    hand = game.state.player(0).hand_size
    coins = game.state.player(0).pennies

    assert activate(game, smelter).accepted

    assert game.state.player(0).hand_size == hand - 1
    assert game.state.player(0).pennies == coins + 3


def test_tech_x_charges_counters_for_its_second_ability(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    tech = give(game, "treasure_deck-active_items-base_game-tech_x")

    assert activate(game, tech, ability=1).rejected, "no counters yet"

    for _ in range(3):
        assert activate(game, tech, ability=0).accepted
        tech.tapped = False

    assert tech.counters["charge"] == 3

    assert activate(game, tech, ability=1).accepted

    decision = game.runtime.awaiting_decision

    assert decision is not None

    victim = game.state.player(1)

    assert choose(game, 0, list(decision.options).index(victim)).accepted

    assert tech.counters["charge"] == 0
    assert victim.hp == 0 or not victim.alive


def test_the_potato_peeler_discards_the_top_of_each_deck(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    peeler = give(game, "treasure_deck-active_items-base_game-potato_peeler")

    tops = {name: deck_of(game, name)[0] for name in ("loot", "treasure", "monster")}

    assert activate(game, peeler).accepted

    for name, card in tops.items():
        assert card in getattr(game.state, f"{name}_discard").cards
        assert card not in deck_of(game, name)


def test_the_jawbone_takes_three_cents_from_the_player_it_names(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game, players=3)

    jawbone = give(game, "treasure_deck-active_items-base_game-jawbone")

    victim = game.state.player(2)
    victim.pennies = 5

    assert activate(game, jawbone).accepted

    decision = game.runtime.awaiting_decision

    assert decision is not None
    assert game.state.player(0) not in decision.options

    assert choose(game, 0, list(decision.options).index(victim)).accepted

    assert victim.pennies == 2
    assert game.state.player(0).pennies == 3


def test_shiny_rock_pays_for_activating_anything(base_game: ContentLibrary) -> None:
    game = new_game(base_game)

    give(game, "treasure_deck-passive_items-base_game-shiny_rock")
    boom = give(game, "treasure_deck-active_items-base_game-mr_boom")

    assert game.act(CommandType.END_PHASE, 0).accepted

    coins = game.state.player(0).pennies

    assert activate(game, boom).accepted

    decision = game.runtime.awaiting_decision

    if decision is not None:
        assert choose(game, 0, 0).accepted

    assert game.state.player(0).pennies == coins + 1


# ----------------------------------------------------------------------
# Monsters
# ----------------------------------------------------------------------


def summon(game: Game, card_id: str) -> CardInstance:
    """
    Put a named published monster into the first monster slot.

    Waiting for the shuffle to deal the wanted monster would make the test
    about the shuffle.
    """
    monster = CardInstance(
        definition=game.runtime.cards.get(card_id),
        instance_id=game.state.ids.allocate("monster"),
    )

    monster.hp = monster.definition.health
    monster.alive = True

    game.state.active_monsters.cards.insert(0, monster)

    return monster


def slay(game: Game, monster: CardInstance, killer: int = 0) -> None:
    """
    Kill a monster outright, crediting the player who did it.
    """
    monster.last_damaged_by = killer

    game.runtime.context.apply("kill", [monster])
    game.runtime.run()


def test_a_boom_fly_takes_everybody_with_it(base_game: ContentLibrary) -> None:
    game = new_game(base_game, players=3)

    fly = summon(game, "monster_deck-basic_enemies-base_game-boom_fly")

    for player in game.state.players:
        toughen(game, player)

    before = [player.hp for player in game.state.players]

    slay(game, fly)

    assert [player.hp for player in game.state.players] == [hp - 1 for hp in before]


def test_a_black_bony_hits_the_player_who_killed_it(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game, players=3)

    bony = summon(game, "monster_deck-basic_enemies-base_game-black_bony")

    for player in game.state.players:
        toughen(game, player)

    before = [player.hp for player in game.state.players]

    slay(game, bony, killer=2)

    assert game.state.player(2).hp == before[2] - 1
    assert game.state.player(0).hp == before[0]


@pytest.mark.parametrize(("roll", "damage"), ((2, 1), (5, 2)))
def test_wrath_rolls_for_how_much_it_hurts(
    base_game: ContentLibrary, roll: int, damage: int
) -> None:
    game = new_game(base_game, players=3, rolls=[roll])

    wrath = summon(game, "monster_deck-bosses-base_game-wrath")

    for player in game.state.players:
        toughen(game, player)

    before = [player.hp for player in game.state.players]

    slay(game, wrath)

    assert [player.hp for player in game.state.players] == [
        hp - damage for hp in before
    ]


def test_a_greedling_charges_the_player_it_names(base_game: ContentLibrary) -> None:
    game = new_game(base_game, players=3)

    greedling = summon(game, "monster_deck-basic_enemies-base_game-greedling")

    victim = game.state.player(2)
    victim.pennies = 9

    slay(game, greedling)

    decision = game.runtime.awaiting_decision

    assert decision is not None
    assert choose(game, 0, list(decision.options).index(victim)).accepted

    assert victim.pennies == 2


def test_sloth_empties_the_hand_of_whoever_killed_it(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game, players=3)

    sloth = summon(game, "monster_deck-bosses-base_game-sloth")

    assert game.state.player(1).hand_size > 0

    slay(game, sloth, killer=1)

    assert game.state.player(1).hand_size == 0
    assert game.state.player(0).hand_size > 0


def test_a_psy_horf_recharges_the_killer_s_items(base_game: ContentLibrary) -> None:
    game = new_game(base_game)

    horf = summon(game, "monster_deck-basic_enemies-base_game-psy_horf")

    for card in game.state.player(0).treasures.cards:
        card.tapped = True

    slay(game, horf)

    assert [card.tapped for card in game.state.player(0).treasures.cards] == [False]


def test_moms_dead_hand_offers_a_theft_that_may_be_refused(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    hand = summon(game, "monster_deck-basic_enemies-base_game-mom_s_dead_hand")

    game.runtime.context.apply("gain_treasure", [game.state.player(1)], count=1)
    game.runtime.run()

    theirs = game.state.player(1).treasures.cards[-1]

    slay(game, hand)

    answer(game, "yes")

    decision = game.runtime.awaiting_decision

    if decision is not None:
        assert choose(game, 0, list(decision.options).index(theirs)).accepted

    assert theirs in game.state.player(0).treasures.cards


PILLS_PAYOUT = {1: 4, 2: 4, 3: 7, 4: 7, 5: -4, 6: -4}
"""
What Pills! itself pays for each face.

Pills! is only here to make somebody roll a die, but it pays for the privilege,
and a test that forgot that would be measuring the wrong card.
"""


@pytest.mark.parametrize(
    ("card_id", "roll", "coins", "loot", "damage"),
    (
        ("monster_deck-cursed_enemies-base_game-cursed_keeper_head", 1, -2, 0, 0),
        ("monster_deck-cursed_enemies-base_game-cursed_horf", 2, 0, 0, 2),
        ("monster_deck-cursed_enemies-base_game-cursed_fatty", 5, 0, -1, 0),
        ("monster_deck-holy_charmed_enemies-base_game-holy_dip", 1, 1, 0, 0),
        ("monster_deck-holy_charmed_enemies-base_game-holy_keeper_head", 4, 2, 0, 0),
        ("monster_deck-holy_charmed_enemies-base_game-holy_squirt", 5, 0, 1, 0),
    ),
)
def test_a_cursed_or_holy_monster_answers_the_roll_it_names(
    base_game: ContentLibrary,
    card_id: str,
    roll: int,
    coins: int,
    loot: int,
    damage: int,
) -> None:
    game = new_game(base_game, rolls=[roll])

    summon(game, card_id)

    player = game.state.player(0)
    toughen(game, player)

    game.state.player(0).pennies = 20

    before = snapshot(player)

    assert play(game, deal(game, "loot_deck-pills_runes-base_game-pills")).accepted

    assert player.pennies == before.pennies + PILLS_PAYOUT[roll] + coins
    assert player.hand_size == before.hand_size + loot
    assert player.hp == before.hp - damage


def test_a_holy_monster_leaves_other_rolls_alone(base_game: ContentLibrary) -> None:
    game = new_game(base_game, rolls=[3])

    summon(game, "monster_deck-holy_charmed_enemies-base_game-holy_dip")

    coins = game.state.player(0).pennies

    assert play(game, deal(game, "loot_deck-pills_runes-base_game-pills")).accepted

    # Pills! pays 7¢ on a three, and the monster pays nothing on anything but a one.
    assert game.state.player(0).pennies == coins + 7


def test_chub_heals_only_while_it_is_the_one_being_attacked(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game, rolls=[1, 1, 1, 1])

    chub = summon(game, "monster_deck-bosses-base_game-chub")
    chub.hp = 1

    assert game.act(CommandType.END_PHASE, 0).accepted

    # A roll made outside a fight with Chub does nothing for it.
    assert chub.hp == 1

    assert game.act(CommandType.ATTACK, 0, index=0).accepted

    assert chub.hp > 1


# ----------------------------------------------------------------------
# Characters and curses
# ----------------------------------------------------------------------


def test_a_character_taps_for_an_extra_loot_card(base_game: ContentLibrary) -> None:
    game = new_game(base_game)

    character = game.state.player(0).character

    assert character is not None

    assert play(game, deal(game, "loot_deck-1-base_game-a_penny")).accepted
    assert play(game, deal(game, "loot_deck-1-base_game-a_penny")).rejected

    assert game.act(CommandType.ACTIVATE_TREASURE, 0, zone="character").accepted

    assert character.tapped is True
    assert play(game, deal(game, "loot_deck-1-base_game-a_penny")).accepted


def test_a_tapped_character_cannot_be_tapped_again(base_game: ContentLibrary) -> None:
    game = new_game(base_game)

    assert game.act(CommandType.ACTIVATE_TREASURE, 0, zone="character").accepted
    assert game.act(CommandType.ACTIVATE_TREASURE, 0, zone="character").rejected


def curse(game: Game, card_id: str, player: int = 0) -> CardInstance:
    """
    Put a curse on a player, the way a card that attaches one would.
    """
    card = CardInstance(
        definition=game.runtime.cards.get(card_id),
        instance_id=game.state.ids.allocate("curse"),
    )

    game.runtime.context.apply("attach_curse", [game.state.player(player)], card=card)
    game.runtime.run()

    return card


def test_the_curse_of_greed_charges_its_bearer_at_the_end_of_the_turn(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    curse(game, "monster_deck-curses-base_game-curse_of_greed")

    game.state.player(0).pennies = 9
    game.state.player(1).pennies = 9

    end_turn(game)

    assert game.state.player(0).pennies == 5
    assert game.state.player(1).pennies == 9, "the curse is one player's, not the table's"


def test_the_curse_of_amnesia_costs_two_cards(base_game: ContentLibrary) -> None:
    game = new_game(base_game)

    curse(game, "monster_deck-curses-base_game-curse_of_amnesia")

    hand = game.state.player(0).hand_size

    end_turn(game)

    assert game.state.player(0).hand_size == hand - 2


def test_the_curse_of_pain_hurts_at_the_start_of_the_turn(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    curse(game, "monster_deck-curses-base_game-curse_of_pain")

    player = game.state.player(0)

    assert player.hp == player.max_hp

    # Round the table back to the cursed player: the curse hurts when their
    # turn starts, not when somebody else's does.
    end_turn(game)

    assert player.hp == player.max_hp

    end_turn(game)

    assert player.hp == player.max_hp - 1


def test_the_curse_of_loss_takes_a_soul_when_its_bearer_dies(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    curse(game, "monster_deck-curses-base_game-curse_of_loss")

    game.runtime.context.apply("gain_soul", [game.state.player(0)], count=2)
    game.runtime.run()

    game.runtime.context.apply("kill", [game.state.player(0)])
    game.runtime.run()

    assert game.state.player(0).soul_count == 1


# ----------------------------------------------------------------------
# Monsters whose own numbers change
# ----------------------------------------------------------------------


def difficulty_of(game: Game, monster: CardInstance) -> int:
    from fsme.rules import DIFFICULTY, monster_value

    printed = monster.definition.roll or 4

    return monster_value(game.state, DIFFICULTY, monster, printed)


def attack_of(game: Game, monster: CardInstance) -> int:
    from fsme.rules import ATTACK, monster_value

    printed = monster.definition.attack or 1

    return monster_value(game.state, ATTACK, monster, printed)


def test_gemini_hits_harder_at_one_hit_point(base_game: ContentLibrary) -> None:
    game = new_game(base_game)

    gemini = summon(game, "monster_deck-bosses-base_game-gemini")

    printed = gemini.definition.attack

    assert attack_of(game, gemini) == printed

    gemini.hp = 1

    assert attack_of(game, gemini) == printed + 1


@pytest.mark.parametrize(
    ("card_id", "hp", "bonus"),
    (
        ("monster_deck-bosses-base_game-larry_jr", 2, 1),
        ("monster_deck-bosses-base_game-mask_of_infamy", 1, 2),
    ),
)
def test_a_wounded_monster_is_harder_to_hit(
    base_game: ContentLibrary, card_id: str, hp: int, bonus: int
) -> None:
    game = new_game(base_game)

    monster = summon(game, card_id)
    printed = monster.definition.roll

    assert difficulty_of(game, monster) == printed

    monster.hp = hp

    assert difficulty_of(game, monster) == printed + bonus


def test_war_grows_angrier_each_time_it_is_hurt(base_game: ContentLibrary) -> None:
    game = new_game(base_game)

    war = summon(game, "monster_deck-bosses-base_game-war")
    printed = war.definition.attack

    game.runtime.context.apply("deal_damage", [war], amount=1)
    game.runtime.run()

    assert attack_of(game, war) == printed + 1

    game.runtime.context.apply("deal_damage", [war], amount=1)
    game.runtime.run()

    assert attack_of(game, war) == printed + 2

    end_turn(game)

    assert attack_of(game, war) == printed, "the anger lasted for the turn"


def test_the_curse_of_the_blind_only_blinds_its_bearer(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game)

    monster = game.state.active_monsters.cards[0]
    printed = monster.definition.roll or 4

    curse(game, "monster_deck-curses-base_game-curse_of_the_blind", player=1)

    assert difficulty_of(game, monster) == printed

    end_turn(game)

    assert difficulty_of(game, monster) == printed + 1


# ----------------------------------------------------------------------
# Events revealed from the monster deck
# ----------------------------------------------------------------------


def stack_deck(game: Game, card_id: str) -> CardInstance:
    """
    Put a named card on top of the monster deck.
    """
    card = CardInstance(
        definition=game.runtime.cards.get(card_id),
        instance_id=game.state.ids.allocate("monster"),
    )

    game.state.monster_deck.add_top(card)

    return card


def clear_a_slot(game: Game) -> None:
    """
    Empty a monster slot so the rules reveal whatever is on top of the deck.

    The monster is discarded rather than killed: a defeated monster may have a
    death ability of its own, and this is a test about what comes next.
    """
    game.runtime.context.apply(
        "discard_monsters", [game.state.active_monsters.cards[-1]]
    )
    game.runtime.run()


def test_an_event_happens_when_it_is_revealed(base_game: ContentLibrary) -> None:
    game = new_game(base_game, players=3, rolls=[6])

    event = stack_deck(game, "monster_deck-good_events-base_game-chest")

    coins = game.state.player(0).pennies

    clear_a_slot(game)

    assert game.state.player(0).pennies == coins + 6
    assert event in game.state.monster_discard.cards
    assert event not in game.state.active_monsters.cards
    assert len(game.state.active_monsters) == 2, "the event did not fill the slot"


def test_a_revealed_curse_attaches_to_the_active_player(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game, players=3)

    card = stack_deck(game, "monster_deck-curses-base_game-curse_of_pain")

    clear_a_slot(game)

    assert card in game.state.player(0).curses.cards
    assert len(game.state.active_monsters) == 2


def test_troll_bombs_hurt_only_the_player_who_found_them(
    base_game: ContentLibrary,
) -> None:
    game = new_game(base_game, players=3)

    for player in game.state.players:
        toughen(game, player)

    before = [player.hp for player in game.state.players]

    stack_deck(game, "monster_deck-bad_events-base_game-troll_bombs")

    clear_a_slot(game)

    assert game.state.player(0).hp == before[0] - 2
    assert game.state.player(1).hp == before[1]


def test_greed_empties_the_richest_purse(base_game: ContentLibrary) -> None:
    game = new_game(base_game, players=3)

    game.state.player(1).pennies = 12
    game.state.player(2).pennies = 12
    game.state.player(0).pennies = 3

    stack_deck(game, "monster_deck-bad_events-base_game-greed")

    clear_a_slot(game)

    decision = game.runtime.awaiting_decision

    assert decision is not None
    assert list(decision.options) == [game.state.player(1), game.state.player(2)]

    assert choose(game, 0, 1).accepted

    assert game.state.player(2).pennies == 0
    assert game.state.player(1).pennies == 12
    assert game.state.player(0).pennies == 3


def test_a_game_is_never_laid_out_with_an_event_in_a_slot(
    base_game: ContentLibrary,
) -> None:
    """
    Laying a game out is not a turn: there is nobody for an event to happen to.
    """
    for seed in range(12):
        game = Game.from_content(base_game, ["Ann", "Bo"], seed=seed)

        for monster in game.state.active_monsters.cards:
            assert monster.definition.type is CardType.MONSTER


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
