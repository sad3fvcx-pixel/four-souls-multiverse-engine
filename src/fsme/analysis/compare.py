# src/fsme/analysis/compare.py

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
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .tally import Tally

ENOUGH = 0.1
"""
How often a card must reach the table before a difference can be about it.

One in ten is not a statistical threshold and is not pretending to be one. It
is the point below which the two runs plainly differ by more than the card —
every shuffle having moved — and the reading stops offering its numbers as if
they were about the card.
"""


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
    printed differently.
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
        a reader is not invited to draw it wherever suits them.
        """
        change = self.change

        if change is None or self.error is None or self.error <= 0:
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

    The number that decides whether the rest means anything: a card that never
    reached the table cannot have changed the game, and a comparison that shows
    a difference anyway is showing noise.
    """

    differences: tuple[Difference, ...] = ()

    errors_with: int = 0
    errors_without: int = 0

    @property
    def can_be_about_the_card(self) -> bool:
        """
        Whether the card was in enough games for a difference to be its doing.
        """
        return bool(self.games) and self.appeared >= self.games * ENOUGH

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "games": self.games,
            "appeared": self.appeared,
            "can_be_about_the_card": self.can_be_about_the_card,
            "differences": [difference.to_dict() for difference in self.differences],
            "errors_with": self.errors_with,
            "errors_without": self.errors_without,
        }


def compare(
    subject: str,
    with_it: Tally,
    without_it: Tally,
    *,
    appeared: int = 0,
    errors_with: int = 0,
    errors_without: int = 0,
) -> Comparison:
    """
    Measure the same handful of things in both runs.

    The measurements are properties of a game rather than of a player: how long
    it ran, how often somebody died, how often an attack landed. A card's
    effect on *whose* game it is cannot be read from a run where only one table
    in three even drew it, so it is not offered.
    """
    return Comparison(
        subject=subject,
        games=min(with_it.games, without_it.games),
        appeared=appeared,
        errors_with=errors_with,
        errors_without=errors_without,
        differences=(
            _mean(
                "turns a game",
                with_it.turns,
                with_it.games,
                without_it.turns,
                without_it.games,
            ),
            _mean(
                "commands a game",
                with_it.commands,
                with_it.games,
                without_it.commands,
                without_it.games,
            ),
            _mean(
                "deaths a game",
                with_it.deaths,
                with_it.games,
                without_it.deaths,
                without_it.games,
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
    name: str, total: int, games: int, other_total: int, other_games: int
) -> Difference:
    """
    Compare two averages of counts per game.

    The spread is estimated from the average itself, as a count over a fixed
    number of games is: it is the roughest of estimates and it is honest about
    the order of magnitude, which is all that is being asked of it here.
    """
    here = total / games if games else None
    there = other_total / other_games if other_games else None

    if here is None or there is None:
        return Difference(name, here, there)

    error = math.sqrt(
        (here / games if games else 0.0) + (there / other_games if other_games else 0.0)
    )

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
    lines = [
        "=" * width,
        f"Card test — {comparison.subject}",
        "=" * width,
        "",
        f"  {comparison.games} games with it, {comparison.games} without,"
        f" on the same seeds",
        f"  it turned up in {comparison.appeared} of them",
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
    elif not comparison.can_be_about_the_card:
        lines += [
            "",
            "  It reached the table too rarely for the numbers below to be its",
            "  doing: taking a card out of the deck reshuffles every game, so",
            "  the two runs differ everywhere, not only where the card is.",
        ]

    lines += ["", "-" * width, f"  {'':<22}{'with':>12}{'without':>12}{'change':>14}", "-" * width]

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
            f"{told:>14}{mark}"
        )

    lines += ["-" * width, ""]

    if comparison.can_be_about_the_card:
        lines += [
            "  * bigger than twice its own uncertainty, and the card was in",
            "    enough games for that to be worth saying. Everything unmarked",
            "    is within the noise of this many games and says nothing.",
            "",
        ]
    else:
        lines += [
            "  Nothing is marked: with the card this scarce, the difference",
            "  between the runs is the deck rather than the card.",
            "",
        ]

    return "\n".join(lines)


def _number(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"
