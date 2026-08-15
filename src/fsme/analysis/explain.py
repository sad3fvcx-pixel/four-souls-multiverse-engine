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

from .moments import Turning
from .risk import Risks, Risky
from .study import MEASURES
from .summary import GameSummary, SeatFacts

WIDTH = 78

SOUL_WORDS = {
    "monster": "from monsters",
    "card": "from cards",
    "unnamed": "from effects that named no card",
}


def explain(
    summary: GameSummary,
    *,
    width: int = WIDTH,
    turning: Turning | None = None,
    dangers: Risks | None = None,
) -> str:
    """
    Write one game out as an account of it.

    ``turning`` adds where the game was decided, and ``dangers`` what a bot
    made of the decisions along the way. Both are optional because both cost
    something the plain account does not — the first a pass over the events,
    the second a whole replay — and a reader who only wants the result should
    not pay for either.
    """
    return "\n".join(
        _lines(summary, width=width, turning=turning, dangers=dangers)
    )


def _lines(
    summary: GameSummary,
    *,
    width: int,
    turning: Turning | None,
    dangers: Risks | None,
) -> Iterator[str]:
    yield "=" * width
    yield f"Game {summary.seed} — {summary.players} players, {summary.turns} turns"
    yield "=" * width
    yield ""

    winner = summary.winning_seat

    if winner is None:
        yield f"  Nobody won: {summary.commands} commands and no fourth soul."
        yield ""

        yield from _table(summary, width=width)
        yield from _turning(turning, width=width)
        yield from _dangers(dangers, width=width)

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
    yield from _turning(turning, width=width)
    yield from _dangers(dangers, width=width)


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


def _turning(turning: Turning | None, *, width: int) -> Iterator[str]:
    """
    Where the game turned: the few moves that moved the scoreboard furthest.
    """
    if turning is None:
        return

    yield "-" * width
    yield "Where it turned"
    yield "-" * width

    if turning.towards is None or not turning.moments:
        yield "  Nothing in this game moved the scoreboard."
        yield ""

        return

    if turning.won:
        yield (
            f"  The {len(turning.moments)} moves that moved"
            f" {turning.towards_name}'s lead furthest, out of"
            f" {turning.weighed} that moved anything at all"
            f" ({turning.moves} moves in the game)."
        )
    else:
        yield (
            f"  Nobody won, so this is measured towards"
            f" {turning.towards_name}, who came closest."
        )

    yield ""

    for place, moment in enumerate(turning.moments, start=1):
        yield (
            f"  {place}. turn {moment.turn}, {moment.phase or 'no phase'}"
            f" — {moment.who}: {moment.label}"
        )
        yield f"     swing {moment.swing:+.2f}"

        for word in moment.said:
            yield f"     {word}"

        for seat, ledger in sorted(moment.ledgers.items()):
            if ledger.empty:
                continue

            counted = ", ".join(
                part
                for part in (
                    f"{ledger.souls:+d} souls" if ledger.souls else "",
                    f"{ledger.coins:+d}¢" if ledger.coins else "",
                    f"{ledger.hp:+d} hp" if ledger.hp else "",
                    f"died {ledger.deaths}×" if ledger.deaths else "",
                )
                if part
            )

            yield f"     seat {seat}: {counted}"

        if moment.chance is not None:
            yield (
                f"     the first roll had a {moment.chance * 100:.0f}% chance"
                f" of landing"
            )

        if moment.decided_by_dice:
            faces = ", ".join(str(face) for face in moment.dice)

            yield f"     the dice decided this one ({faces})"

        yield ""

    yield "  (this is where the game went, not proof it had to go there:"
    yield "   no other line of play was tried.)"
    yield ""


def _dangers(dangers: Risks | None, *, width: int) -> Iterator[str]:
    """
    What a bot made of the decisions, with the bot named.
    """
    if dangers is None:
        return

    yield "-" * width
    yield "The decisions"
    yield "-" * width
    yield (
        f"  Judged by {dangers.by}, a bot that looks one move ahead. A gap"
        f" below is"
    )
    yield "  a disagreement with a readable opinion, not a proven mistake."
    yield ""

    if not dangers.faithful:
        yield "  The replay diverged from the journal: the engine has changed"
        yield "  under this game, and nothing below is about it."
        yield ""

        return

    yield (
        f"  {dangers.weighed} moves weighed, {dangers.forced} of them forced,"
        f" {dangers.skipped} skipped"
    )

    if dangers.bot_seats:
        seats = ", ".join(str(seat) for seat in dangers.bot_seats)

        yield (
            f"  seats {seats} were played by a bot, so their gaps are zero by"
            f" construction"
        )

    yield ""

    yield "  Riskiest — the moves carrying the most against them:"
    yield ""

    yield from _risky(dangers.riskiest, nothing="nothing was risky")

    yield "  Most disagreed with — what the bot would have done instead:"
    yield ""

    yield from _risky(dangers.worst, nothing="it would have played the same")


def _risky(risks: list[Risky], *, nothing: str) -> Iterator[str]:
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

        yield f"    turn {risk.turn} — {risk.who}: {risk.label}{again}"

        for danger in risk.dangers:
            yield f"      {danger.what} ({danger.value:g}) {danger.worth:+.1f}"

        if risk.regret > 0:
            yield (
                f"      {risk.regret:+.1f} against playing"
                f" {risk.instead!r}, of {risk.considered} on offer"
            )

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
