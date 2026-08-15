# src/fsme/analysis/study.py

"""
What a pile of games has to say.

Four questions, each answered from the summaries and each answerable back to a
seed. Why the winners won. Which cards travel together. Which games are worth
looking at by hand. And, when a bot was playing, what it actually does.

The statistics are deliberately plain — differences of means, ratios of counts,
standard errors — because the point is that a reader can check them. Anything
that needed a model would need the model defending too, and a balance report
nobody can audit is a balance report nobody should act on.

Three cautions are built in rather than left to the reader.

Winners are compared with losers, which is a comparison between people who won
and people who did not, and everything separating them is as much a symptom as
a cause: a player who killed four monsters won because of it *and* killed the
fourth because they were already ahead. The wording says "went with winning",
never "caused".

Pairs are the same trap, sharper. With hundreds of cards there are tens of
thousands of pairs, so the most striking one in any run is striking by
arithmetic alone. Every pair here is reported with how many games it rests on,
nothing under a floor is shown, and the reading says outright that a pair from
one run is a hypothesis rather than a synergy.

Anomalies are rules, not judgements: each one is named and each says what it
looked at, so a flagged game can be dismissed by a reader who disagrees.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

from .summary import GameSummary, SeatFacts

TOGETHER_AT_LEAST = 5
"""
Games a pair must share before it is worth printing.

Not a significance test. Two cards seen together twice will happily show a
winrate of 100%, and printing that invites a reader to believe it.
"""


@dataclass(slots=True)
class Split:
    """
    One measurement, taken over winners and over everybody else.
    """

    what: str

    winners: float = 0.0
    losers: float = 0.0

    error: float | None = None

    @property
    def gap(self) -> float:
        return self.winners - self.losers

    @property
    def beyond_noise(self) -> bool:
        return (
            self.error is not None
            and self.error > 0
            and abs(self.gap) >= 2 * self.error
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "what": self.what,
            "winners": self.winners,
            "losers": self.losers,
            "gap": self.gap,
            "error": self.error,
            "beyond_noise": self.beyond_noise,
        }


@dataclass(slots=True)
class Pair:
    """
    Two cards that were used by the same player in the same game.
    """

    one: str
    other: str

    names: tuple[str, str] = ("", "")

    together: int = 0
    won_together: int = 0

    expected: float = 0.0
    """
    How often they would have met by chance, given how common each one is.

    The comparison that makes a co-occurrence worth a second look: two cards in
    every deck meet constantly and mean nothing by it.
    """

    @property
    def lift(self) -> float | None:
        """
        How much more often they met than chance would have them meet.
        """
        return self.together / self.expected if self.expected else None

    @property
    def rate(self) -> float | None:
        return self.won_together / self.together if self.together else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "one": self.one,
            "other": self.other,
            "names": list(self.names),
            "together": self.together,
            "won_together": self.won_together,
            "expected": self.expected,
            "lift": self.lift,
            "winrate": self.rate,
        }


@dataclass(slots=True)
class Oddity:
    """
    One game a rule thought was worth a look, and the rule that thought so.
    """

    seed: int
    rule: str
    saying: str

    def to_dict(self) -> dict[str, Any]:
        return {"seed": self.seed, "rule": self.rule, "saying": self.saying}


@dataclass(slots=True)
class Thinking:
    """
    What a bot did, over as many decisions as it made.
    """

    moves: int = 0
    forced: int = 0

    won: int = 0
    seats: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "moves": self.moves,
            "forced": self.forced,
            "seats": self.seats,
            "won": self.won,
            "winrate": self.won / self.seats if self.seats else None,
        }


@dataclass(slots=True)
class Study:
    """
    Everything a pile of games was asked, and what it said.
    """

    games: int = 0
    finished: int = 0

    splits: list[Split] = field(default_factory=list)
    pairs: list[Pair] = field(default_factory=list)
    oddities: list[Oddity] = field(default_factory=list)

    souls_from: Counter[str] = field(default_factory=Counter)
    winning_souls_from: Counter[str] = field(default_factory=Counter)

    thinking: Thinking = field(default_factory=Thinking)

    def to_dict(self) -> dict[str, Any]:
        return {
            "games": self.games,
            "finished": self.finished,
            "splits": [split.to_dict() for split in self.splits],
            "pairs": [pair.to_dict() for pair in self.pairs],
            "oddities": [oddity.to_dict() for oddity in self.oddities],
            "souls_from": dict(sorted(self.souls_from.items())),
            "winning_souls_from": dict(sorted(self.winning_souls_from.items())),
            "thinking": self.thinking.to_dict(),
        }


MEASURES: tuple[tuple[str, Any], ...] = (
    ("monsters killed", lambda seat: float(seat.kills)),
    ("attacks made", lambda seat: float(seat.attacks)),
    ("times died", lambda seat: float(seat.deaths)),
    ("coins gained", lambda seat: float(seat.coins_gained)),
    ("items bought", lambda seat: float(seat.purchases)),
    ("cards used", lambda seat: float(len(seat.cards_used))),
    ("moves made", lambda seat: float(seat.moves)),
)
"""
What is measured about a seat.

Each is a count of something the engine recorded, and each is a thing a player
does rather than a thing that happens to them — which is as close to a cause as
counting can get.
"""


def study(summaries: list[GameSummary], *, names: dict[str, str] | None = None) -> Study:
    """
    Ask a pile of games the four questions.
    """
    told = Study(
        games=len(summaries),
        finished=sum(1 for summary in summaries if summary.finished),
    )

    winners: list[SeatFacts] = []
    losers: list[SeatFacts] = []

    for summary in summaries:
        for seat in summary.seats:
            (winners if seat.won else losers).append(seat)

            told.souls_from.update(seat.souls_from)

            if seat.won:
                told.winning_souls_from.update(seat.souls_from)

            told.thinking.moves += seat.thought
            told.thinking.forced += seat.forced_moves if seat.thought else 0

            if seat.thought:
                told.thinking.seats += 1
                told.thinking.won += 1 if seat.won else 0

    told.splits = _what_separated_them(winners, losers)
    told.pairs = _what_travelled_together(summaries, names or {})
    told.oddities = _what_looks_odd(summaries)

    return told


def _what_separated_them(
    winners: list[SeatFacts], losers: list[SeatFacts]
) -> list[Split]:
    """
    Measure the same things about winners and about everybody else.
    """
    splits: list[Split] = []

    for what, measure in MEASURES:
        here = [measure(seat) for seat in winners]
        there = [measure(seat) for seat in losers]

        if not here or not there:
            continue

        splits.append(
            Split(
                what=what,
                winners=_mean(here),
                losers=_mean(there),
                error=_error(here, there),
            )
        )

    return sorted(splits, key=lambda split: -abs(split.gap))


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _error(here: list[float], there: list[float]) -> float | None:
    """
    The standard error of the difference between two means.
    """
    if len(here) < 2 or len(there) < 2:
        return None

    spread = _variance(here) / len(here) + _variance(there) / len(there)

    return math.sqrt(spread) or None


def _variance(values: list[float]) -> float:
    average = _mean(values)

    return sum((value - average) ** 2 for value in values) / (len(values) - 1)


def _what_travelled_together(
    summaries: list[GameSummary], names: dict[str, str]
) -> list[Pair]:
    """
    Find cards that turned up in the same hands more often than chance.

    Counted per seat rather than per game: two cards played by two different
    players in the same game did not travel together, and counting them as a
    pair would make every popular card the partner of every other.
    """
    seats = 0
    alone: Counter[str] = Counter()
    both: Counter[tuple[str, str]] = Counter()
    both_won: Counter[tuple[str, str]] = Counter()

    for summary in summaries:
        for seat in summary.seats:
            seats += 1

            used = sorted(seat.cards_used)

            alone.update(used)

            for pair in combinations(used, 2):
                both[pair] += 1

                if seat.won:
                    both_won[pair] += 1

    if not seats:
        return []

    pairs: list[Pair] = []

    for (one, other), together in both.items():
        if together < TOGETHER_AT_LEAST:
            continue

        expected = alone[one] * alone[other] / seats

        pairs.append(
            Pair(
                one=one,
                other=other,
                names=(names.get(one, one), names.get(other, other)),
                together=together,
                won_together=both_won[(one, other)],
                expected=expected,
            )
        )

    return sorted(
        pairs,
        key=lambda pair: (-(pair.lift or 0.0), -pair.together, pair.one),
    )


def _what_looks_odd(summaries: list[GameSummary]) -> list[Oddity]:
    """
    Flag games that a named rule says are worth a look.

    Every rule is arithmetic on the summaries and says what it looked at, so a
    reader can disagree with one without having to distrust the rest.
    """
    if not summaries:
        return []

    odd: list[Oddity] = []

    lengths = [float(summary.turns) for summary in summaries if summary.finished]
    typical = _mean(lengths) if lengths else 0.0
    spread = math.sqrt(_variance(lengths)) if len(lengths) > 1 else 0.0

    for summary in summaries:
        if not summary.finished:
            odd.append(
                Oddity(
                    summary.seed,
                    "unfinished",
                    f"nobody won within {summary.commands} commands",
                )
            )

            continue

        if spread and abs(summary.turns - typical) > 3 * spread:
            odd.append(
                Oddity(
                    summary.seed,
                    "length",
                    f"{summary.turns} turns against a usual {typical:.0f}",
                )
            )

        winner = summary.winning_seat

        if winner is not None and winner.kills == 0 and winner.souls:
            odd.append(
                Oddity(
                    summary.seed,
                    "won without fighting",
                    f"{winner.name} won with {winner.souls} souls and no kills",
                )
            )

        idle = [seat for seat in summary.seats if seat.moves == 0]

        if idle:
            odd.append(
                Oddity(
                    summary.seed,
                    "a seat never acted",
                    ", ".join(seat.name for seat in idle),
                )
            )

        starved = [
            seat
            for seat in summary.seats
            if seat.deaths > max(8, 4 * _mean([s.deaths for s in summary.seats]))
        ]

        if starved:
            odd.append(
                Oddity(
                    summary.seed,
                    "one seat died far more than the rest",
                    ", ".join(
                        f"{seat.name} {seat.deaths} times" for seat in starved
                    ),
                )
            )

    return odd
