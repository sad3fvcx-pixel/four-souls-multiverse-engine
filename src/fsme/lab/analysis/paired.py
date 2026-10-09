# src/fsme/lab/analysis/paired.py

"""
A card test read as pairs.

On RNG model 2 the same seed deals the same game with the card in the content
and without it, and the two stay one game until the card does something. So
every seed of a card test is a pair: the game with the card, and the same game
without it. What the card did to a measure is then the difference inside each
pair, d = with − without, averaged — and its uncertainty is the spread of those
differences, not of the two runs as if they were strangers. The part of a
game's length that the seed decides cancels inside the pair instead of being
counted as noise twice.

Three rules keep it a paired comparison and nothing else.

A pair is matched by its seed, never by where it came in the run: games come
back from the workers in whatever order they finish.

Both runs play the same seeds or the comparison is refused. A seed on one side
only, or twice on one side, is a run that went wrong, and quietly keeping the
seeds both sides have would turn the test back into two populations without
saying so.

A game that fell over takes its pair out with it, and the pair is named.
Keeping the half that finished would compare it with nothing; counting it
anyway would be the same quiet slide back. A game that ran out of steps did not
fall over: it is a game, and it is read like one.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from fsme.rng.rng import KEYED_MODEL

from .compare import (
    MCNEMAR_EXACT,
    PAIRED,
    PAIRED_MEAN,
    PAIRED_RATIO,
    Comparison,
    Difference,
)
from .tally import Tally

WITH = "with"
WITHOUT = "without"
SIDES = (WITH, WITHOUT)


@dataclass(frozen=True, slots=True)
class Played:
    """
    One game of one run, reduced to what a paired comparison reads of it.
    """

    seed: int

    turns: int = 0
    commands: int = 0
    deaths: int = 0

    hits: int = 0
    rolls: int = 0

    finished: bool = False

    appeared: bool = False
    """Whether the card under test was played, activated or bought."""

    broke: str = ""
    """Why the game fell over, when it did. A game that fell over measures nothing."""


@dataclass(slots=True)
class PairedRun:
    """
    Both runs of a card test, kept seed by seed.

    Fed one game at a time, in any order, from either run; kept small — a
    handful of numbers a game, never the game's tally.
    """

    card: str
    """The card under test, which is how a game says whether it was played."""

    _played: dict[str, dict[int, Played]] = field(
        default_factory=lambda: {side: {} for side in SIDES}
    )

    def add(self, side: str, seed: int, tally: Tally, broke: str = "") -> None:
        """
        Keep one game of the run ``side`` (``"with"`` or ``"without"``).

        ``tally`` is that one game's tally. A seed already kept on this side is
        refused: two games for one seed is not a pair.
        """
        if side not in SIDES:
            raise ValueError(f"a card test has a run with the card and one without, not {side!r}")

        kept = self._played[side]

        if seed in kept:
            raise RuntimeError(f"seed {seed} came back twice in the run {side} the card")

        if broke:
            kept[seed] = Played(seed=seed, broke=broke)
            return

        seen = tally.cards.get(self.card)

        kept[seed] = Played(
            seed=seed,
            turns=tally.turns,
            commands=tally.commands,
            deaths=tally.deaths,
            hits=tally.attack_hits,
            rolls=tally.attack_rolls,
            finished=tally.finished > 0,
            appeared=bool(seen is not None and seen.games),
        )

    def games(self, side: str) -> int:
        return len(self._played[side])

    def broken(self, side: str) -> int:
        """How many games of the run ``side`` fell over."""
        return sum(1 for played in self._played[side].values() if played.broke)

    def appeared(self) -> int:
        """
        How many games of the run with the card had it played, activated or
        bought — every game of that run that did not fall over, whether or not
        its pair is read.

        The same number the run's tally gives, ``tally.cards[card].games``: it
        describes the run with the card, not the pairs, so a pair left out
        because the game without the card fell over still counts here.
        """
        return sum(
            1 for played in self._played[WITH].values() if not played.broke and played.appeared
        )

    def pairs(self) -> tuple[tuple[tuple[Played, Played], ...], tuple[tuple[int, str], ...]]:
        """
        The pairs to read, by seed, and the pairs left out with why.

        Refused when the two runs did not play the same seeds.
        """
        with_it, without_it = self._played[WITH], self._played[WITHOUT]

        only_with = sorted(set(with_it) - set(without_it))
        only_without = sorted(set(without_it) - set(with_it))

        if only_with or only_without:
            raise RuntimeError(
                "the two runs of the card test did not play the same seeds:"
                f" only with the card {_seeds(only_with)},"
                f" only without it {_seeds(only_without)}"
            )

        read: list[tuple[Played, Played]] = []
        excluded: list[tuple[int, str]] = []

        for seed in sorted(with_it):
            one, other = with_it[seed], without_it[seed]

            if one.broke or other.broke:
                excluded.append(
                    (
                        seed,
                        "; ".join(
                            f"{side} it: {played.broke}"
                            for side, played in ((WITH, one), (WITHOUT, other))
                            if played.broke
                        ),
                    )
                )
                continue

            read.append((one, other))

        return tuple(read), tuple(excluded)


def compare_paired(
    subject: str,
    run: PairedRun,
    *,
    card: str,
    rng_model: str,
) -> Comparison:
    """
    Read a card test as pairs: each game against its own game without the card.

    Only on model 2, where the same seed is the same game with the card and
    without it. On model 1 taking a card out deals every game again, there is
    no pair to read, and ``compare`` is the comparison to make.
    """
    if rng_model != KEYED_MODEL:
        raise ValueError(
            f"a paired comparison is made only on RNG model {KEYED_MODEL}, where the"
            f" same seed is the same game; this run was played on model {rng_model}"
        )

    if card != run.card:
        raise ValueError(f"this run was kept for {run.card!r}, not {card!r}")

    pairs, excluded = run.pairs()

    return Comparison(
        subject=subject,
        games=len(pairs),
        appeared=run.appeared(),
        errors_with=run.broken(WITH),
        errors_without=run.broken(WITHOUT),
        rng_model=rng_model,
        design=PAIRED,
        excluded=excluded,
        differences=(
            paired_mean("turns a game", pairs, lambda played: played.turns),
            paired_mean("commands a game", pairs, lambda played: played.commands),
            paired_mean("deaths a game", pairs, lambda played: played.deaths),
            paired_ratio("attacks that hit", pairs),
            paired_share("games that finished", pairs),
        ),
    )


def paired_mean(
    name: str,
    pairs: Sequence[tuple[Played, Played]],
    reading: Callable[[Played], int],
) -> Difference:
    """
    The mean of d = with − without over the pairs, with sd(d) / √n as its error.

    The error is None for fewer than two pairs, and when every pair moved by
    the same amount — the change is then exact rather than uncertain.
    """
    if not pairs:
        return Difference(name, None, None, method=PAIRED_MEAN, differing=0)

    here = [reading(one) for one, _ in pairs]
    there = [reading(other) for _, other in pairs]
    moved = [one - other for one, other in zip(here, there, strict=True)]

    return Difference(
        name,
        sum(here) / len(here),
        sum(there) / len(there),
        _error(moved),
        method=PAIRED_MEAN,
        differing=sum(1 for d in moved if d),
    )


def paired_ratio(name: str, pairs: Sequence[tuple[Played, Played]]) -> Difference:
    """
    Hits over rolls on both sides, with an error clustered by seed.

    An attack roll is not a game: the rolls of one game are not independent of
    each other, so the pair is the unit, and the difference of the two ratios
    is linearised by the delta method into one number per pair,

        u = (h_w − p_w·r_w) / r̄_w − (h_o − p_o·r_o) / r̄_o,

    whose spread over √n is the error. ``p`` is each side's ratio over every
    pair, ``r̄`` its rolls per pair. A pair differs when its hits or its rolls
    do. None on either side that rolled nothing.
    """
    differing = sum(1 for one, other in pairs if (one.hits, one.rolls) != (other.hits, other.rolls))

    rolls = sum(one.rolls for one, _ in pairs)
    other_rolls = sum(other.rolls for _, other in pairs)

    if not rolls or not other_rolls:
        return Difference(name, None, None, method=PAIRED_RATIO, differing=differing)

    here = sum(one.hits for one, _ in pairs) / rolls
    there = sum(other.hits for _, other in pairs) / other_rolls

    per_pair = rolls / len(pairs)
    other_per_pair = other_rolls / len(pairs)

    linear = [
        (one.hits - here * one.rolls) / per_pair
        - (other.hits - there * other.rolls) / other_per_pair
        for one, other in pairs
    ]

    return Difference(
        name,
        here,
        there,
        _error(linear),
        method=PAIRED_RATIO,
        differing=differing,
    )


def paired_share(name: str, pairs: Sequence[tuple[Played, Played]]) -> Difference:
    """
    The share of games that finished, read pair by pair.

    A pair where both games finished, or neither did, says nothing about the
    card; the discordant pairs say everything — ``b`` where only the game with
    the card finished, ``c`` where only the one without it did. The change is
    (b − c) / n with sd(d) / √n beside it, and whether it is marked is the exact
    two-sided McNemar test, not the error: discordant pairs in a card test are
    few, and an interval drawn from a handful of them marks what it should not.
    """
    if not pairs:
        return Difference(
            name, None, None, method=MCNEMAR_EXACT, differing=0, discordant=(0, 0)
        )

    only_with = sum(1 for one, other in pairs if one.finished and not other.finished)
    only_without = sum(1 for one, other in pairs if other.finished and not one.finished)

    moved = [int(one.finished) - int(other.finished) for one, other in pairs]

    return Difference(
        name,
        sum(1 for one, _ in pairs if one.finished) / len(pairs),
        sum(1 for _, other in pairs if other.finished) / len(pairs),
        _error(moved) if only_with + only_without else None,
        method=MCNEMAR_EXACT,
        differing=only_with + only_without,
        discordant=(only_with, only_without),
        p=mcnemar(only_with, only_without),
    )


def mcnemar(only_with: int, only_without: int) -> float | None:
    """
    The exact two-sided McNemar p for ``only_with`` against ``only_without``.

    Under no effect each discordant pair is a fair coin, so the p is twice the
    smaller binomial tail of b + c tosses, capped at one. None when no pair
    disagreed: there is nothing to test.
    """
    tosses = only_with + only_without

    if not tosses:
        return None

    tail = sum(math.comb(tosses, k) for k in range(min(only_with, only_without) + 1))

    return min(1.0, 2 * tail / (1 << tosses))


def _error(values: Sequence[float]) -> float | None:
    """
    sd / √n, with the n − 1 sample deviation; None below two values or at none.
    """
    count = len(values)

    if count < 2:
        return None

    mean = sum(values) / count
    variance = sum((value - mean) ** 2 for value in values) / (count - 1)

    if variance <= 0:
        return None

    return math.sqrt(variance) / math.sqrt(count)


def _seeds(seeds: Sequence[int]) -> str:
    if not seeds:
        return "none"

    shown = ", ".join(str(seed) for seed in seeds[:10])

    return shown if len(seeds) <= 10 else f"{shown} and {len(seeds) - 10} more"
