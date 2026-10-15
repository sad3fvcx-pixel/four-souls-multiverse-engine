"""
A card test on model 2 is read pair by pair.

Each seed is one game with the card and the same game without it, so what the
card did is the difference inside each pair. These tests hold the reading to
that: the mean and its error come from the differences, a share of games is
marked by the exact McNemar test, attack rolls are clustered by the game they
were rolled in, a pair is matched by its seed or refused, and a game that fell
over takes its pair out with it and is named.
"""

from __future__ import annotations

import math
import random

import pytest

from fsme.lab.analysis import (
    PairedRun,
    Seen,
    Tally,
    compare,
    compare_paired,
    read_out,
)
from fsme.lab.analysis.compare import (
    INDEPENDENT,
    MCNEMAR_EXACT,
    MCNEMAR_LINE,
    MIN_DIFFERING,
    PAIRED,
    PAIRED_MEAN,
    PAIRED_RATIO,
    Comparison,
    Difference,
)
from fsme.lab.analysis.paired import Played, mcnemar, paired_ratio, paired_share

CARD = "a-card"

OLD_KEYS = {"subject", "games", "appeared", "can_be_about_the_card", "verdict"}
OLD_KEYS |= {"differences", "errors_with", "errors_without", "rng_model"}
OLD_DIFFERENCE_KEYS = {"name", "with", "without", "change", "error", "beyond_noise"}


def game(
    turns: int = 50,
    *,
    commands: int = 200,
    deaths: int = 1,
    hits: int = 5,
    rolls: int = 10,
    finished: bool = True,
    played: bool = False,
) -> Tally:
    """One game's tally, with only what a paired comparison reads."""
    tally = Tally(games=1, finished=int(finished))

    tally.turns = turns
    tally.commands = commands
    tally.deaths = deaths

    tally.turns_squared = turns * turns
    tally.commands_squared = commands * commands
    tally.deaths_squared = deaths * deaths
    tally.attack_hits = hits
    tally.attack_rolls = rolls

    if played:
        tally.cards[CARD] = Seen(name=CARD, games=1, times=1)

    return tally


def kept(pairs: list[tuple[Tally, Tally]], first_seed: int = 0) -> PairedRun:
    run = PairedRun(CARD)

    for offset, (one, other) in enumerate(pairs):
        run.add("with", first_seed + offset, one)
        run.add("without", first_seed + offset, other)

    return run


def read(run: PairedRun) -> Comparison:
    return compare_paired("A card (a-card)", run, card=CARD, rng_model="2")


def measure(comparison: Comparison, name: str) -> Difference:
    return next(difference for difference in comparison.differences if difference.name == name)


def turns_of(comparison: Comparison) -> Difference:
    return measure(comparison, "turns a game")


def standard_error(values: list[float]) -> float:
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)

    return math.sqrt(variance) / math.sqrt(len(values))


# ----------------------------------------------------------------------
# Means
# ----------------------------------------------------------------------


def test_identical_pairs_changed_nothing() -> None:
    told = read(kept([(game(40 + seed), game(40 + seed)) for seed in range(20)]))

    turns = turns_of(told)

    assert turns.change == 0
    assert turns.error is None
    assert turns.differing == 0
    assert turns.method == PAIRED_MEAN
    assert not turns.tells_us_anything

    assert told.design == PAIRED
    assert told.games == 20
    assert told.unchanged
    assert told.verdict == "taking the card out changed none of 20 games"
    assert told.told_us == ()


@pytest.mark.parametrize("step", [3, -3])
def test_a_constant_difference_is_exact(step: int) -> None:
    told = read(kept([(game(40 + seed + step), game(40 + seed)) for seed in range(12)]))

    turns = turns_of(told)

    assert turns.change == step
    assert turns.error is None, "every pair moved the same: the change is exact"
    assert turns.differing == 12
    assert not turns.tells_us_anything
    assert f"{step:+.2f}" in read_out(told)


def test_one_pair_has_no_error() -> None:
    told = read(kept([(game(45), game(40))]))

    turns = turns_of(told)

    assert turns.change == 5
    assert turns.error is None
    assert turns.differing == 1


def test_the_error_is_the_spread_of_the_differences() -> None:
    moved = [1, 4, -2, 7, 3, 0, 5, 2, 6, -1, 3, 4]
    told = read(kept([(game(60 + d + n * 9), game(60 + n * 9)) for n, d in enumerate(moved)]))

    turns = turns_of(told)

    assert turns.change == pytest.approx(sum(moved) / len(moved))
    assert turns.error == pytest.approx(standard_error([float(d) for d in moved]))
    assert turns.differing == sum(1 for d in moved if d)


def test_fewer_than_min_differing_pairs_are_never_marked() -> None:
    moved = [10, 11, 12, 10, 11]
    pairs = [(game(60 + d + seed * 7), game(60 + seed * 7)) for seed, d in enumerate(moved)]
    pairs += [(game(30 + seed), game(30 + seed)) for seed in range(15)]

    turns = turns_of(read(kept(pairs)))

    assert turns.differing == 5 < MIN_DIFFERING
    assert turns.error is not None
    assert abs(turns.change or 0) >= 2 * turns.error, "twice the error alone would mark it"
    assert not turns.tells_us_anything


def test_min_differing_pairs_can_be_marked() -> None:
    moved = [10, 11, 12, 10, 11, 9, 12, 10, 11, 13]
    told = read(kept([(game(60 + d + n * 7), game(60 + n * 7)) for n, d in enumerate(moved)]))

    turns = turns_of(told)

    assert turns.differing == MIN_DIFFERING
    assert turns.tells_us_anything
    assert told.can_be_about_the_card
    assert told.told_us == (turns,)
    assert told.verdict.startswith("an effect, in 1 of 5 measures: turns a game +10.90")


def test_a_paired_error_is_narrower_than_two_populations_would_say() -> None:
    picked = random.Random(4)
    lengths = [picked.randint(40, 250) for _ in range(40)]
    moved = [picked.choice([1, 2, 3]) for _ in lengths]

    pairs = [(game(length + d), game(length)) for length, d in zip(lengths, moved, strict=True)]

    paired = turns_of(read(kept(pairs)))

    with_it, without_it = Tally(), Tally()

    for one, other in pairs:
        with_it.merge(one)
        without_it.merge(other)

    independent = turns_of(compare("A card", with_it, without_it, appeared=40, rng_model="2"))

    assert paired.change == pytest.approx(independent.change or 0)
    assert paired.error is not None and independent.error is not None
    assert paired.error < independent.error / 10
    assert paired.tells_us_anything
    assert not independent.tells_us_anything


def test_deaths_and_commands_are_paired_too() -> None:
    told = read(
        kept(
            [
                (game(commands=100 + seed, deaths=seed % 3), game(commands=100, deaths=0))
                for seed in range(12)
            ]
        )
    )

    commands = measure(told, "commands a game")
    deaths = measure(told, "deaths a game")

    assert commands.method == deaths.method == PAIRED_MEAN
    assert commands.change == pytest.approx(5.5)
    assert commands.differing == 11
    assert deaths.differing == 8


# ----------------------------------------------------------------------
# A share of games: exact McNemar
# ----------------------------------------------------------------------


def finished_pairs(only_with: int, only_without: int, both: int = 0, neither: int = 0) -> PairedRun:
    pairs = [(game(finished=True), game(finished=False))] * only_with
    pairs += [(game(finished=False), game(finished=True))] * only_without
    pairs += [(game(finished=True), game(finished=True))] * both
    pairs += [(game(finished=False), game(finished=False))] * neither

    return kept(pairs)


def finished_of(comparison: Comparison) -> Difference:
    return measure(comparison, "games that finished")


def test_no_discordant_pair_is_nothing_to_test() -> None:
    share = finished_of(read(finished_pairs(0, 0, both=30, neither=5)))

    assert share.method == MCNEMAR_EXACT
    assert share.change == 0
    assert share.error is None
    assert share.p is None
    assert share.discordant == (0, 0)
    assert share.differing == 0
    assert not share.tells_us_anything


def test_four_to_nothing_is_not_marked_although_wald_would() -> None:
    share = finished_of(read(finished_pairs(4, 0, both=96)))

    assert share.discordant == (4, 0)
    assert share.p == pytest.approx(0.125)
    assert share.error is not None
    assert abs(share.change or 0) >= 2 * share.error, "the plain interval would mark it"
    assert not share.tells_us_anything


def test_ten_to_nothing_is_marked() -> None:
    told = read(finished_pairs(10, 0, both=90))
    share = finished_of(told)

    assert share.p == pytest.approx(0.001953125)
    assert share.p is not None and share.p <= MCNEMAR_LINE
    assert share.tells_us_anything
    assert told.can_be_about_the_card
    assert share in told.told_us
    assert "10 only with it, 0 only without it; exact McNemar p = 0.0020" in read_out(told)


def test_mixed_discordant_pairs() -> None:
    share = finished_of(read(finished_pairs(7, 2, both=40, neither=1)))

    assert share.discordant == (7, 2)
    assert share.change == pytest.approx(5 / 50)
    assert share.p == pytest.approx(2 * (1 + 9 + 36) / 512)
    assert not share.tells_us_anything


def test_concordant_pairs_do_not_move_the_test() -> None:
    few = finished_of(read(finished_pairs(9, 1)))
    many = finished_of(read(finished_pairs(9, 1, both=200, neither=50)))

    assert few.p == many.p == pytest.approx(2 * (1 + 10) / 1024)
    assert few.differing == many.differing == 10


def test_the_exact_test_by_hand() -> None:
    assert mcnemar(0, 0) is None
    assert mcnemar(3, 3) == 1.0
    assert mcnemar(1, 0) == 1.0
    assert mcnemar(0, 6) == pytest.approx(2 / 64)
    assert mcnemar(5000, 5000) == 1.0
    assert mcnemar(0, 2000) == 0.0


def test_an_empty_share_is_none() -> None:
    share = paired_share("games that finished", ())

    assert share.with_it is None and share.without_it is None
    assert share.discordant == (0, 0)
    assert share.p is None


# ----------------------------------------------------------------------
# Attack rolls, clustered by game
# ----------------------------------------------------------------------


def test_the_hit_ratio_is_clustered_by_game() -> None:
    pairs = [
        (Played(seed=0, hits=3, rolls=6), Played(seed=0, hits=2, rolls=5)),
        (Played(seed=1, hits=8, rolls=10), Played(seed=1, hits=4, rolls=9)),
        (Played(seed=2, hits=1, rolls=4), Played(seed=2, hits=1, rolls=4)),
    ]

    ratio = paired_ratio("attacks that hit", pairs)

    here, there = 12 / 20, 7 / 18
    per_pair, other_per_pair = 20 / 3, 18 / 3

    linear = [
        (3 - here * 6) / per_pair - (2 - there * 5) / other_per_pair,
        (8 - here * 10) / per_pair - (4 - there * 9) / other_per_pair,
        (1 - here * 4) / per_pair - (1 - there * 4) / other_per_pair,
    ]

    assert ratio.method == PAIRED_RATIO
    assert ratio.with_it == pytest.approx(here)
    assert ratio.without_it == pytest.approx(there)
    assert ratio.error == pytest.approx(standard_error(linear))
    assert ratio.differing == 2


def test_no_rolls_on_a_side_is_none() -> None:
    pairs = [
        (Played(seed=0, hits=0, rolls=0), Played(seed=0, hits=1, rolls=2)),
        (Played(seed=1, hits=0, rolls=0), Played(seed=1, hits=0, rolls=0)),
    ]

    ratio = paired_ratio("attacks that hit", pairs)

    assert ratio.change is None
    assert ratio.error is None
    assert ratio.differing == 1
    assert not ratio.tells_us_anything


def test_a_hit_ratio_needs_min_differing_pairs() -> None:
    pairs = [(game(hits=9, rolls=10), game(hits=1, rolls=10))] * 6
    pairs += [(game(hits=5, rolls=10), game(hits=5, rolls=10))] * 30

    hits = measure(read(kept(pairs)), "attacks that hit")

    assert hits.differing == 6
    assert not hits.tells_us_anything


# ----------------------------------------------------------------------
# Which games make a pair
# ----------------------------------------------------------------------


def test_a_seed_on_one_side_only_is_refused() -> None:
    run = PairedRun(CARD)

    run.add("with", 0, game())
    run.add("without", 0, game())
    run.add("without", 1, game())

    with pytest.raises(RuntimeError, match="only with the card none, only without it 1"):
        read(run)


def test_seed_sets_that_differ_both_ways_are_refused() -> None:
    run = PairedRun(CARD)

    for seed in (0, 1, 2):
        run.add("with", seed, game())

    for seed in (1, 2, 3, 4):
        run.add("without", seed, game())

    with pytest.raises(RuntimeError, match="only with the card 0, only without it 3, 4"):
        read(run)


def test_a_seed_twice_on_one_side_is_refused() -> None:
    run = PairedRun(CARD)
    run.add("with", 3, game())

    with pytest.raises(RuntimeError, match="seed 3 came back twice in the run with the card"):
        run.add("with", 3, game())


def test_there_are_two_sides_and_no_third() -> None:
    with pytest.raises(ValueError):
        PairedRun(CARD).add("beside", 0, game())


def test_the_order_games_come_back_in_does_not_matter() -> None:
    picked = random.Random(11)
    pairs = [
        (game(picked.randint(30, 90), played=picked.random() < 0.3), game(picked.randint(30, 90)))
        for _ in range(25)
    ]

    in_order = read(kept(pairs))

    arrivals = [("with", seed, one) for seed, (one, _) in enumerate(pairs)]
    arrivals += [("without", seed, other) for seed, (_, other) in enumerate(pairs)]
    picked.shuffle(arrivals)

    shuffled = PairedRun(CARD)

    for side, seed, tally in arrivals:
        shuffled.add(side, seed, tally)

    assert read(shuffled).to_dict() == in_order.to_dict()


@pytest.mark.parametrize("side", ["with", "without", "both"])
def test_a_game_that_fell_over_takes_its_pair_out(side: str) -> None:
    pairs = [(game(50 + seed * 3 + 2), game(50 + seed * 3)) for seed in range(6)]
    run = PairedRun(CARD)

    for seed, (one, other) in enumerate(pairs):
        broke_with = "RecursionError: deep" if seed == 2 and side in ("with", "both") else ""
        broke_without = "ValueError: odd" if seed == 2 and side in ("without", "both") else ""

        run.add("with", seed, Tally() if broke_with else one, broke_with)
        run.add("without", seed, Tally() if broke_without else other, broke_without)

    told = read(run)

    reasons = {"with": "with it: RecursionError: deep", "without": "without it: ValueError: odd"}
    expected = "; ".join(reasons[name] for name in ("with", "without") if side in (name, "both"))

    assert told.excluded == ((2, expected),)
    assert told.games == 5
    assert (told.errors_with, told.errors_without) == (
        int(side in ("with", "both")),
        int(side in ("without", "both")),
    )

    kept_whole = read(kept([pair for seed, pair in enumerate(pairs) if seed != 2]))

    assert [difference.to_dict() for difference in told.differences] == [
        difference.to_dict() for difference in kept_whole.differences
    ], "no half of the fallen pair reached a number"

    said = read_out(told)

    assert "seed 2: " + expected in said
    assert told.to_dict()["excluded"] == [{"seed": 2, "reason": expected}]


def test_a_game_that_ran_out_of_steps_is_still_a_game() -> None:
    pairs = [(game(80, finished=False), game(60, finished=True))]
    pairs += [(game(40 + seed), game(40 + seed)) for seed in range(9)]

    told = read(kept(pairs))

    assert told.games == 10
    assert told.excluded == ()
    assert turns_of(told).differing == 1
    assert finished_of(told).discordant == (0, 1)


def test_a_paired_reading_is_only_made_on_model_two() -> None:
    run = kept([(game(), game())])

    with pytest.raises(ValueError, match="only on RNG model 2"):
        compare_paired("A card", run, card=CARD, rng_model="1")


def test_a_run_kept_for_one_card_is_not_read_for_another() -> None:
    with pytest.raises(ValueError, match="kept for 'a-card', not 'another'"):
        compare_paired("A card", kept([(game(), game())]), card="another", rng_model="2")


def test_appeared_counts_games_the_card_was_played_in_and_decides_nothing() -> None:
    pairs = [(game(50, played=seed < 3), game(50)) for seed in range(20)]

    told = read(kept(pairs))

    assert told.appeared == 3
    assert told.unchanged, "played in three games, and changed none of them"
    assert told.verdict == "taking the card out changed none of 20 games"


def kept_with_falls(sides: list[tuple[str, str]]) -> tuple[Comparison, Tally]:
    """
    A run built seed by seed from what each side did, and the merged tally of
    the run with the card.

    The side with the card is ``played``, ``unplayed`` or ``broke``; the side
    without it is ``ok`` or ``broke``. A game that fell over comes back with an
    empty tally, the way the pool sends it.
    """
    run = PairedRun(CARD)
    with_run = Tally()

    for seed, (with_side, without_side) in enumerate(sides):
        if with_side == "broke":
            one, broke = Tally(), "RuntimeError: with"
        else:
            one, broke = game(50 + seed, played=with_side == "played"), ""

        with_run.merge(one)
        run.add("with", seed, one, broke)

        if without_side == "broke":
            run.add("without", seed, Tally(), "RuntimeError: without")
        else:
            run.add("without", seed, game(50 + seed))

    return read(run), with_run


def card_games(tally: Tally) -> int:
    seen = tally.cards.get(CARD)

    return seen.games if seen is not None else 0


def test_appeared_counts_the_card_played_in_pairs_that_are_read() -> None:
    told, with_run = kept_with_falls([("played", "ok"), ("played", "ok"), ("unplayed", "ok")])

    assert told.appeared == card_games(with_run) == 2
    assert told.games == 3
    assert told.excluded == ()


def test_appeared_is_nothing_when_the_card_was_never_played() -> None:
    told, with_run = kept_with_falls([("unplayed", "ok")] * 4)

    assert told.appeared == card_games(with_run) == 0
    assert told.games == 4


def test_a_game_with_the_card_that_fell_over_adds_nothing_to_appeared() -> None:
    told, with_run = kept_with_falls([("broke", "ok"), ("played", "ok")])

    assert told.appeared == card_games(with_run) == 1
    assert told.games == 1
    assert [seed for seed, _ in told.excluded] == [0]
    assert (told.errors_with, told.errors_without) == (1, 0)


def test_the_card_played_in_a_game_whose_pair_fell_over_still_appeared() -> None:
    told, with_run = kept_with_falls([("played", "broke"), ("unplayed", "ok")])

    assert told.appeared == card_games(with_run) == 1
    assert told.games == 1
    assert told.excluded == ((0, "without it: RuntimeError: without"),)
    assert (told.errors_with, told.errors_without) == (0, 1)
    assert "it was played in 1 games with it" in read_out(told)


def test_an_unplayed_card_in_a_game_whose_pair_fell_over_adds_nothing() -> None:
    told, with_run = kept_with_falls([("unplayed", "broke"), ("played", "ok")])

    assert told.appeared == card_games(with_run) == 1
    assert told.games == 1
    assert [seed for seed, _ in told.excluded] == [0]
    assert (told.errors_with, told.errors_without) == (0, 1)


def test_a_pair_that_fell_over_on_both_sides_adds_nothing_to_appeared() -> None:
    told, with_run = kept_with_falls([("broke", "broke"), ("played", "ok")])

    assert told.appeared == card_games(with_run) == 1
    assert told.games == 1
    assert told.excluded == (
        (0, "with it: RuntimeError: with; without it: RuntimeError: without"),
    )
    assert (told.errors_with, told.errors_without) == (1, 1)


def test_appeared_can_be_more_than_the_pairs_read() -> None:
    told, with_run = kept_with_falls(
        [
            ("played", "broke"),
            ("played", "broke"),
            ("unplayed", "broke"),
            ("broke", "ok"),
            ("broke", "broke"),
            ("played", "ok"),
            ("unplayed", "ok"),
        ]
    )

    assert told.appeared == card_games(with_run) == 3
    assert told.games == 2
    assert told.appeared > told.games
    assert [seed for seed, _ in told.excluded] == [0, 1, 2, 3, 4]
    assert (told.errors_with, told.errors_without) == (2, 4)
    assert told.to_dict()["appeared"] == 3
    assert "it was played in 3 games with it" in read_out(told)

    read_whole = read(kept([(game(55, played=True), game(55)), (game(56), game(56))]))

    assert [difference.to_dict() for difference in told.differences] == [
        difference.to_dict() for difference in read_whole.differences
    ], "appeared counts the whole run; the numbers still read only the pairs"


def test_too_few_changed_games_are_too_few_to_say() -> None:
    pairs = [(game(50 + seed), game(50)) for seed in range(1, 5)]
    pairs += [(game(50), game(50))] * 26

    told = read(kept(pairs))

    assert not told.can_be_about_the_card
    assert told.verdict == (
        "too few games changed to say: at most 4 of 30 differed in any one measure"
    )
    assert "*" not in read_out(told).split("-" * 78)[2]


def test_nothing_played_is_nothing_to_say() -> None:
    told = read(PairedRun(CARD))

    assert told.games == 0
    assert told.verdict == "nothing was played"


# ----------------------------------------------------------------------
# What a comparison says it is
# ----------------------------------------------------------------------


def test_a_paired_comparison_says_how_every_number_was_made() -> None:
    told = read(kept([(game(50 + seed), game(50)) for seed in range(12)]))
    written = told.to_dict()

    assert OLD_KEYS <= set(written)
    assert written["design"] == "paired"
    assert written["rng_model"] == "2"
    assert written["excluded"] == []

    methods = [difference["method"] for difference in written["differences"]]

    assert methods == [PAIRED_MEAN, PAIRED_MEAN, PAIRED_MEAN, PAIRED_RATIO, MCNEMAR_EXACT]

    for difference in written["differences"]:
        assert OLD_DIFFERENCE_KEYS | {"method", "differing", "discordant", "p"} == set(difference)

    assert written["differences"][-1]["discordant"] == [0, 0]


def test_an_independent_comparison_keeps_what_it_said_and_names_its_design() -> None:
    with_it, without_it = Tally(), Tally()

    for seed in range(20):
        with_it.merge(game(40 + seed, played=seed < 5))
        without_it.merge(game(42 + seed))

    told = compare("A card", with_it, without_it, appeared=5, rng_model="1")
    written = told.to_dict()

    assert told.design == INDEPENDENT
    assert told.excluded == ()
    assert written["design"] == "independent"
    assert written["excluded"] == []

    for difference in told.differences:
        assert difference.method == INDEPENDENT
        assert difference.differing is None
        assert difference.discordant is None
        assert difference.p is None

    turns = turns_of(told)

    assert turns.change == pytest.approx(-2)
    assert turns.error == pytest.approx(math.sqrt(2 * 35 / 20))
    assert "differed" not in read_out(told)
    assert "McNemar" not in read_out(told)


def test_a_difference_made_the_old_way_reads_the_old_way() -> None:
    plain = Difference("turns a game", 12.0, 10.0, 0.5)

    assert plain.method == INDEPENDENT
    assert plain.tells_us_anything
    assert plain.to_dict()["beyond_noise"] is True
    assert plain.to_dict()["differing"] is None
