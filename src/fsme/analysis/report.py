# src/fsme/analysis/report.py

"""
A tally, written out for a person.

The numbers are the tally's; the only judgement here is which of them to show
and how to name them. Two of those names matter.

A card's "won" column is how often the player holding it went on to win. It is
not the card's doing — a card played mostly by whoever is already winning will
top this table and mean nothing — and the heading says so, because a table that
implies more than it knows is worse than no table.

A run of a few dozen games says almost nothing about any one card; the counts
are printed so that a reader can see how thin the evidence is rather than
having to guess.
"""

from __future__ import annotations

from collections.abc import Iterator

from .tally import Seen, Tally, by_games, by_times

WIDTH = 78


def report(tally: Tally, *, top: int = 15, width: int = WIDTH) -> str:
    """
    Write the whole tally out as text.
    """
    return "\n".join(_lines(tally, top=top, width=width))


def _lines(tally: Tally, *, top: int, width: int) -> Iterator[str]:
    yield "=" * width
    yield f"FSME — {tally.games} games"
    yield "=" * width
    yield ""

    if not tally.games:
        yield "Nothing was played."

        return

    yield f"  finished          {tally.finished} of {tally.games}"
    yield f"  average turns     {_number(tally.average_turns())}"
    yield f"  average commands  {_number(tally.average_commands())}"
    yield f"  player deaths     {tally.deaths} ({_number(tally.deaths / tally.games)} a game)"
    yield f"  attack rolls      {tally.attack_rolls}, {_percent(tally.hit_rate())} hit"

    if tally.wins_by_seat:
        yield ""
        yield "  wins by seat      " + ", ".join(
            f"seat {seat} {count}" for seat, count in sorted(tally.wins_by_seat.items())
        )

    yield ""

    yield from _table(
        "Characters",
        [seen for _, seen in by_games(tally.characters)][:top],
        columns=("games", "won", "winrate", "avg turns"),
        row=lambda seen: (
            str(seen.games),
            str(seen.wins),
            _percent(seen.rate()),
            _number(seen.average_turns()),
        ),
        width=width,
    )

    yield from _table(
        "Cards — played, and how often the player holding one won",
        [seen for _, seen in by_times(tally.cards)][:top],
        columns=("games", "times", "won", "won %"),
        row=lambda seen: (
            str(seen.games),
            str(seen.times),
            str(seen.wins),
            _percent(seen.rate()),
        ),
        width=width,
        note=(
            "how often the player who used it went on to win — a correlation, "
            "not the card's doing"
        ),
    )

    yield from _table(
        "Monsters",
        [seen for _, seen in by_games(tally.monsters)][:top],
        columns=("games", "seen", "beaten", "turns alive"),
        row=lambda seen: (
            str(seen.games),
            str(seen.times),
            str(seen.wins),
            _number(seen.average_turns()),
        ),
        width=width,
    )

    yield "-" * width
    yield "Events"
    yield "-" * width
    yield ""

    for kind, count in sorted(
        tally.events.items(), key=lambda item: (-item[1], item[0])
    )[:top]:
        yield f"  {kind:<32} {count:>10}"

    yield ""


def _table(
    title: str,
    rows: list[Seen],
    *,
    columns: tuple[str, ...],
    row: object,
    width: int,
    note: str = "",
) -> Iterator[str]:
    yield "-" * width
    yield title
    yield "-" * width

    if note:
        yield f"({note})"

    yield ""

    if not rows:
        yield "  nothing to count"
        yield ""

        return

    heading = f"  {'':<32}" + "".join(f"{name:>12}" for name in columns)

    yield heading

    for seen in rows:
        cells = row(seen)  # type: ignore[operator]

        yield f"  {seen.name[:31]:<32}" + "".join(f"{cell:>12}" for cell in cells)

    yield ""


def _number(value: float | None) -> str:
    return "—" if value is None else f"{value:.1f}"


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"
