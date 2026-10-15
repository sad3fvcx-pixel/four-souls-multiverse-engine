# src/fsme/lab/analysis/study.py

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

SEEN_AT_LEAST = 10
"""
Seats a card must have been used by before its winrate is worth doubting.

A card used three times and winning twice looks like the best card in the game
and is a coin landing the same way twice.
"""

IN_NEARLY_EVERY_HAND = 0.9
"""
How often a card must turn up before its ubiquity is itself the finding.
"""

PAIRS_WORTH_CHASING = 3
"""
How far down the pair table a card is still worth putting under test.
"""

GAMES_FOR_A_TEST = 200
"""
Games each side of a card test is offered, in the commands this suggests.

Enough for the difference of means to have an interval worth reading, and few
enough to finish while somebody is waiting. Both runs are played, so the
suggested command is twice this many games of work.
"""

BUSYNESS_BANDS = 5
"""
How many bands seats are sorted into by how many cards they got through.

The correction that stops this section being nonsense. A player who is winning
takes more turns, and a player who takes more turns uses more cards, so *every*
card is used disproportionately by winners and a flat comparison marks the
whole deck as overpowered. Comparing a card's users against seats that were
equally busy takes that back out.

Five is a compromise between bands narrow enough to match like with like and
bands wide enough to have some seats in them.
"""

A_FALSE_ROW_IN = 0.05
"""
How often this section is willing to print a card that is only luck.

Spread across every card examined, not per card: a run looks at hundreds of
cards, and a threshold applied to each of them separately would mark ten of
them in a deck where nothing is wrong at all.
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
class Suspect:
    """
    A card a run thinks is worth putting under test, and why.

    The end of what a study can do and the start of what it cannot. Everything
    a study measures is a correlation inside one run — a card that turns up in
    winning hands may be winning games or may simply be a card winners draw. A
    suspect is that correlation written down with the command that would settle
    it, so the reader's next step is a measurement rather than a belief.
    """

    card: str
    name: str = ""

    rule: str = ""
    """The named reason this card was picked out, so it can be disagreed with."""

    saying: str = ""

    seats: int = 0
    won: int = 0

    rate: float | None = None

    base: float = 0.0
    """
    How often its users would have won anyway, from how busy their games were.

    Not the winrate of the table. A card is compared against seats that got
    through about as many cards as its users did, because otherwise it is
    being compared against seats that were losing and idle — and every card in
    the game beats those.
    """

    sigmas: float = 0.0
    """
    How far from that expectation it landed, in standard errors.

    Kept in the row so the reader can see how much of a stretch the rule made,
    rather than only that it fired.
    """

    @property
    def command(self) -> str:
        """
        The command that would turn this suspicion into a measurement.
        """
        return f"fsme test-card {self.card} --games {GAMES_FOR_A_TEST}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "card": self.card,
            "name": self.name,
            "rule": self.rule,
            "saying": self.saying,
            "seats": self.seats,
            "won": self.won,
            "rate": self.rate,
            "base": self.base,
            "sigmas": self.sigmas,
            "command": self.command,
        }


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
    suspects: list[Suspect] = field(default_factory=list)

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
            "suspects": [suspect.to_dict() for suspect in self.suspects],
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
    told.suspects = _what_is_worth_testing(summaries, names or {}, told.pairs)

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


def _what_is_worth_testing(
    summaries: list[GameSummary], names: dict[str, str], pairs: list[Pair]
) -> list[Suspect]:
    """
    Pick the cards whose numbers are worth spending a card test on.

    Three rules, each named in the row it produces. A card whose users won far
    more or far less often than a seat picked at random. A card that turned up
    in nearly every hand, where the finding is the ubiquity rather than the
    winrate. And a card at the top of the pair table, where the pair is the
    thing under suspicion and the card is the way to test it.

    None of these is evidence. Each is a reason to run the measurement that
    would be, which is why every suspect carries the command that runs it.
    """
    everyone = [seat for summary in summaries for seat in summary.seats]

    if not everyone:
        return []

    chances = _how_busy_they_were(everyone)

    seats = len(everyone)
    used: Counter[str] = Counter()
    won: Counter[str] = Counter()
    expected: dict[str, float] = {}
    spread: dict[str, float] = {}

    for seat, chance in zip(everyone, chances, strict=True):
        for card in seat.cards_used:
            used[card] += 1
            won[card] += 1 if seat.won else 0

            expected[card] = expected.get(card, 0.0) + chance
            spread[card] = spread.get(card, 0.0) + chance * (1 - chance)

    examined = sum(1 for card, seen in used.items() if seen >= SEEN_AT_LEAST)
    stretch = _how_far_is_too_far(examined)

    suspects: dict[str, Suspect] = {}

    def suspect(
        card: str, rule: str, saying: str, sigmas: float = 0.0
    ) -> None:
        # First rule to name a card keeps it: two rows for one card would be
        # two entries in a queue of tests that runs the same test twice.
        if card in suspects:
            return

        seen = used[card]

        suspects[card] = Suspect(
            card=card,
            name=names.get(card, card),
            rule=rule,
            saying=saying,
            seats=seen,
            won=won[card],
            rate=won[card] / seen if seen else None,
            base=expected.get(card, 0.0) / seen if seen else 0.0,
            sigmas=sigmas,
        )

    for card, seen in used.most_common():
        if seen < SEEN_AT_LEAST:
            continue

        if seen >= seats * IN_NEARLY_EVERY_HAND:
            suspect(
                card,
                "in nearly every hand",
                f"used by {seen} of {seats} seats — a staple, and a staple is"
                f" worth knowing the price of",
            )

            continue

        noise = math.sqrt(spread.get(card, 0.0))

        if not noise:
            continue

        sigmas = (won[card] - expected[card]) / noise

        if abs(sigmas) < stretch:
            continue

        suspect(
            card,
            "won more than its share" if sigmas > 0 else "won less than it",
            f"{won[card]} of {seen} seats using it won, against"
            f" {expected[card]:.1f} expected of seats as busy as theirs"
            f" ({sigmas:+.1f} σ)",
            sigmas,
        )

    for pair in pairs[:PAIRS_WORTH_CHASING]:
        for card, other in ((pair.one, pair.other), (pair.other, pair.one)):
            if used[card] < SEEN_AT_LEAST:
                continue

            suspect(
                card,
                "top of the pair table",
                f"met {names.get(other, other)} {pair.together} times,"
                f" {pair.lift or 0:.1f}× what chance would have",
            )

    return sorted(suspects.values(), key=lambda found: -abs(found.sigmas))


def _how_busy_they_were(everyone: list[SeatFacts]) -> list[float]:
    """
    Give each seat the winrate of seats that got through as many cards as it.

    The confound this exists to remove is not subtle: a seat that is winning
    takes more turns, uses more cards, and would show up in the users of every
    card in the deck. Grouping seats by how many cards they used and taking
    each group's own winrate gives every seat the chance it had before any
    particular card is credited with anything.

    Seats that used the same number of cards are never split between two bands,
    however the arithmetic falls. Splitting them would put identical seats on
    opposite sides of a line and hand them different expectations, which is the
    confound coming back in through the correction.
    """
    together: dict[int, list[int]] = {}

    for index, seat in enumerate(everyone):
        together.setdefault(len(seat.cards_used), []).append(index)

    least = max(1, len(everyone) // max(1, BUSYNESS_BANDS))

    bands: list[list[int]] = []
    building: list[int] = []

    for busyness in sorted(together):
        building.extend(together[busyness])

        if len(building) >= least:
            bands.append(building)
            building = []

    if building:
        # A remainder too small to speak for itself joins the band below it.
        if bands:
            bands[-1].extend(building)
        else:
            bands.append(building)

    chances = [0.0] * len(everyone)

    for band in bands:
        rate = sum(1 for index in band if everyone[index].won) / len(band)

        for index in band:
            chances[index] = rate

    return chances


def _how_far_is_too_far(examined: int) -> float:
    """
    How many standard errors a card must be out before it is worth printing.

    Two would be the usual line for one card looked at once. This section looks
    at every card in the content, so the line is moved out until a run of a
    perfectly balanced deck would produce a false row only ``A_FALSE_ROW_IN``
    of the time — which is the only way a list of "suspicious cards" is not
    simply a list of the most-used cards.
    """
    if examined < 1:
        return 2.0

    wanted = A_FALSE_ROW_IN / examined

    low, high = 0.0, 12.0

    for _ in range(64):
        middle = (low + high) / 2

        # The two-sided chance of landing this far out by luck alone.
        if math.erfc(middle / math.sqrt(2)) > wanted:
            low = middle
        else:
            high = middle

    return max(2.0, (low + high) / 2)


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
