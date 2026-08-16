"""
The alternate-art set, played in a game that contains it.

These cards share names with the base game and not much else: an alternate
Larry Jr. gains attack where the printed one gains difficulty, and an
alternate Pin shrugs off two attack rolls where the printed one shrugs off
one. So they are read and tested as their own cards, against their own text.
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
    summon,
    toughen,
)

from fsme.cards import CardInstance
from fsme.commands import CommandType
from fsme.content import ContentLibrary, ContentLoader
from fsme.game import Game
from fsme.rules import STARTING_COINS
from fsme.runtime.vocabulary import engine_vocabulary
from fsme.state import GamePhase

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def alt_art() -> ContentLibrary:
    """
    A library holding the base game and the alternate-art set together.

    The alternate set is not a game on its own — it has no full deck of
    anything — and in play it is shuffled in with the cards it was printed
    alongside.
    """
    library = ContentLoader(engine_vocabulary()).load_root(CONTENT_ROOT)

    only = ContentLibrary()
    only.add(library.get("base_game"))
    only.add(library.get("alt_art"))

    return only


def new_game(
    alt_art: ContentLibrary,
    players: int = 2,
    seed: int = 1234,
    rolls: list[int] | None = None,
) -> Game:
    from test_combat import FixedRNG

    game = Game.from_content(
        alt_art,
        ["Ann", "Bo", "Cy"][:players],
        seed=seed,
        rng=FixedRNG(rolls) if rolls is not None else None,
    )

    assert game.start().accepted

    return game


def text_of(game: Game, card_id: str) -> str:
    return str(game.runtime.cards.get(card_id).metadata["text"])


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


# ----------------------------------------------------------------------
# Characters
# ----------------------------------------------------------------------


def seated_as(
    alt_art: ContentLibrary,
    card_id: str,
    seat: int = 0,
    players: int = 2,
) -> Game:
    game = Game.from_content(alt_art, ["Ann", "Bo", "Cy"][:players], seed=1234)

    player = game.state.player(seat)

    player.character = CardInstance(
        definition=game.runtime.cards.get(card_id),
        instance_id=game.state.ids.allocate("character"),
        owner=seat,
        controller=seat,
    )

    assert game.start().accepted

    return game


def activate_character(game: Game, player: int = 0) -> Any:
    return game.act(CommandType.ACTIVATE_TREASURE, player, zone="character")


def test_a_character_buys_another_loot_play(alt_art: ContentLibrary) -> None:
    game = seated_as(alt_art, "characters-alt_art-judas")

    before = game.state.player(0).additional_loot_plays

    assert activate_character(game).accepted

    assert game.state.player(0).additional_loot_plays == before + 1


def test_the_capricious_may_sweep_the_shop_instead(alt_art: ContentLibrary) -> None:
    game = seated_as(alt_art, "characters-alt_art-the_capricious")

    assert activate_character(game).accepted

    answer(game, "Put a shop item into discard.")

    for_sale = list(game.state.treasure_shop.cards)

    swept = pending(game, 0).options[0]

    assert choose(game, 0, 0).accepted

    assert swept in game.state.treasure_discard.cards
    assert swept not in game.state.treasure_shop.cards

    # The card puts a shop item in the discard; it does not close the slot.
    # COMPREHENSIVE_RULES.md 9 refills a slot as soon as it is empty, so the
    # shop is full again with a different card in it. This test used to assert
    # the shop was left one short, which is what the engine did before the
    # refill covered every way of emptying a slot rather than only a purchase.
    assert len(game.state.treasure_shop.cards) == len(for_sale)


def test_the_lost_wakes_a_character_at_the_end_of_its_turn(
    alt_art: ContentLibrary,
) -> None:
    game = seated_as(alt_art, "characters-alt_art-the_lost")

    other = game.state.player(1).character

    assert other is not None
    other.tapped = True

    while game.state.turn.phase is not GamePhase.END:
        assert game.act(CommandType.END_PHASE, 0).accepted

    assert game.act(CommandType.END_TURN, 0).accepted

    answer(game, "yes")
    assert pick(game, 0, other).accepted

    assert not other.tapped


# ----------------------------------------------------------------------
# Loot and events
# ----------------------------------------------------------------------


def test_death_kills_the_whole_table(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art, players=3)

    assert play(game, deal(game, "loot_deck-cards_miscellaneous-alt_art-xiii_death")).accepted

    assert [player.alive for player in game.state.players] == [False, False, False]


def test_the_stars_pays_the_table_and_then_you(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art, players=3)

    before = [player.treasure_count for player in game.state.players]

    assert play(
        game, deal(game, "loot_deck-cards_miscellaneous-alt_art-xvii_the_stars")
    ).accepted

    after = [player.treasure_count for player in game.state.players]

    assert after[0] == before[0] + 2, "one with everybody, one on your own"
    assert after[1] == before[1] + 1
    assert after[2] == before[2] + 1


def test_the_devil_deal_searches_the_loot_deck(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art)

    player = game.state.player(0)
    toughen(game, player)

    hp = player.hp
    hand = player.hand_size

    assert play(
        game, deal(game, "monster_deck-good_events-alt_art-devil_deal")
    ).accepted

    answer(
        game,
        "Take 2 damage. Search the loot deck for a loot card, put it in your "
        "hand, then shuffle the loot deck.",
    )

    wanted = pending(game, 0).options[3]

    assert choose(game, 0, 3).accepted

    assert player.hp == hp - 2
    assert wanted in player.hand.cards
    assert player.hand_size == hand + 1, "the event left the hand, the search came in"


def test_the_devil_deal_may_simply_pay(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art)

    player = game.state.player(0)
    toughen(game, player)

    hp = player.hp

    assert play(
        game, deal(game, "monster_deck-good_events-alt_art-devil_deal")
    ).accepted

    answer(game, "Gain 6¢. Take 1 damage.")

    assert player.pennies == STARTING_COINS + 6
    assert player.hp == hp - 1


# ----------------------------------------------------------------------
# Monsters
# ----------------------------------------------------------------------


def test_begotten_hardens_when_it_is_hurt(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art)

    begotten = only_monster(
        game, "monster_deck-basic_enemies-alt_art-begotten", hp=5
    )

    printed = int(begotten.definition.roll or 0)

    assert difficulty_of(game, begotten) == printed

    begotten.hp = 2

    assert difficulty_of(game, begotten) == printed + 2


def test_the_alternate_larry_jr_gains_attack_not_difficulty(
    alt_art: ContentLibrary,
) -> None:
    game = new_game(alt_art)

    larry = only_monster(game, "monster_deck-bosses-alt_art-larry_jr", hp=4)

    printed = int(larry.definition.attack or 0)

    larry.hp = 2

    assert attack_of(game, larry) == printed + 1
    assert difficulty_of(game, larry) == int(larry.definition.roll or 0)


def test_the_alternate_dark_one_gains_two_attack(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art)

    dark = only_monster(game, "monster_deck-bosses-alt_art-dark_one", hp=3)

    printed = int(dark.definition.attack or 0)

    hurt(game, dark, amount=1)

    assert attack_of(game, dark) == printed + 2


def test_daddy_long_legs_arms_every_monster_on_a_one(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art, rolls=[1])

    legs = only_monster(game, "monster_deck-bosses-alt_art-daddy_long_legs", hp=5)
    other = summon(game, "monster_deck-bosses-base_game-greed")

    printed = int(other.definition.attack or 0)

    assert play(game, deal(game, "loot_deck-pills_runes-base_game-pills")).accepted

    assert attack_of(game, other) == printed + 1
    assert attack_of(game, legs) == int(legs.definition.attack or 0) + 1


def test_the_alternate_pin_shrugs_off_fives_as_well_as_sixes(
    alt_art: ContentLibrary,
) -> None:
    game = new_game(alt_art)

    pin = only_monster(game, "monster_deck-bosses-alt_art-pin", hp=2)

    hp = pin.hp

    game.runtime.context.apply(
        "deal_damage", [pin], amount=1, combat=True, roll=5
    )
    game.runtime.run()

    assert pin.hp == hp, "a five deals nothing"

    game.runtime.context.apply(
        "deal_damage", [pin], amount=1, combat=True, roll=4
    )
    game.runtime.run()

    assert pin.hp == hp - 1, "a four still lands"


def test_the_alternate_duke_of_flies_opens_two_slots(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art)

    duke = only_monster(game, "monster_deck-bosses-alt_art-the_duke_of_flies", hp=3)

    slots = game.state.monster_slots

    slay(game, duke)

    assert game.state.monster_slots == slots + 2


def test_the_alternate_mulligan_opens_the_slot_it_is_told_to(
    alt_art: ContentLibrary,
) -> None:
    game = new_game(alt_art)

    mulligan = only_monster(
        game, "monster_deck-basic_enemies-alt_art-mulligan", hp=2
    )

    shops = game.state.shop_slots

    slay(game, mulligan)

    answer(game, "Expand shop slots by 1.")

    assert game.state.shop_slots == shops + 1


def test_the_alternate_mulliboom_spreads_its_damage(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art)

    boom = only_monster(game, "monster_deck-basic_enemies-alt_art-mulliboom", hp=1)
    bystander = summon(game, "monster_deck-bosses-base_game-greed")

    victim = game.state.player(1)
    toughen(game, victim)
    toughen(game, game.state.player(0))

    monster_hp = bystander.hp
    theirs = victim.hp
    mine = game.state.player(0).hp

    slay(game, boom)

    assert pick(game, 0, bystander).accepted
    assert pick(game, 0, victim).accepted

    assert bystander.hp == monster_hp - 1
    assert victim.hp == theirs - 1
    assert game.state.player(0).hp == mine - 1


def test_the_alternate_famine_empties_a_hand(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art)

    famine = only_monster(game, "monster_deck-bosses-alt_art-famine", hp=3)

    assert game.state.player(0).hand_size > 0

    slay(game, famine)

    assert game.state.player(0).hand_size == 0


def test_hornfel_lashes_out_at_a_monster(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art)

    hornfel = only_monster(game, "monster_deck-bosses-alt_art-hornfel", hp=2)
    other = summon(game, "monster_deck-bosses-base_game-greed")

    before = [hornfel.hp, other.hp]

    game.runtime.context.apply(
        "deal_damage",
        [game.state.player(0)],
        amount=1,
        combat=True,
        dealt_by=hornfel,
    )
    game.runtime.run()

    assert [hornfel.hp, other.hp] != before, "somebody was hit"


def test_the_alternate_monstro_destroys_at_random(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art, rolls=[2])

    monstro = only_monster(game, "monster_deck-bosses-alt_art-monstro", hp=2)

    give(game, "treasure_deck-passive_items-base_game-breakfast")

    before = game.state.player(0).treasure_count

    slay(game, monstro)

    assert game.state.player(0).treasure_count == before - 1
    assert game.state.treasure_discard.cards


def test_the_alternate_monstro_spares_on_a_high_roll(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art, rolls=[4])

    monstro = only_monster(game, "monster_deck-bosses-alt_art-monstro", hp=2)

    give(game, "treasure_deck-passive_items-base_game-breakfast")

    before = game.state.player(0).treasure_count

    slay(game, monstro)

    assert game.state.player(0).treasure_count == before


def test_the_alternate_rag_man_buries_itself_one_card_down(
    alt_art: ContentLibrary,
) -> None:
    game = new_game(alt_art, rolls=[6])

    rag = only_monster(game, "monster_deck-bosses-alt_art-rag_man", hp=2)

    slay(game, rag)

    assert list(game.state.monster_deck.cards)[-2] is rag


def test_moms_hand_ends_the_turn_when_it_connects(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art)

    hand = only_monster(game, "monster_deck-basic_enemies-alt_art-mom_s_hand", hp=2)

    player = game.state.player(0)
    toughen(game, player)

    game.runtime.context.apply(
        "deal_damage", [player], amount=1, combat=True, dealt_by=hand
    )
    game.runtime.run()

    assert game.state.turn.active_player != 0


def test_the_alternate_pestilence_passes_the_blow_along(
    alt_art: ContentLibrary,
) -> None:
    game = new_game(alt_art, players=3)

    pestilence = only_monster(game, "monster_deck-bosses-alt_art-pestilence", hp=4)

    for player in game.state.players:
        toughen(game, player)

    chosen = game.state.player(1)
    victim = game.state.player(2)

    theirs = chosen.hp
    victims = victim.hp

    slay(game, pestilence)

    assert pick(game, 0, chosen).accepted

    # The chosen player is the one who decides where their damage lands.
    assert pick(game, 1, victim).accepted

    assert chosen.hp == theirs - 1
    assert victim.hp == victims - 1


def test_the_alternate_lamb_takes_two_souls(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art, players=3)

    lamb = only_monster(game, "monster_deck-epic_boss-alt_art-the_lamb", hp=6)

    for seat in (1, 2):
        game.runtime.context.apply("gain_soul", [game.state.player(seat)], count=1)

    game.runtime.run()

    slay(game, lamb)

    answer(game, "yes")

    assert choose(game, 0, 0, 1).accepted

    assert game.state.player(1).soul_count == 0
    assert game.state.player(2).soul_count == 0


# ----------------------------------------------------------------------
# Treasures
# ----------------------------------------------------------------------


def test_the_alternate_epic_fetus_hits_the_room_and_its_owner(
    alt_art: ContentLibrary,
) -> None:
    game = new_game(alt_art)

    fetus = give(game, "treasure_deck-active_items-alt_art-epic_fetus")

    monster = only_monster(game, "monster_deck-bosses-base_game-greed", hp=9)
    other = summon(game, "monster_deck-basic_enemies-base_game-portal")

    player = game.state.player(0)
    toughen(game, player)

    hp = player.hp
    monsters = [monster.hp, other.hp]

    assert activate(game, fetus).accepted

    assert [monster.hp, other.hp] == [monsters[0] - 1, monsters[1] - 1]
    assert player.hp == hp - 1


def test_godhead_reads_a_roll_from_the_other_side(alt_art: ContentLibrary) -> None:
    from test_official_cards import answering_game, pass_until_roll, pass_until_settled

    library = alt_art

    game = answering_game(library, [2])

    godhead = give(game, "treasure_deck-active_items-alt_art-godhead")

    assert play(game, deal(game, "loot_deck-pills_runes-base_game-pills")).accepted

    assert pass_until_roll(game) is not None
    assert game.state.pending_roll.value == 2

    assert activate(game, godhead).accepted

    pass_until_settled(game)

    # A two becomes a five, and Pills! charges 4¢ on 5-6 instead of paying 7¢.
    assert game.state.player(0).pennies == 0


def attack_the_first_monster(game: Game) -> Any:
    while game.state.turn.phase is not GamePhase.ACTION:
        assert game.act(CommandType.END_PHASE, 0).accepted

    return game.act(CommandType.ATTACK, 0, index=0)


def test_big_bony_punishes_a_miss(alt_art: ContentLibrary) -> None:
    # A miss, the die Big Bony makes them roll, then the hit that ends the
    # fight: a script that only ever misses would run until somebody died.
    game = new_game(alt_art, rolls=[1, 2, 6])

    only_monster(game, "monster_deck-basic_enemies-alt_art-big_bony", hp=1)

    player = game.state.player(0)
    toughen(game, player)

    hp = player.hp

    assert attack_the_first_monster(game).accepted

    # One from the monster's blow, one for having missed.
    assert player.hp == hp - 2


def test_big_bony_says_nothing_about_a_hit(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art, rolls=[6])

    bony = only_monster(game, "monster_deck-basic_enemies-alt_art-big_bony", hp=1)

    player = game.state.player(0)
    toughen(game, player)

    hp = player.hp

    assert attack_the_first_monster(game).accepted

    assert player.hp == hp
    assert not bony.alive


def test_polycephalus_turns_the_next_attack_roll_over(
    alt_art: ContentLibrary,
) -> None:
    game = new_game(alt_art, rolls=[2])

    poly = only_monster(game, "monster_deck-bosses-alt_art-polycephalus", hp=2)

    hurt(game, poly, amount=1)

    assert attack_the_first_monster(game).accepted

    # A two would have missed a 4+; read from the other side it is a five.
    assert not poly.alive


def test_polycephalus_leaves_an_unhurt_roll_alone(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art, rolls=[2, 6])

    poly = only_monster(game, "monster_deck-bosses-alt_art-polycephalus", hp=1)

    player = game.state.player(0)
    toughen(game, player)

    assert attack_the_first_monster(game).accepted

    # Nothing hurt it first, so the two stayed a two and missed.
    assert player.hp < player.max_hp
    assert not poly.alive, "the six that followed landed"


def test_the_alternate_satan_kills_on_the_third_six(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art, rolls=[6, 6, 6])

    only_monster(game, "monster_deck-epic_boss-alt_art-satan", hp=6)

    game.state.player(0).additional_loot_plays += 2

    for roll in range(3):
        assert play(
            game, deal(game, "loot_deck-pills_runes-base_game-pills")
        ).accepted

        assert game.state.player(0).alive == (roll < 2)


def test_the_alternate_satan_counts_a_five_as_a_six(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art, rolls=[5, 5, 5])

    only_monster(game, "monster_deck-epic_boss-alt_art-satan", hp=6)

    game.state.player(0).additional_loot_plays += 2

    for _ in range(3):
        assert play(
            game, deal(game, "loot_deck-pills_runes-base_game-pills")
        ).accepted

    assert not game.state.player(0).alive, "every five was a six"


def test_the_alternate_satan_spares_a_table_that_rolls_low(
    alt_art: ContentLibrary,
) -> None:
    game = new_game(alt_art, rolls=[4, 4, 4])

    only_monster(game, "monster_deck-epic_boss-alt_art-satan", hp=6)

    game.state.player(0).additional_loot_plays += 2

    for _ in range(3):
        assert play(
            game, deal(game, "loot_deck-pills_runes-base_game-pills")
        ).accepted

    assert game.state.player(0).alive


def test_ultra_greed_gilds_an_item_and_takes_it(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art, rolls=[6])

    greed = only_monster(game, "monster_deck-epic_boss-alt_art-ultra_greed", hp=1)

    theirs = give(game, "treasure_deck-passive_items-base_game-breakfast", player=1)
    give(game, "treasure_deck-passive_items-base_game-the_relic", player=1)

    assert attack_the_first_monster(game).accepted

    assert pick(game, 0, theirs).accepted

    assert theirs.counters.get("gold") == 1
    assert not greed.alive

    answer(game, "yes")

    assert theirs in game.state.player(0).treasures.cards


def test_fistula_hardens_its_neighbours_as_it_is_hurt(
    alt_art: ContentLibrary,
) -> None:
    game = new_game(alt_art)

    fistula = only_monster(game, "monster_deck-bosses-alt_art-fistula", hp=9)
    other = summon(game, "monster_deck-bosses-base_game-greed")

    printed = int(other.definition.roll or 0)

    assert difficulty_of(game, other) == printed

    hurt(game, fistula, amount=1)

    assert difficulty_of(game, other) == printed + 1

    hurt(game, fistula, amount=1)

    assert difficulty_of(game, other) == printed + 2
    assert difficulty_of(game, fistula) == int(fistula.definition.roll or 0), (
        "other monsters, not this one"
    )


def test_the_alternate_guppys_paw_pays_hit_points_for_items(
    alt_art: ContentLibrary,
) -> None:
    game = new_game(alt_art)

    paw = give(game, "treasure_deck-active_items-alt_art-guppy_s_paw")

    fodder = give(game, "treasure_deck-passive_items-base_game-the_relic")
    give(game, "treasure_deck-passive_items-base_game-dry_baby")

    before = game.state.player(0).max_hp

    assert activate(game, paw).accepted
    assert pick(game, 0, fodder).accepted

    assert fodder in game.state.treasure_discard.cards
    assert paw.counters.get("paw") == 1
    assert game.state.player(0).max_hp == before + 1, "a counter is worth a heart"


def test_dingle_silences_the_item_it_fouls(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art)

    dingle = only_monster(game, "monster_deck-bosses-alt_art-dingle", hp=9)

    meal = give(game, "treasure_deck-passive_items-base_game-breakfast", player=1)
    give(game, "treasure_deck-passive_items-base_game-the_relic", player=1)

    fed = game.state.player(1).max_hp

    hurt(game, dingle, amount=1)

    assert pick(game, 0, meal).accepted

    assert meal.counters.get("poo") == 1
    assert not meal.face.statics, "a fouled item says nothing"
    assert game.state.player(1).max_hp == fed - 1

    meal.counters["poo"] = 0

    assert meal.face.statics, "and speaks again when the counter is gone"


def test_the_alternate_bloat_kills_on_a_matching_pair(
    alt_art: ContentLibrary,
) -> None:
    game = new_game(alt_art, rolls=[1, 3, 3])

    only_monster(game, "monster_deck-bosses-alt_art-the_bloat", hp=5)

    player = game.state.player(0)
    toughen(game, player)

    assert attack_the_first_monster(game).accepted

    assert not player.alive


def test_the_alternate_bloat_spares_a_mismatch(alt_art: ContentLibrary) -> None:
    game = new_game(alt_art, rolls=[1, 3, 4, 6])

    bloat = only_monster(game, "monster_deck-bosses-alt_art-the_bloat", hp=1)

    player = game.state.player(0)
    toughen(game, player)

    assert attack_the_first_monster(game).accepted

    assert player.alive
    assert not bloat.alive, "the six that followed the miss landed"


def test_every_implemented_alt_art_card_keeps_its_text(
    alt_art: ContentLibrary,
) -> None:
    """
    Behaviour was written from a card's own text, so the text must be there.
    """
    for definition in alt_art.get("alt_art").definitions:
        if not definition.abilities and not definition.statics:
            continue

        assert definition.metadata.get("text", "").strip(), definition.id
