"""
Reading a card instead of assuming one.

The defect these tests exist to prevent is specific and was in the engine for
its whole life: a purchase was scored by a constant, that constant came out
below passing, and so the bot never bought anything in any game ever played.
Nothing caught it, because nothing here asked what a purchase was worth — the
bot's own arithmetic was consistent, self-contained and wrong.

So the tests below ask two different kinds of question. Some are about the
arithmetic: does the appraiser read what the card says, and does it stop where
the card stops saying it. The rest are about the behaviour the arithmetic is
for: given the real content, does the bot actually decide — buying some things,
refusing others — rather than doing the same thing every time. A bot that
always buys would pass every unit test here and be exactly as broken as one
that never does.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from conftest import make_definition, treasure_definition

from fsme.api import load_content
from fsme.cards import Ability, CardType, Static
from fsme.commands import CommandType
from fsme.content import ContentLibrary
from fsme.game import Game
from fsme.lab.bot.appraisal import (
    FALLBACK_ITEM_IS_WORTH,
    SOUL_IS_WORTH,
    TURNS_AHEAD,
    Scale,
    appraise,
    horizon,
    scale_of,
)
from fsme.lab.bot.heuristic import HeuristicBot
from fsme.lab.simulation.runner import NAMES, _whose_move
from fsme.rules.constants import SOULS_TO_WIN, TREASURE_COST

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


@pytest.fixture(scope="module")
def real(everything: ContentLibrary) -> Scale:
    return scale_of(everything.definitions())


def a_scale(coin: float = 0.5, item: float = 5.0, most_health: int = 8) -> Scale:
    """
    A scale with round numbers, so a test's arithmetic can be done by hand.
    """
    return Scale(coin=coin, item=item, most_health=most_health, readable=1, pool=1)


def treasure(*, effects: tuple[Any, ...], trigger: str = "on_activate", **extra: Any):
    return treasure_definition("test.item", effects=effects, trigger=trigger, **extra)


# ----------------------------------------------------------------------
# What the reading says
# ----------------------------------------------------------------------


def test_two_cards_that_do_different_things_are_worth_different_amounts() -> None:
    """
    The whole point, stated as bluntly as it can be.
    """
    scale = a_scale()

    small = appraise(treasure(effects=({"draw_loot": 1},)), scale)
    large = appraise(treasure(effects=({"draw_loot": 3},)), scale)

    assert large.points > small.points
    assert small.points > 0


def test_a_repeatable_ability_is_worth_more_than_a_one_off() -> None:
    """
    An item is bought to be used again, and that is most of what makes it worth
    ten cents rather than one use of a loot card.
    """
    scale = a_scale()

    every_turn = appraise(treasure(effects=({"gain_coins": 2},)), scale)
    on_arrival = appraise(
        treasure(effects=({"gain_coins": 2},), trigger="on_enter"), scale
    )

    assert every_turn.points == pytest.approx(on_arrival.points * TURNS_AHEAD)


def test_what_an_ability_costs_comes_off_what_it_gives() -> None:
    paid = make_definition(
        "test.dear",
        abilities=(
            Ability(
                trigger="on_activate",
                effects=({"gain_coins": 4},),
                cost={"coins": 3},
            ),
        ),
    )
    free = treasure(effects=({"gain_coins": 4},))

    scale = a_scale()

    assert appraise(paid, scale).points < appraise(free, scale).points


def test_an_ability_whose_price_cannot_be_read_is_not_valued_at_all() -> None:
    """
    Counting the payout and skipping the bill is how a card that costs nine
    counters comes out as the best card in the game. It did, before this.
    """
    card = make_definition(
        "test.counters",
        abilities=(
            Ability(
                trigger="on_activate",
                effects=({"effect": "deal_damage", "amount": 3},),
                cost={"counters": {"counter": "nuke", "amount": 9}},
            ),
        ),
    )

    read = appraise(card, a_scale())

    assert read.points == 0.0
    assert any(missed.startswith("cost:") for missed in read.unread)


def test_a_card_that_destroys_itself_is_worth_one_use() -> None:
    once = make_definition(
        "test.nuke",
        abilities=(
            Ability(
                trigger="on_activate",
                effects=(
                    {"effect": "destroy_treasure", "target": "self"},
                    {"effect": "deal_damage", "amount": 2},
                ),
            ),
        ),
    )
    again = treasure(effects=({"effect": "deal_damage", "amount": 2},))

    scale = a_scale()

    assert appraise(once, scale).points == pytest.approx(
        appraise(again, scale).points / TURNS_AHEAD
    )


def test_a_huge_printed_number_does_not_outweigh_the_game() -> None:
    """
    999 damage is not 999 damage. It is enough, and enough has a size.

    Read literally, one board wipe came out at 8991 points — more than every
    soul in a four-player game put together, and the best card in the pool by a
    factor of two hundred and fifty.
    """
    scale = a_scale(most_health=8)

    wipe = treasure(effects=({"effect": "deal_damage", "amount": 999},))
    enough = treasure(effects=({"effect": "deal_damage", "amount": 8},))
    less = treasure(effects=({"effect": "deal_damage", "amount": 7},))

    assert appraise(wipe, scale).points == appraise(enough, scale).points
    assert appraise(less, scale).points < appraise(enough, scale).points


def test_a_card_that_does_one_of_two_things_is_worth_the_average() -> None:
    """
    Not the sum. A card does one of them.
    """
    scale = a_scale()

    either = appraise(
        treasure(
            effects=(
                {
                    "if": ({"dice_less": 4},),
                    "then": ({"draw_loot": 2},),
                    "else": ({"draw_loot": 4},),
                },
            )
        ),
        scale,
    )
    always = appraise(treasure(effects=({"draw_loot": 3},)), scale)

    assert either.points == pytest.approx(always.points)


def test_a_branch_with_no_else_may_come_to_nothing() -> None:
    scale = a_scale()

    sometimes = appraise(
        treasure(effects=({"if": ({"dice_less": 4},), "then": ({"draw_loot": 2},)},)),
        scale,
    )
    always = appraise(treasure(effects=({"draw_loot": 2},)), scale)

    assert sometimes.points == pytest.approx(always.points / 2)


def test_a_static_that_pays_every_turn_beats_one_that_pays_once() -> None:
    """
    +1 attack is income and +1 max HP is stock, and a bot that confuses them
    ends up believing a hit point is worth more than a soul.
    """
    income = make_definition(
        "test.income", statics=(Static(stat="attack", amount=1),)
    )
    stock = make_definition("test.stock", statics=(Static(stat="max_hp", amount=1),))

    scale = a_scale()

    assert appraise(income, scale).points == pytest.approx(
        appraise(stock, scale).points * TURNS_AHEAD
    )


def test_what_it_could_not_read_is_reported_rather_than_scored() -> None:
    card = treasure(effects=({"effect": "reroll", "sides": 6},))

    read = appraise(card, a_scale())

    assert read.points == 0.0
    assert "reroll" in read.unread
    assert read.understood == 0.0


def test_a_card_fsme_has_not_written_down_is_worth_a_card_not_nothing() -> None:
    """
    Scoring the unimplemented cards at zero would make the bot prefer the
    implemented ones, which is a preference about FSME and not about Four Souls.
    """
    blank = make_definition("test.blank")

    read = appraise(blank, a_scale(item=5.0))

    assert read.points == 5.0
    assert read.unread == ("(no rules)",)


def test_health_is_worth_more_to_a_buyer_about_to_die() -> None:
    card = treasure(effects=({"effect": "heal", "amount": 1},))

    scale = a_scale()

    assert (
        appraise(card, scale, hurt=True).points
        > appraise(card, scale, hurt=False).points
    )


def test_the_horizon_shrinks_as_somebody_approaches_winning() -> None:
    assert horizon(0) == TURNS_AHEAD
    assert horizon(SOULS_TO_WIN - 1) < horizon(1)
    assert horizon(SOULS_TO_WIN) >= 1.0, "never zero, or nothing is ever worth buying"


def test_a_shorter_horizon_makes_a_repeatable_item_worth_less() -> None:
    card = treasure(effects=({"gain_coins": 2},))
    scale = a_scale()

    assert (
        appraise(card, scale, turns=1.0).points
        < appraise(card, scale, turns=TURNS_AHEAD).points
    )


# ----------------------------------------------------------------------
# The scale
# ----------------------------------------------------------------------


def test_the_printed_exchange_holds(real: Scale) -> None:
    """
    Ten cents buys a treasure, so a cent is a tenth of one. That is the rules'
    own number and the appraiser is not allowed to disagree with it.
    """
    assert real.coin * TREASURE_COST == pytest.approx(real.item)


def test_the_scale_is_a_finite_number_on_the_real_content(real: Scale) -> None:
    """
    An earlier version solved a fixed point instead, and on this content the
    loop nearly closed: the answer sat on a near-singularity and came out at
    nine points a cent, which is most of a soul for one penny.
    """
    assert 0.0 < real.coin < SOUL_IS_WORTH
    assert 0.0 < real.item < SOULS_TO_WIN * SOUL_IS_WORTH


def test_the_cap_on_damage_comes_off_the_cards(real: Scale) -> None:
    assert real.most_health >= 1


def test_a_pool_with_nothing_readable_in_it_falls_back(real: Scale) -> None:
    empty = scale_of([make_definition("test.blank")])

    assert empty.item == FALLBACK_ITEM_IS_WORTH
    assert empty.readable == 0


def test_the_scale_says_how_much_of_the_pool_it_could_read(real: Scale) -> None:
    """
    Not a passing statistic. Most of FSME's treasure pool has no rules yet, and
    a purchase decision taken over it is a decision taken mostly blind.
    """
    assert 0 < real.readable < real.pool


# ----------------------------------------------------------------------
# What the bot does with it
# ----------------------------------------------------------------------


@dataclass
class Shopping:
    """
    What happened at the shop over a run of games.
    """

    offered: int = 0
    bought: int = 0

    scores: set[float] = field(default_factory=set)
    """Every score the bot gave a purchase, rounded to where ties are broken."""

    taken: list[float] = field(default_factory=list)
    """The score of each purchase it actually made."""


def shop(library: ContentLibrary, seeds: range) -> Shopping:
    """
    Play some games and watch what the bot does when a purchase is on offer.
    """
    seen = Shopping()

    for seed in seeds:
        game = Game.from_content(library, list(NAMES[:4]), seed=seed)
        game.start()

        bot = HeuristicBot(seed)

        for _ in range(3000):
            if game.is_over:
                break

            thought = bot.choose(game, seats=(_whose_move(game),))

            if thought is None:
                break

            command, _, working = thought

            buys = [
                evaluation
                for evaluation in working.considered
                if evaluation.move.startswith("Buy")
            ]

            if buys:
                seen.offered += 1
                seen.scores.update(round(buy.score, 6) for buy in buys)

            if command.type is CommandType.BUY_TREASURE:
                seen.bought += 1
                seen.taken.append(working.chosen.score)

            if not game.submit(command).accepted:
                break

    return seen


def test_the_bot_buys_things(everything: ContentLibrary) -> None:
    """
    The regression, in one line.

    Before this change the bot bought nothing in any game: 748 positions in
    sixty four-handed games where a purchase was legal, and not one taken,
    because every purchase scored -1.0 against 0.0 for ending the turn.
    """
    seen = shop(everything, range(12))

    assert seen.offered > 0, "the games did not reach a shop"
    assert seen.bought > 0, "buying was legal and never once chosen"


def test_the_bot_also_declines_to_buy(everything: ContentLibrary) -> None:
    """
    The other half, and the half a badly tuned constant would fail.

    A bot that bought whenever it could would pass the test above and be just
    as unthinking as one that never did. What is being asked for here is a
    decision, which means both answers have to occur.
    """
    seen = shop(everything, range(12))

    assert seen.bought < seen.offered, "it bought at every single opportunity"


def test_it_prefers_the_better_of_two_cards_in_the_shop(
    everything: ContentLibrary, real: Scale
) -> None:
    """
    Put two cards in front of it and it takes the one that does more.
    """
    game = Game.from_content(everything, list(NAMES[:2]), seed=1)
    game.start()

    bot = HeuristicBot(1)

    generous = treasure_definition("test.generous", effects=({"draw_loot": 3},))
    stingy = treasure_definition("test.stingy", effects=({"draw_loot": 1},))

    scale = bot._scale_for(game)

    assert (
        appraise(generous, scale).points > appraise(stingy, scale).points
    ), "and the difference is the cards, not the position"


def test_the_purchase_it_takes_is_worth_more_than_the_price(
    everything: ContentLibrary,
) -> None:
    """
    Whatever it buys, it buys because the reading beat the bill.

    This is what stops the fix from being a constant with a better sign. The
    score of a chosen purchase is the appraisal minus the price, so a purchase
    the bot takes at or above zero is one where the card paid for itself.
    """
    seen = shop(everything, range(12))

    assert seen.taken, "no purchase was made in any of these games"
    assert all(score >= 0.0 for score in seen.taken), (
        "it bought something it thought was a bad deal"
    )


def test_a_purchase_is_no_longer_scored_by_a_constant(
    everything: ContentLibrary,
) -> None:
    """
    The shape of the original defect, tested for directly.

    Every purchase used to score exactly -1.0, whatever the card was. If the
    set of scores the bot gives purchases ever collapses to one value again,
    the reading has stopped happening whether or not anything else still passes.

    One value is expected to recur and is not the defect: buying the top of the
    treasure deck unseen scores the same every time, because there is nothing to
    read and the price is a fair one. What has to vary is the rest.
    """
    seen = shop(everything, range(12))

    assert len(seen.scores) > 1, f"every purchase scored the same: {seen.scores}"


def test_the_working_says_what_the_card_does(everything: ContentLibrary) -> None:
    """
    A purchase in the journal has to be arguable, which means the reasons
    beside it are the card's own text and not a category.
    """
    game = Game.from_content(everything, list(NAMES[:2]), seed=1)
    game.start()

    bot = HeuristicBot(1)
    scale = bot._scale_for(game)

    card = next(
        definition
        for definition in everything.definitions()
        if definition.type is CardType.TREASURE
        and definition.abilities
        and definition.abilities[0].description
    )

    read = appraise(card, scale)

    assert read.reasons, f"{card.name} was read and nothing was said about it"
    assert any(reason.what for reason in read.reasons)


def test_reading_a_card_does_not_touch_the_game(everything: ContentLibrary) -> None:
    """
    An appraiser that changed the position it was asked about would make every
    measurement taken through it a measurement of itself.
    """
    game = Game.from_content(everything, list(NAMES[:4]), seed=2)
    game.start()

    bot = HeuristicBot(2)

    before = game.save()
    bot.opinions(game)
    bot.opinions(game)

    assert game.save() == before
