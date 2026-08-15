# src/fsme/analysis/explain.py

"""
Why this game went the way it did.

One game, told as an account rather than a table: who won, what their souls
were made of, and what they did more of than the players who did not win.

The last part is the only place judgement enters, and it is kept as small as
possible. It compares the winner with the other seats *in that game* and names
what they did differently. That is a description of one game and is offered as
one — a single game can be won by the player who did nothing at all while a die
did the work, and the account says so when the numbers say so.

Nothing here is a cause. What separated the winner from the table went with
winning, and in one game it may have gone with it by luck.
"""

from __future__ import annotations

from collections.abc import Iterator

from .study import MEASURES
from .summary import GameSummary, SeatFacts

WIDTH = 78

SOUL_WORDS = {
    "monster": "from monsters",
    "card": "from cards",
    "unnamed": "from effects that named no card",
}


def explain(summary: GameSummary, *, width: int = WIDTH) -> str:
    """
    Write one game out as an account of it.
    """
    return "\n".join(_lines(summary, width=width))


def _lines(summary: GameSummary, *, width: int) -> Iterator[str]:
    yield "=" * width
    yield f"Game {summary.seed} — {summary.players} players, {summary.turns} turns"
    yield "=" * width
    yield ""

    winner = summary.winning_seat

    if winner is None:
        yield f"  Nobody won: {summary.commands} commands and no fourth soul."
        yield ""

        yield from _table(summary, width=width)

        return

    yield f"  {winner.name} won as {winner.character or 'nobody in particular'}."
    yield ""

    if winner.souls_from:
        yield "  Their souls:"

        for kind, count in sorted(winner.souls_from.items()):
            yield f"    {count} {SOUL_WORDS.get(kind, kind)}"

        yield ""

    yield from _what_they_did_differently(summary, winner)
    yield from _table(summary, width=width)


def _what_they_did_differently(
    summary: GameSummary, winner: SeatFacts
) -> Iterator[str]:
    """
    Name what the winner did more or less of than the rest of the table.
    """
    others = [seat for seat in summary.seats if seat.seat != winner.seat]

    if not others:
        return

    said: list[str] = []

    for what, measure in MEASURES:
        mine = measure(winner)
        theirs = sum(measure(seat) for seat in others) / len(others)

        if theirs == 0 and mine == 0:
            continue

        gap = mine - theirs

        # A tenth of the table's own figure, or a whole unit, whichever is
        # larger: a difference smaller than that is not worth a sentence.
        if abs(gap) < max(1.0, theirs * 0.1):
            continue

        said.append(
            f"    {what}: {mine:.0f} against the table's {theirs:.1f}"
            f" ({gap:+.1f})"
        )

    if not said:
        yield "  They did nothing the rest of the table did not do."
        yield "  In one game that happens, and it means the dice decided it."
        yield ""

        return

    yield "  What went with winning here:"

    yield from said

    yield ""
    yield "  (in one game, what went with winning may simply have gone with it)"
    yield ""


def _table(summary: GameSummary, *, width: int) -> Iterator[str]:
    yield "-" * width
    yield (
        f"  {'':<14}{'souls':>7}{'kills':>7}{'attacks':>9}"
        f"{'died':>7}{'coins':>7}{'bought':>8}{'moves':>7}"
    )
    yield "-" * width

    for seat in summary.seats:
        mark = "*" if seat.won else " "

        yield (
            f"{mark} {seat.name[:13]:<14}"
            f"{seat.souls:>7}{seat.kills:>7}{seat.attacks:>9}"
            f"{seat.deaths:>7}{seat.coins_gained:>7}"
            f"{seat.purchases:>8}{seat.moves:>7}"
        )

    yield "-" * width
    yield ""
