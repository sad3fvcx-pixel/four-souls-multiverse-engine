"""
The small sets, played in games that contain them.

A promo set is a handful of cards printed alongside a plush or a can of
powder, and it is content like any other: read the card, write the ability,
play it in a real game. They are gathered in one file because each set is
too small to fill one of its own, not because they are tested any differently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_official_cards import (
    activate,
    answer,
    choose,
    deal,
    give,
    hurt,
    only_monster,
    pending,
    pick,
    play,
    slay,
    starting_item,
    summon,
    toughen,
)

from fsme.cards import CardInstance
from fsme.commands import CommandType
from fsme.content import ContentLibrary, ContentLoader
from fsme.game import Game
from fsme.runtime.vocabulary import engine_vocabulary
from fsme.state import GamePhase

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def promos() -> ContentLoader:
    return ContentLoader(engine_vocabulary()).load_root(CONTENT_ROOT)


def library_with(promos: Any, expansion: str) -> ContentLibrary:
    """
    The base game plus one small set, which is how a promo is played.
    """
    only = ContentLibrary()
    only.add(promos.get("base_game"))
    only.add(promos.get(expansion))

    return only


def new_game(
    library: ContentLibrary,
    players: int = 2,
    seed: int = 1234,
    rolls: list[int] | None = None,
) -> Game:
    from test_combat import FixedRNG

    # Who takes the first turn is the deal's business — Cain says he does —
    # and a test about a promo card is not about that, so a deal that seats
    # somebody else first is dealt again.
    for candidate in range(seed, seed + 64):
        game = Game.from_content(
            library,
            ["Ann", "Bo", "Cy"][:players],
            seed=candidate,
            rng=FixedRNG(rolls) if rolls is not None else None,
        )

        assert game.start().accepted

        if game.state.turn.active_player == 0:
            break

    # A character dealt at random may ask something as the game opens — Eden
    # chooses a starting item — and a test about a promo card is not about
    # that. The first answer is taken and the game gets going.
    while game.runtime.awaiting_decision is not None:
        decision = game.runtime.awaiting_decision

        assert choose(game, decision.player, 0).accepted

    return game


def difficulty_of(game: Game, monster: CardInstance) -> int:
    from fsme.rules import DIFFICULTY, monster_value

    return monster_value(
        game.state, DIFFICULTY, monster, int(monster.definition.roll or 0)
    )


def attack_of(game: Game, monster: CardInstance) -> int:
    from fsme.rules import ATTACK, monster_value

    return monster_value(
        game.state, ATTACK, monster, int(monster.definition.attack or 0)
    )


def reach_action_phase(game: Game) -> None:
    while game.state.turn.phase is not GamePhase.ACTION:
        assert game.act(CommandType.END_PHASE, game.state.turn.active_player).accepted


def end_turn(game: Game) -> None:
    while game.state.turn.phase is not GamePhase.END:
        assert game.act(CommandType.END_PHASE, game.state.turn.active_player).accepted

    assert game.act(CommandType.END_TURN, game.state.turn.active_player).accepted


# ----------------------------------------------------------------------
# Gish
# ----------------------------------------------------------------------


def test_gish_must_be_attacked(promos: Any) -> None:
    game = new_game(library_with(promos, "gish"))

    only_monster(game, "monster_deck-bosses-gish-gish", hp=6)

    end_turn(game)

    # The next player's turn opened with Gish on the table.
    active = game.state.turn.active_player

    reach_action_phase(game)

    refused = game.act(CommandType.END_TURN, active)

    assert not refused.accepted
    assert "must still attack" in str(refused.reason)


def test_gish_costs_the_killer_a_turn(promos: Any) -> None:
    game = new_game(library_with(promos, "gish"), players=3)

    gish = only_monster(game, "monster_deck-bosses-gish-gish", hp=6)

    slay(game, gish)

    assert pick(game, 0, game.state.player(1)).accepted

    assert game.state.skipped_players == [1]


def test_lil_gish_keeps_an_item_asleep(promos: Any) -> None:
    library = library_with(promos, "gish")

    game = new_game(library)

    lil = give(game, "treasure_deck-active_items-gish-lil_gish")
    theirs = give(game, "treasure_deck-active_items-base_game-decoy", player=1)

    theirs.tapped = True

    assert activate(game, lil).accepted
    assert pick(game, 0, theirs).accepted

    end_turn(game)

    assert theirs.tapped, "their turn began and the item stayed down"

    end_turn(game)
    end_turn(game)

    assert not theirs.tapped, "one recharge missed, not every recharge"


# ----------------------------------------------------------------------
# Target
# ----------------------------------------------------------------------


def test_the_target_epic_fetus_hits_three_things(promos: Any) -> None:
    game = new_game(library_with(promos, "target"))

    fetus = give(game, "treasure_deck-active_items-target-epic_fetus")

    monster = only_monster(game, "monster_deck-bosses-base_game-greed", hp=9)

    mine = game.state.player(0)
    theirs = game.state.player(1)

    toughen(game, mine)
    toughen(game, theirs)

    before = (monster.hp, theirs.hp, mine.hp)

    assert activate(game, fetus).accepted

    assert pick(game, 0, monster).accepted
    assert pick(game, 0, theirs).accepted

    assert (monster.hp, theirs.hp, mine.hp) == (
        before[0] - 1,
        before[1] - 1,
        before[2] - 1,
    )


def test_dead_eye_sharpens_on_monsters_only(promos: Any) -> None:
    from fsme.rules import ATTACK, static_value

    game = new_game(library_with(promos, "target"))

    give(game, "treasure_deck-passive_items-target-dead_eye")

    monster = only_monster(game, "monster_deck-bosses-base_game-greed", hp=9)

    before = static_value(game.state, ATTACK, 0, 1)

    bomb = deal(game, "loot_deck-bombs-base_game-bomb")

    assert play(game, bomb).accepted
    assert pick(game, 0, monster).accepted

    assert static_value(game.state, ATTACK, 0, 1) == before + 1

    toughen(game, game.state.player(1))

    game.state.player(0).additional_loot_plays += 1

    assert play(game, deal(game, "loot_deck-bombs-base_game-bomb")).accepted
    assert pick(game, 0, game.state.player(1)).accepted

    assert static_value(game.state, ATTACK, 0, 1) == before + 1, (
        "players are not monsters"
    )


# ----------------------------------------------------------------------
# G Fuel
# ----------------------------------------------------------------------


def test_the_g_fuel_can_wakes_a_character(promos: Any) -> None:
    game = new_game(library_with(promos, "g_fuel"))

    can = give(game, "treasure_deck-active_items-g_fuel-g_fuel")

    theirs = game.state.player(1).character

    assert theirs is not None
    theirs.tapped = True

    assert activate(game, can).accepted
    assert pick(game, 0, theirs).accepted

    assert not theirs.tapped


def test_isaacs_tears_fill_up_and_go_off(promos: Any) -> None:
    game = new_game(library_with(promos, "g_fuel"), players=3, rolls=[1] * 8)

    tears = give(game, "treasure_deck-paid_items-g_fuel-isaac_s_tears")

    monster = only_monster(game, "monster_deck-bosses-base_game-greed", hp=9)

    for player in game.state.players:
        toughen(game, player)

    game.state.player(0).additional_loot_plays += 6

    for _ in range(6):
        assert play(
            game, deal(game, "loot_deck-pills_runes-base_game-pills")
        ).accepted

    assert tears.counters.get("tear") == 6

    hp = [player.hp for player in game.state.players]
    monster_hp = monster.hp

    assert activate(game, tears).accepted

    assert tears.counters.get("tear") == 0
    assert monster.hp == monster_hp - 1
    assert [player.hp for player in game.state.players] == [hp[0], hp[1] - 1, hp[2] - 1]


def test_the_g_fuel_brimstone_fires_on_a_six(promos: Any) -> None:
    game = new_game(library_with(promos, "g_fuel"), rolls=[6])

    give(game, "treasure_deck-passive_items-g_fuel-brimstone")

    monster = only_monster(game, "monster_deck-bosses-base_game-greed", hp=9)

    hp = monster.hp

    assert play(game, deal(game, "loot_deck-pills_runes-base_game-pills")).accepted

    assert pick(game, 0, monster).accepted

    assert monster.hp == hp - 1


def test_the_g_fuel_powder_feeds_and_wakes_its_owner(promos: Any) -> None:
    game = new_game(library_with(promos, "g_fuel"))

    before = game.state.player(0).max_hp

    give(game, "treasure_deck-passive_items-g_fuel-g_fuel")

    assert game.state.player(0).max_hp == before + 1

    character = game.state.player(0).character

    assert character is not None
    character.tapped = True

    end_turn(game)

    assert not character.tapped


# ----------------------------------------------------------------------
# Mewgenics
# ----------------------------------------------------------------------


def test_the_radical_rat_bites_a_player_on_a_low_roll(promos: Any) -> None:
    game = new_game(library_with(promos, "mewgenics"), rolls=[1])

    only_monster(game, "monster_deck-bosses-mewgenics-radical_rat", hp=4)

    end_turn(game)

    assert [player.alive for player in game.state.players].count(False) == 1


def test_the_radical_rat_bites_a_monster_on_a_high_roll(promos: Any) -> None:
    game = new_game(library_with(promos, "mewgenics"), rolls=[5])

    rat = only_monster(game, "monster_deck-bosses-mewgenics-radical_rat", hp=4)
    other = summon(game, "monster_deck-bosses-base_game-greed")

    before = [rat.hp, other.hp]

    end_turn(game)

    assert [rat.hp, other.hp] != before


def test_the_mini_nuke_needs_nine_deaths(promos: Any) -> None:
    game = new_game(library_with(promos, "mewgenics"))

    nuke = give(game, "treasure_deck-one_use_items-mewgenics-mini_nuke")

    refused = activate(game, nuke)

    assert not refused.accepted
    assert "counter" in str(refused.reason)

    monster = only_monster(game, "monster_deck-bosses-base_game-greed", hp=1)

    slay(game, monster)

    assert nuke.counters.get("nuke") == 1, "one death, one counter"

    nuke.counters["nuke"] = 9

    assert activate(game, nuke).accepted

    assert nuke in game.state.treasure_discard.cards
    assert [player.alive for player in game.state.players] == [False, False]


# ----------------------------------------------------------------------
# Nendoroid, Youtooz, Star, Bum-bo
# ----------------------------------------------------------------------


def test_the_nendoroid_guppys_head_pays_a_card_for_a_look(promos: Any) -> None:
    game = new_game(library_with(promos, "nendoroid"))

    head = starting_item(game, "starting_items-nendoroid-guppy_s_head")

    game.state.player(0).hand.cards.clear()

    gift = deal(game, "loot_deck-1-base_game-a_penny")
    kept = deal(game, "loot_deck-2-base_game-2_cents")

    top = list(reversed(game.state.loot_deck.cards[-2:]))

    assert activate(game, head).accepted
    assert pick(game, 0, gift).accepted

    # The two cards go back in the order they are named, last on top.
    assert choose(game, 0, 1, 0).accepted

    assert gift in game.state.player(1).hand.cards
    assert kept in game.state.player(0).hand.cards
    assert top[0] in game.state.player(0).hand.cards, "the loot came off the top"


def test_the_nendoroid_guppys_head_wakes_on_a_four(promos: Any) -> None:
    game = new_game(library_with(promos, "nendoroid"), rolls=[4])

    head = starting_item(game, "starting_items-nendoroid-guppy_s_head")

    head.tapped = True

    assert play(game, deal(game, "loot_deck-pills_runes-base_game-pills")).accepted

    assert not head.tapped


def test_the_youtooz_devil_deal_finds_a_guppy_item(promos: Any) -> None:
    game = new_game(library_with(promos, "youtooz"))

    player = game.state.player(0)
    toughen(game, player)

    assert play(
        game, deal(game, "monster_deck-good_events-youtooz-devil_deal")
    ).accepted

    answer(
        game,
        "Take 2 damage. Search the treasure deck for a Guppy item, gain it, "
        "then shuffle the treasure deck.",
    )

    found = pending(game, 0).options[0]

    assert choose(game, 0, 0).accepted

    assert found in player.treasures.cards
    assert found.has_tag("guppy")


def test_the_bag_of_trash_sells_three_things(promos: Any) -> None:
    game = new_game(library_with(promos, "the_legend_of_bum_bo"))

    bag = starting_item(game, "starting_items-the_legend_of_bum_bo-bag_o_trash")

    player = game.state.player(0)
    player.pennies = 4

    hand = player.hand_size

    assert activate(game, bag, ability=1).accepted

    assert player.pennies == 0
    assert player.hand_size == hand + 1

    refused = activate(game, bag, ability=2)

    assert not refused.accepted


# ----------------------------------------------------------------------
# Dick Knot, Tapeworm, Retro
# ----------------------------------------------------------------------


def test_the_dick_knot_grows_with_every_attack(promos: Any) -> None:
    game = new_game(library_with(promos, "dick_knots"), rolls=[6, 6, 6, 6, 6, 6, 6])

    knot = only_monster(
        game, "monster_deck-basic_enemies-dick_knots-dick_knot", hp=9
    )

    printed = (int(knot.definition.roll or 0), int(knot.definition.attack or 0))

    reach_action_phase(game)

    assert game.act(CommandType.ATTACK, 0, index=0).accepted

    assert difficulty_of(game, knot) == printed[0] + 1
    assert attack_of(game, knot) == printed[1] + 1


def test_the_dick_knot_takes_the_table_with_it(promos: Any) -> None:
    game = new_game(library_with(promos, "dick_knots"))

    knot = only_monster(
        game, "monster_deck-basic_enemies-dick_knots-dick_knot", hp=9
    )

    knot.counters["knot"] = 6

    end_turn(game)

    assert not knot.alive
    assert not game.state.player(1).alive, "the player whose turn began"


def test_the_rainbow_tapeworm_becomes_something_else(promos: Any) -> None:
    game = new_game(library_with(promos, "tapeworm"), rolls=[5])

    worm = play(
        game, deal(game, "loot_deck-trinkets-tapeworm-rainbow_tapeworm")
    )

    assert worm.accepted

    copy = game.state.player(0).treasures.cards[-1]

    # Whatever the other player started with is cleared away: their items ask
    # questions of their own at the start of a turn, and this test is about
    # the worm.
    game.state.player(1).treasures.cards.clear()

    meal = give(game, "treasure_deck-passive_items-base_game-breakfast", player=1)
    give(game, "treasure_deck-passive_items-base_game-the_relic", player=1)

    before = game.state.player(0).max_hp

    end_turn(game)
    end_turn(game)

    assert pick(game, 0, meal).accepted

    assert copy.copy_of is meal.definition
    assert game.state.player(0).max_hp == before + 1

    end_turn(game)

    assert copy.copy_of is None, "till the end of your turn"


def test_the_retro_eden_orders_what_it_puts_back(promos: Any) -> None:
    library = library_with(promos, "retro")

    game = Game.from_content(library, ["Ann", "Bo"], seed=1234)

    player = game.state.player(1)

    player.character = CardInstance(
        definition=game.runtime.cards.get("characters-retro-eden"),
        instance_id=game.state.ids.allocate("character"),
        owner=1,
        controller=1,
    )
    player.treasures.cards.clear()

    assert game.start().accepted

    top = list(reversed(game.state.treasure_deck.cards[-3:]))

    assert choose(game, 1, 0).accepted

    # The two left over go under the deck in the order they are named.
    assert choose(game, 1, 1, 0).accepted

    assert top[0] in player.treasures.cards

    # Moved to the bottom in the order named, so the last one named sits
    # deepest.
    assert list(game.state.treasure_deck.cards[:2]) == [top[1], top[2]]


def test_the_one_up_buys_a_life_and_a_swing(promos: Any) -> None:
    game = new_game(library_with(promos, "retro"))

    life = give(game, "treasure_deck-passive_items-retro-1_up")

    player = game.state.player(0)
    toughen(game, player)

    attacks = player.attacks_left

    hurt(game, player, amount=player.hp)

    assert player.alive
    assert player.hp == player.max_hp
    assert life in game.state.treasure_discard.cards
    assert player.attacks_left == attacks + 1


def test_the_one_up_says_nothing_on_somebody_elses_turn(promos: Any) -> None:
    game = new_game(library_with(promos, "retro"))

    give(game, "treasure_deck-passive_items-retro-1_up", player=1)

    victim = game.state.player(1)

    hurt(game, victim, amount=victim.hp)

    assert not victim.alive


def test_every_implemented_promo_card_keeps_its_text(promos: Any) -> None:
    for expansion in (
        "gish",
        "target",
        "g_fuel",
        "mewgenics",
        "nendoroid",
        "youtooz",
        "the_legend_of_bum_bo",
        "dick_knots",
        "tapeworm",
        "retro",
    ):
        for definition in promos.get(expansion).definitions:
            if not definition.abilities and not definition.statics:
                continue

            assert definition.metadata.get("text", "").strip(), definition.id


def test_the_tapeworm_lays_an_egg_and_hatches_from_the_discard(promos: Any) -> None:
    """
    "When this dies put an egg counter on the active player. When a player with
    an egg counter dies and this is in discard, remove their egg counters and
    put this back into an active monster slot."
    """
    game = new_game(library_with(promos, "tapeworm"), players=2)

    worm = only_monster(game, "monster_deck-basic_enemies-tapeworm-tapeworm", hp=1)

    active = game.state.turn.active_player

    slay(game, worm, killer=active)

    while game.runtime.awaiting_decision is not None:
        decision = game.runtime.awaiting_decision
        choose(game, decision.player, *([0] if decision.options else []))

    assert game.state.player(active).counters.get("egg") == 1
    assert worm in game.state.monster_discard.cards

    game.runtime.context.apply("kill", [game.state.player(active)])
    game.runtime.run()

    while game.runtime.awaiting_decision is not None:
        decision = game.runtime.awaiting_decision
        choose(game, decision.player, *([0] if decision.options else []))

    assert game.state.player(active).counters.get("egg", 0) == 0
    assert worm in game.state.active_monsters.cards
    assert worm.alive is True
