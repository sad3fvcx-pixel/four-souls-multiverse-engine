# src/fsme/lab/analysis/party.py

"""
One game, one report.

Everything this package can say about a single game, said once, in an order a
person reads rather than an order a program computes: who won and how long it
took, where the game turned, why the winner won, what beat everybody else, the
decisions that stood out in both directions, and which cards did the work.

Nothing here measures anything. Every number comes from ``summary``,
``moments`` or ``risk``, and this module's whole job is arrangement — which is
worth its own file because arrangement is where a report either becomes usable
or becomes six tables stapled together.

The cautions come with the numbers rather than being restated. What separated
the winner from the table went *with* winning; the turning points are where the
game went and not proof it had to go there; a decision the bot dislikes is a
disagreement with a readable opinion; a card at the top of the contributions
did work in this game and is not thereby a good card. Each section carries the
sentence that says so, because a section read on its own has to be honest on
its own.

One structural decision worth defending: the report *composes* the existing
reports rather than reimplementing them. If ``explain`` and this ever disagreed
about the same game, one of them would be wrong and there would be no way to
tell which — so they cannot, because they read the same objects.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from fsme.content import ContentLibrary
from fsme.journal import Journal

from .moments import Contribution, Turning, turning_points
from .risk import Risks, Risky, risks
from .study import MEASURES
from .summary import GameSummary, SeatFacts, summarise

WIDTH = 78

CARDS_WORTH_NAMING = 6

SOUL_WORDS = {
    "monster": "monsters",
    "card": "cards",
    "unnamed": "effects that named no card",
}


@dataclass(slots=True)
class Review:
    """
    A whole game, assembled.
    """

    summary: GameSummary
    turning: Turning
    dangers: Risks | None = None

    names: dict[str, str] = field(default_factory=dict)
    """Card identifiers to printed names, when the content was to hand."""

    @property
    def winner(self) -> SeatFacts | None:
        return self.summary.winning_seat

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary.to_dict(),
            "turning": self.turning.to_dict(),
            "dangers": None if self.dangers is None else self.dangers.to_dict(),
        }


def review(
    journal: Journal,
    library: ContentLibrary | None = None,
    *,
    moments: int = 3,
    decisions: int = 3,
) -> Review:
    """
    Read one game every way this package knows how.

    ``library`` is what makes the decisions section possible: weighing a move
    means replaying the game, and replaying it means having the cards. Without
    one the report is still a report, and says which section is missing rather
    than leaving a gap.
    """
    return Review(
        summary=summarise(journal),
        turning=turning_points(journal, top=max(0, moments)),
        dangers=(
            risks(journal, library, top=max(1, decisions))
            if library is not None and decisions > 0
            else None
        ),
        names=(
            {}
            if library is None
            else {
                definition.id: definition.name
                for definition in library.definitions()
            }
        ),
    )


def reviewed(report: Review, *, width: int = WIDTH) -> str:
    """
    Write the whole report out for a person.
    """
    return "\n".join(_lines(report, width=width))


def _lines(report: Review, *, width: int) -> Iterator[str]:
    summary = report.summary

    yield "=" * width
    yield "FSME GAME REPORT".center(width)
    yield "=" * width
    yield ""

    winner = report.winner

    if winner is None:
        yield f"  Nobody won. {summary.turns} turns, {summary.commands} moves."
    else:
        yield f"  Winner        {winner.name} — {winner.character or 'no character'}"
        yield f"  Length        {summary.turns} turns, {summary.commands} moves"
        yield f"  Souls         {winner.souls}, from {_souls_of(winner)}"

    yield f"  Seed          {summary.seed}, {summary.players} players"
    yield ""

    yield from _standings(report, width=width)
    yield from _key_moments(report, width=width)
    yield from _why_they_won(report, width=width)
    yield from _why_the_others_lost(report, width=width)
    yield from _decisions(report, width=width)
    yield from _cards(report, width=width)


def _souls_of(seat: SeatFacts) -> str:
    if not seat.souls_from:
        return "nowhere the record names"

    return ", ".join(
        f"{count} from {SOUL_WORDS.get(kind, kind)}"
        for kind, count in sorted(seat.souls_from.items())
    )


def _heading(title: str, *, width: int) -> Iterator[str]:
    yield "-" * width
    yield f"  {title}"
    yield "-" * width
    yield ""


def _standings(report: Review, *, width: int) -> Iterator[str]:
    yield from _heading("The table", width=width)

    yield (
        f"  {'':<14}{'souls':>7}{'kills':>7}{'attacks':>9}"
        f"{'died':>7}{'coins':>7}{'bought':>8}{'moves':>7}"
    )

    for seat in report.summary.seats:
        mark = "*" if seat.won else " "

        yield (
            f"{mark} {seat.name[:13]:<14}"
            f"{seat.souls:>7}{seat.kills:>7}{seat.attacks:>9}"
            f"{seat.deaths:>7}{seat.coins_gained:>7}"
            f"{seat.purchases:>8}{seat.moves:>7}"
        )

    yield ""


def _key_moments(report: Review, *, width: int) -> Iterator[str]:
    turning = report.turning

    yield from _heading("Key moments", width=width)

    if not turning.moments:
        yield "  Nothing in this game moved the scoreboard."
        yield ""

        return

    if not turning.won:
        yield (
            f"  Nobody won, so these are measured towards"
            f" {turning.towards_name}, who came closest."
        )
        yield ""

    for place, moment in enumerate(turning.moments, start=1):
        told = ", ".join(moment.said) or moment.label

        yield f"  {place}. Turn {moment.turn} — {told}"
        yield f"     {moment.who}: {moment.label}   (swing {moment.swing:+.2f})"

        if moment.chance is not None:
            yield (
                f"     the first roll had a {moment.chance * 100:.0f}% chance"
                f" of landing"
            )

        if moment.decided_by_dice:
            yield f"     decided by the dice ({', '.join(str(f) for f in moment.dice)})"

        yield ""

    yield (
        f"  Out of {turning.weighed} moves that moved anything, in a game of"
        f" {turning.moves}."
    )
    yield "  This is where the game went, not proof it had to go there."
    yield ""


def _why_they_won(report: Review, *, width: int) -> Iterator[str]:
    winner = report.winner

    if winner is None:
        return

    yield from _heading(f"Why {winner.name} won", width=width)

    others = [seat for seat in report.summary.seats if seat.seat != winner.seat]

    said = list(_apart_from(winner, others))

    if not said:
        yield "  They did nothing the rest of the table did not do."
        yield "  In one game that happens, and it means the dice decided it."
        yield ""

        return

    for word in said:
        yield f"  · {word}"

    yield ""
    yield "  This is what differed, not what helped: the report has no opinion"
    yield "  about whether more of a thing is better, and a winner who died"
    yield "  more often than the table will say so here."
    yield ""
    yield "  And these went with winning rather than causing it. A player who"
    yield "  killed four monsters won partly because of it and killed the"
    yield "  fourth partly because they were winning; in one game the two"
    yield "  cannot be told apart."
    yield ""


def _apart_from(
    seat: SeatFacts, others: list[SeatFacts], *, called: str = "the table"
) -> Iterator[str]:
    """
    What one seat did more or less of than whoever it is being held against.
    """
    if not others:
        return

    for what, measure in MEASURES:
        mine = measure(seat)
        theirs = sum(measure(other) for other in others) / len(others)

        if theirs == 0 and mine == 0:
            continue

        gap = mine - theirs

        # A tenth of the table's own figure, or a whole unit, whichever is
        # larger: a difference smaller than that is not worth a sentence.
        if abs(gap) < max(1.0, theirs * 0.1):
            continue

        yield f"{what}: {mine:.0f} against {called}'s {theirs:.1f} ({gap:+.1f})"


def _why_the_others_lost(report: Review, *, width: int) -> Iterator[str]:
    winner = report.winner
    losers = [seat for seat in report.summary.seats if not seat.won]

    if not losers or winner is None:
        return

    yield from _heading("Why the others did not", width=width)

    dangers = report.dangers

    for seat in losers:
        yield f"  {seat.name}"

        said = list(_apart_from(seat, [winner], called=winner.name))

        # Neutral, because these are counts and the report does not know which
        # direction of a count is the good one.
        for word in said[:3]:
            yield f"    · {word}"

        # These are not neutral: a reason the bot held against a move is a
        # stated cost, in the move's own arithmetic.
        if dangers is not None:
            for risk in _theirs(dangers.riskiest, seat.seat)[:2]:
                yield f"    - turn {risk.turn}: {risk.label} — {_worst_of(risk)}"

        if not said and (dangers is None or not _theirs(dangers.riskiest, seat.seat)):
            yield "    · nothing the record separates them by; they were behind"

        yield ""

    if dangers is None:
        yield "  (decisions were not weighed: no content was given to replay with)"
        yield ""


def _theirs(risks: list[Risky], seat: int) -> list[Risky]:
    return [risk for risk in risks if risk.player == seat]


def _worst_of(risk: Risky) -> str:
    """
    The single heaviest thing that counted against a move, in its own words.
    """
    if not risk.dangers:
        return f"{risk.regret:+.1f} against the bot's choice"

    heaviest = min(risk.dangers, key=lambda danger: danger.worth)

    return f"{heaviest.what} ({heaviest.value:g})"


def _decisions(report: Review, *, width: int) -> Iterator[str]:
    dangers = report.dangers

    if dangers is None:
        return

    yield from _heading("The decisions", width=width)

    if not dangers.faithful:
        yield "  The replay diverged from the journal, so nothing here is about"
        yield "  this game. The engine has changed under it."
        yield ""

        return

    yield f"  Judged by {dangers.by}, a bot that looks one move ahead and does"
    yield "  not know what most cards say. A gap below is a disagreement with a"
    yield "  readable opinion, not a proven mistake."
    yield ""

    if dangers.bot_seats:
        seats = ", ".join(str(seat) for seat in dangers.bot_seats)

        yield (
            f"  Seats {seats} were played by that bot, so they take the best"
            f" move every"
        )
        yield "  time by construction and appear only in the good column."
        yield ""

    yield "  Best — took the top option with the next well behind:"
    yield ""

    yield from _rows(dangers.best, measured=lambda risk: risk.margin, nothing=(
        "nothing on offer was clearly better than anything else"
    ))

    yield "  Worst — the bot would have played something else:"
    yield ""

    yield from _rows(dangers.worst, measured=lambda risk: risk.regret, nothing=(
        "it would have played the same"
    ))

    yield (
        f"  {dangers.weighed} moves weighed, {dangers.forced} of them forced,"
        f" {dangers.skipped} skipped."
    )
    yield ""


def _rows(
    risks: list[Risky], *, measured: Any, nothing: str
) -> Iterator[str]:
    if not risks:
        yield f"    {nothing}"
        yield ""

        return

    for risk in risks:
        again = (
            ""
            if risk.times < 2
            else ", and once more"
            if risk.times == 2
            else f", and {risk.times - 1} more times"
        )

        yield (
            f"    turn {risk.turn:<4} {risk.who}: {risk.label}{again}"
            f"  ({measured(risk):+.1f})"
        )

        if risk.dangers:
            yield f"      against it: {_worst_of(risk)}"

        if risk.regret:
            yield f"      the bot would have played {risk.instead!r}"

    yield ""


def _cards(report: Review, *, width: int) -> Iterator[str]:
    cards = report.turning.cards

    yield from _heading("What did the work", width=width)

    if not cards:
        yield "  No card was named as the source of anything that moved."
        yield ""

        return

    towards = report.turning.towards_name or "the winner"

    yield f"  {'':<44}{'swing':>10}{'souls':>8}{'events':>8}"

    for card in cards[:CARDS_WORTH_NAMING]:
        yield (
            f"  {_named(report, card)[:43]:<44}"
            f"{card.swing:>10.2f}{card.souls:>8}{card.times:>8}"
        )

    yield ""
    yield f"  Swing is signed towards {towards}: a card that helped somebody"
    yield "  else scores below zero. This is what did the work in this game —"
    yield "  a card that turns up often will out-total a card that turned up"
    yield "  once and decided it, so this is not a ranking of cards."
    yield ""


def _named(report: Review, card: Contribution) -> str:
    return report.names.get(card.card) or card.name or card.card
