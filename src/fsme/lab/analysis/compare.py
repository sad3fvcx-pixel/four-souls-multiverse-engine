# src/fsme/lab/analysis/compare.py

"""
Two runs, side by side.

This is the tool the card tables could not be: a difference between the game
with a card in it and the game without, rather than a correlation inside one
run. Take the card out of the content, play the same number of games, and
compare what came out.

Two honesties are built in, because without them the numbers would be worse
than nothing.

A difference is reported with the noise it sits in. Fifty games of a random
table will show a several-turn difference in average length between two
identical rulesets, so a difference smaller than its own uncertainty is
reported as "nothing you could tell from this many games" rather than as a
finding. The interval is the ordinary one for a difference of means — the
standard errors added in quadrature — and it assumes only that the games are
independent, which they are, being separately seeded.

And the games are not paired. Removing a card changes the deck, so the same
seed deals a different game: this compares two populations, not two versions of
one game. Every seed is played in both runs, which makes the two populations
alike in everything the seed controls and nothing more.

That last point has teeth, and it is the thing most likely to mislead. Taking
one card out of a deck of hundreds reshuffles every game that deck deals, so
two runs differ everywhere and not only where the card is. When a card reached
the table in a handful of games, a difference in the averages is the deck
moving, not the card working — and the reading says so rather than leaving the
reader to notice.

All of that is about RNG model 1, which a run is played on only when it asks for
it by name. A card test asks for model 2 (``PAIRED_RNG_MODEL``), where each deck is
shuffled by a key per card: taking a card out moves no other card, and a game
the card never reached plays out the same with it and without it. The
populations are then paired by seed as well as alike. ``compare`` still works
its numbers out as if they were not — the interval is the same one, which only
makes it wider than it needs to be — and only the sentences that would be false
on model 2 are said differently. ``compare_paired`` (in ``paired.py``) is the
one that reads a model 2 card test as pairs, and a comparison says which of the
two it is in ``design``.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from fsme.rng.rng import LEGACY_MODEL

from .tally import Tally

ENOUGH = 0.1
"""
How often a card must reach the table before a difference can be about it.

One in ten is not a statistical threshold and is not pretending to be one. It
is the point below which the two runs plainly differ by more than the card —
every shuffle having moved — and the reading stops offering its numbers as if
they were about the card.

A paired comparison does not use it: on model 2 a game the card never changed
is the same game twice, so there is no deck moving for a share of games to
guard against. What a pair needs instead is ``MIN_DIFFERING``.
"""

MIN_DIFFERING = 10
"""
How many pairs a measure has to differ in before a paired difference in it can
be marked.

A rule of thumb for when the normal approximation behind "twice its standard
error" starts to hold — the same ten usually asked of the discordant pairs of
McNemar's test — and not a test of significance. Below it, a difference resting
on a handful of games that moved is not offered as a finding, however its
interval came out.
"""

MCNEMAR_LINE = 0.0455
"""
The two-sided p at or below which the exact McNemar test marks a paired share.

The chance of landing two standard errors from zero, so that a share is marked
at the same line every other measure is.
"""

INDEPENDENT = "independent"
PAIRED = "paired"

PAIRED_MEAN = "paired-mean"
PAIRED_RATIO = "paired-ratio"
MCNEMAR_EXACT = "mcnemar-exact"


@dataclass(frozen=True, slots=True)
class Difference:
    """
    One measurement, in both runs, with a sense of how sure it is.
    """

    name: str

    with_it: float | None
    without_it: float | None

    error: float | None = None
    """
    The uncertainty of the difference, as one standard error.

    None when it cannot be worked out, which is not the same as zero and is
    printed differently. In a paired comparison it is also None when every
    pair moved by exactly the same amount: the change is then exact.
    """

    method: str = INDEPENDENT
    """
    How the uncertainty was worked out: ``independent`` for two populations,
    ``paired-mean``, ``paired-ratio`` or ``mcnemar-exact`` for pairs.
    """

    differing: int | None = None
    """
    In a paired comparison, how many pairs this measure differed in.
    """

    discordant: tuple[int, int] | None = None
    """
    For a paired share: pairs where only the game with the card had it, and
    pairs where only the game without the card did.
    """

    p: float | None = None
    """
    For a paired share: the two-sided p of the exact McNemar test, or None
    when no pair disagreed.
    """

    @property
    def change(self) -> float | None:
        if self.with_it is None or self.without_it is None:
            return None

        return self.with_it - self.without_it

    @property
    def tells_us_anything(self) -> bool:
        """
        Whether the difference is bigger than the noise it sits in.

        Two standard errors, which is the usual line and is drawn here so that
        a reader is not invited to draw it wherever suits them. A paired
        measure has to have differed in ``MIN_DIFFERING`` pairs as well, and a
        paired share is marked by its exact test instead.
        """
        if self.method == MCNEMAR_EXACT:
            return self.p is not None and self.p <= MCNEMAR_LINE

        change = self.change

        if change is None or self.error is None or self.error <= 0:
            return False

        if self.method != INDEPENDENT and (self.differing or 0) < MIN_DIFFERING:
            return False

        return abs(change) >= 2 * self.error

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "with": self.with_it,
            "without": self.without_it,
            "change": self.change,
            "error": self.error,
            "beyond_noise": self.tells_us_anything,
            "method": self.method,
            "differing": self.differing,
            "discordant": None if self.discordant is None else list(self.discordant),
            "p": self.p,
        }


@dataclass(frozen=True, slots=True)
class Comparison:
    """
    What two runs of the same size had to say about each other.
    """

    subject: str

    games: int

    appeared: int = 0
    """
    Games in which the card actually turned up.

    Counted over the whole run with the card. In a paired comparison that
    includes games whose pair was left out because the game without the card
    fell over, so it can be more than ``games``, which counts only the pairs
    read.

    The number that decides whether the rest means anything: a card that never
    reached the table cannot have changed the game, and a comparison that shows
    a difference anyway is showing noise.
    """

    differences: tuple[Difference, ...] = ()

    errors_with: int = 0
    errors_without: int = 0

    rng_model: str = field(kw_only=True)
    """
    The generator both runs were played on, which decides what a difference
    between them can be: on model 1 the deck moving, on model 2 only the card.

    Required, and never taken from the default a new game is dealt on: the
    comparison says what the runs were played on, and only whoever ran them
    knows.
    """

    design: str = field(default=INDEPENDENT, kw_only=True)
    """
    ``independent`` when the runs were read as two populations, ``paired``
    when each game was read against its own game without the card.

    In a paired comparison ``games`` is the number of pairs read, and the
    averages on both sides are taken over those pairs.
    """

    excluded: tuple[tuple[int, str], ...] = field(default=(), kw_only=True)
    """
    The pairs left out of a paired comparison, by seed, with why: a game that
    fell over on either side takes its other half out with it.
    """

    @property
    def paired(self) -> bool:
        return self.design == PAIRED

    @property
    def unchanged(self) -> bool:
        """
        Whether a paired comparison found every pair the same in every measure.
        """
        return self.paired and all(not difference.differing for difference in self.differences)

    @property
    def most_differing(self) -> int:
        """
        The most pairs any one measure of a paired comparison differed in.
        """
        return max((difference.differing or 0 for difference in self.differences), default=0)

    @property
    def reshuffled(self) -> bool:
        """
        Whether taking the card out dealt every game differently.

        True on model 1, where it did. On model 2 it moved nothing else.
        """
        return self.rng_model == LEGACY_MODEL

    @property
    def can_be_about_the_card(self) -> bool:
        """
        Whether the card was in enough games for a difference to be its doing.

        In a paired comparison: whether some measure moved in enough pairs to
        be read — ``MIN_DIFFERING`` of them, or a share whose exact test says
        so. How often the card was played does not decide it, since a card can
        change a game without ever being played.
        """
        if self.paired:
            return any(
                difference.tells_us_anything
                if difference.method == MCNEMAR_EXACT
                else (difference.differing or 0) >= MIN_DIFFERING
                for difference in self.differences
            )

        return bool(self.games) and self.appeared >= self.games * ENOUGH

    @property
    def told_us(self) -> tuple[Difference, ...]:
        """
        The measurements that came out bigger than their own uncertainty.

        Empty when the card was too scarce for any of them to be about it: a
        difference the deck could have produced is not a difference the card
        did, and offering it as one would undo the point of the test.
        """
        if not self.can_be_about_the_card:
            return ()

        return tuple(
            difference
            for difference in self.differences
            if difference.tells_us_anything
        )

    @property
    def verdict(self) -> str:
        """
        The one line a card test exists to produce.

        Three answers and no fourth. The card changed something this many games
        could see; it did not, and here is what a difference would have had to
        be to show; or the run cannot say, because the card was hardly in it.
        Nothing here is stronger than the numbers above it — the wording is
        chosen so that "no effect found" cannot be read as "no effect".
        """
        if not self.games:
            return "nothing was played"

        if self.paired:
            if self.unchanged:
                return f"taking the card out changed none of {self.games} games"

            if not self.can_be_about_the_card:
                return (
                    f"too few games changed to say: at most {self.most_differing}"
                    f" of {self.games} differed in any one measure"
                )

        elif not self.appeared:
            return f"the card never reached the table in {self.games} games"

        if not self.can_be_about_the_card:
            if not self.reshuffled:
                return (
                    f"too scarce to say — it reached the table in {self.appeared}"
                    f" of {self.games} games, too few for a difference to be its"
                    f" doing"
                )

            return (
                f"too scarce to say — it reached the table in {self.appeared}"
                f" of {self.games} games, and the rest of the difference is the"
                f" deck"
            )

        told = self.told_us

        if not told:
            if self.paired:
                return (
                    f"no effect this run could see, over {self.games} games each"
                    f" played with the card and without it"
                )

            return (
                f"no effect this run could see, over {self.games} games in each"
            )

        named = ", ".join(
            f"{difference.name} {difference.change:+.2f}"
            for difference in told
            if difference.change is not None
        )

        return f"an effect, in {len(told)} of {len(self.differences)} measures: {named}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "games": self.games,
            "appeared": self.appeared,
            "can_be_about_the_card": self.can_be_about_the_card,
            "verdict": self.verdict,
            "differences": [difference.to_dict() for difference in self.differences],
            "errors_with": self.errors_with,
            "errors_without": self.errors_without,
            "rng_model": self.rng_model,
            "design": self.design,
            "excluded": [{"seed": seed, "reason": reason} for seed, reason in self.excluded],
        }


def compare(
    subject: str,
    with_it: Tally,
    without_it: Tally,
    *,
    appeared: int = 0,
    errors_with: int = 0,
    errors_without: int = 0,
    rng_model: str,
) -> Comparison:
    """
    Measure the same handful of things in both runs.

    The measurements are properties of a game rather than of a player: how long
    it ran, how often somebody died, how often an attack landed. A card's
    effect on *whose* game it is cannot be read from a run where only one table
    in three even drew it, so it is not offered.

    ``rng_model`` is the generator both runs were played on, and has no
    default: only whoever played the runs knows it. It changes what the reading
    may say about the deck, and nothing that is measured.
    """
    return Comparison(
        subject=subject,
        games=min(with_it.games, without_it.games),
        appeared=appeared,
        errors_with=errors_with,
        errors_without=errors_without,
        rng_model=rng_model,
        differences=(
            _mean(
                "turns a game",
                with_it,
                without_it,
                lambda tally: (tally.turns, tally.turns_squared),
            ),
            _mean(
                "commands a game",
                with_it,
                without_it,
                lambda tally: (tally.commands, tally.commands_squared),
            ),
            _mean(
                "deaths a game",
                with_it,
                without_it,
                lambda tally: (tally.deaths, tally.deaths_squared),
            ),
            _share(
                "attacks that hit",
                with_it.attack_hits,
                with_it.attack_rolls,
                without_it.attack_hits,
                without_it.attack_rolls,
            ),
            _share(
                "games that finished",
                with_it.finished,
                with_it.games,
                without_it.finished,
                without_it.games,
            ),
        ),
    )


def _mean(
    name: str,
    with_it: Tally,
    without_it: Tally,
    reading: Callable[[Tally], tuple[int, int]],
) -> Difference:
    """
    Compare two averages of counts per game, with the spread they actually had.

    The spread is measured rather than assumed, and the difference between
    those two is the difference between a report that can be believed and one
    that cannot. The earlier version took a count's variance to equal its mean,
    as a Poisson count's does. Games do not oblige: they run from forty turns
    to two hundred and fifty around an average near a hundred and twenty, so
    the real spread is several times what that assumption gives, the intervals
    came out several times too narrow, and a forty-game run duly announced an
    effect that a two-hundred-game run reversed.

    Now the interval comes from the games that were played. It gets wider,
    which is the point: an honest interval that says nothing beats a narrow one
    that says the wrong thing.
    """
    total, squared = reading(with_it)
    other_total, other_squared = reading(without_it)

    games = with_it.games
    other_games = without_it.games

    here = total / games if games else None
    there = other_total / other_games if other_games else None

    if here is None or there is None:
        return Difference(name, here, there)

    spread = with_it.spread_of(total, squared)
    other_spread = without_it.spread_of(other_total, other_squared)

    if spread is None or other_spread is None:
        return Difference(name, here, there)

    # The standard error of a difference of two independent means.
    error = math.sqrt(spread**2 / games + other_spread**2 / other_games)

    return Difference(name, here, there, error or None)


def _share(
    name: str, part: int, whole: int, other_part: int, other_whole: int
) -> Difference:
    """
    Compare two proportions.
    """
    here = part / whole if whole else None
    there = other_part / other_whole if other_whole else None

    if here is None or there is None:
        return Difference(name, here, there)

    error = math.sqrt(
        (here * (1 - here) / whole if whole else 0.0)
        + (there * (1 - there) / other_whole if other_whole else 0.0)
    )

    return Difference(name, here, there, error or None)


def read_out(comparison: Comparison, *, width: int = 78) -> str:
    """
    Write a comparison out for a person.
    """
    if comparison.paired:
        return _read_out_paired(comparison, width=width)

    lines = [
        "=" * width,
        f"Card test — {comparison.subject}",
        "=" * width,
        "",
        f"  Verdict: {comparison.verdict}",
        "",
        f"  {comparison.games} games with it, {comparison.games} without,"
        f" on the same seeds",
        f"  it turned up in {comparison.appeared} of them",
    ]

    if not comparison.reshuffled:
        lines += [
            f"  played on RNG model {comparison.rng_model}: taking the card out"
            f" moves no other card",
        ]

    if comparison.errors_with or comparison.errors_without:
        lines += [
            "",
            f"  games that fell over: {comparison.errors_with} with it, "
            f"{comparison.errors_without} without",
        ]

        if comparison.errors_without > comparison.errors_with:
            lines += [
                "  Games that could not be dealt without it are games where",
                "  another card named it — a starting item, most likely. The",
                "  comparison is between unequal numbers of games and is worth",
                "  less than it looks.",
            ]

    if not comparison.appeared:
        lines += [
            "",
            "  The card never reached the table, so nothing below is about it.",
        ]
    elif not comparison.can_be_about_the_card and comparison.reshuffled:
        lines += [
            "",
            "  It reached the table too rarely for the numbers below to be its",
            "  doing: taking a card out of the deck reshuffles every game, so",
            "  the two runs differ everywhere, not only where the card is.",
        ]
    elif not comparison.can_be_about_the_card:
        lines += [
            "",
            "  It reached the table too rarely for the numbers below to be its",
            "  doing: a game it never touched plays out the same in both runs,",
            "  so whatever differs comes from too few games to read.",
        ]

    lines += ["", "-" * width, f"  {'':<22}{'with':>12}{'without':>12}{'change':>20}", "-" * width]

    for difference in comparison.differences:
        change = difference.change

        told = (
            "—"
            if change is None
            else f"{change:+.2f} ± {difference.error:.2f}"
            if difference.error is not None
            else f"{change:+.2f}"
        )

        mark = (
            "  *"
            if difference.tells_us_anything and comparison.can_be_about_the_card
            else ""
        )

        lines.append(
            f"  {difference.name:<22}"
            f"{_number(difference.with_it):>12}"
            f"{_number(difference.without_it):>12}"
            f"{told:>20}{mark}"
        )

    lines += ["-" * width, ""]

    if comparison.can_be_about_the_card:
        lines += [
            "  * bigger than twice its own uncertainty, and the card was in",
            "    enough games for that to be worth saying. Everything unmarked",
            "    is within the noise of this many games and says nothing.",
            "",
        ]
    elif comparison.reshuffled:
        lines += [
            "  Nothing is marked: with the card this scarce, the difference",
            "  between the runs is the deck rather than the card.",
            "",
        ]
    else:
        lines += [
            "  Nothing is marked: the card was too scarce for a difference",
            "  between the runs to be read as its doing.",
            "",
        ]

    return "\n".join(lines)


def _read_out_paired(comparison: Comparison, *, width: int) -> str:
    """
    Write a paired comparison out: every game read against its own game
    without the card.
    """
    lines = [
        "=" * width,
        f"Card test — {comparison.subject}",
        "=" * width,
        "",
        f"  Verdict: {comparison.verdict}",
        "",
        f"  {comparison.games} games with it, {comparison.games} without,"
        f" on the same seeds",
        f"  it was played in {comparison.appeared} games with it",
        f"  played on RNG model {comparison.rng_model}: taking the card out"
        f" moves no other card,",
        "  so each game is read against its own game without the card",
    ]

    if comparison.errors_with or comparison.errors_without:
        lines += [
            "",
            f"  games that fell over: {comparison.errors_with} with it, "
            f"{comparison.errors_without} without",
            f"  {len(comparison.excluded)} pairs left out whole, a fallen game taking"
            f" its other half with it:",
        ]

        lines += [f"    seed {seed}: {reason}" for seed, reason in comparison.excluded[:5]]

        if len(comparison.excluded) > 5:
            lines.append(f"    and {len(comparison.excluded) - 5} more")

        if comparison.errors_without > comparison.errors_with:
            lines += [
                "  Games that could not be dealt without it are games where",
                "  another card named it — a starting item, most likely.",
            ]

    lines += [
        "",
        "-" * width,
        f"  {'':<22}{'with':>12}{'without':>12}{'change':>20}{'differed':>10}",
        "-" * width,
    ]

    for difference in comparison.differences:
        change = difference.change

        told = (
            "—"
            if change is None
            else f"{change:+.2f} ± {difference.error:.2f}"
            if difference.error is not None
            else f"{change:+.2f}"
        )

        mark = (
            "  *"
            if difference.tells_us_anything and comparison.can_be_about_the_card
            else ""
        )

        differed = "—" if difference.differing is None else str(difference.differing)

        lines.append(
            f"  {difference.name:<22}"
            f"{_number(difference.with_it):>12}"
            f"{_number(difference.without_it):>12}"
            f"{told:>20}"
            f"{differed:>10}{mark}"
        )

    lines += ["-" * width, ""]

    for difference in comparison.differences:
        if difference.method == MCNEMAR_EXACT and difference.discordant is not None:
            only_with, only_without = difference.discordant
            tested = "no pair disagreed" if difference.p is None else f"p = {difference.p:.4f}"

            lines += [
                f"  {difference.name}: {only_with} only with it, {only_without} only"
                f" without it; exact McNemar {tested}",
                "",
            ]

    if comparison.unchanged:
        lines += [
            "  Nothing is marked: every game came out the same with the card and",
            "  without it, in every measure.",
            "",
        ]
    elif comparison.can_be_about_the_card:
        lines += [
            "  * bigger than twice its own uncertainty, in a measure that differed",
            f"    in at least {MIN_DIFFERING} games — or, for a share of games, an exact",
            f"    McNemar p of {MCNEMAR_LINE} or less. Everything unmarked is within",
            "    the noise of this many games and says nothing. A change with no ±",
            "    moved by the same amount in every game, or could not be measured.",
            "",
        ]
    else:
        lines += [
            "  Nothing is marked: too few games differed for a difference to be",
            f"  read — fewer than {MIN_DIFFERING} in every measure, and no share an"
            f" exact test",
            "  could tell from chance.",
            "",
        ]

    return "\n".join(lines)


def _number(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"
