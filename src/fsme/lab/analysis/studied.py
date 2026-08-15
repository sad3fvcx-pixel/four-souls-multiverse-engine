# src/fsme/lab/analysis/studied.py

"""
A study, written out for a person.

The numbers are the study's. What this adds is the wording, and the wording is
the part that decides whether the report is useful or misleading — so each
section says what its numbers are and, just as plainly, what they are not.
"""

from __future__ import annotations

from collections.abc import Iterator

from .study import SEEN_AT_LEAST, TOGETHER_AT_LEAST, Study

WIDTH = 78


def written(study: Study, *, top: int = 10, width: int = WIDTH) -> str:
    """
    Write the whole study out.
    """
    return "\n".join(_lines(study, top=top, width=width))


def _lines(study: Study, *, top: int, width: int) -> Iterator[str]:
    yield "=" * width
    yield f"FSME study — {study.games} games, {study.finished} of them finished"
    yield "=" * width
    yield ""

    if not study.games:
        yield "Nothing to study."

        return

    yield from _souls(study)
    yield from _winning(study, width=width)
    yield from _pairs(study, top=top, width=width)
    yield from _thinking(study)
    yield from _oddities(study, top=top, width=width)
    yield from _suspects(study, top=top, width=width)


def _souls(study: Study) -> Iterator[str]:
    if not study.souls_from:
        return

    yield "-" * WIDTH
    yield "Where souls came from"
    yield "-" * WIDTH
    yield ""

    total = sum(study.souls_from.values())
    won = sum(study.winning_souls_from.values())

    for kind, count in sorted(study.souls_from.items()):
        share = count / total if total else 0.0
        winners = study.winning_souls_from.get(kind, 0)
        theirs = winners / won if won else 0.0

        yield (
            f"  {kind:<14}{count:>8} ({share * 100:.0f}% of all souls)"
            f"   winners: {winners} ({theirs * 100:.0f}%)"
        )

    yield ""


def _winning(study: Study, *, width: int) -> Iterator[str]:
    yield "-" * width
    yield "What went with winning"
    yield "-" * width
    yield (
        "(winners against everybody else. These went with winning; a player who"
    )
    yield (
        " killed four monsters won partly because of it and killed the fourth"
    )
    yield " partly because they were winning. Read them as symptoms.)"
    yield ""

    if not study.splits:
        yield "  nothing to compare"
        yield ""

        return

    yield f"  {'':<20}{'winners':>10}{'others':>10}{'gap':>16}"

    for split in study.splits:
        told = (
            f"{split.gap:+.1f} ± {split.error:.1f}"
            if split.error is not None
            else f"{split.gap:+.1f}"
        )

        mark = "  *" if split.beyond_noise else ""

        yield (
            f"  {split.what:<20}{split.winners:>10.1f}{split.losers:>10.1f}"
            f"{told:>16}{mark}"
        )

    yield ""
    yield "  * bigger than twice its own uncertainty."
    yield ""


def _pairs(study: Study, *, top: int, width: int) -> Iterator[str]:
    yield "-" * width
    yield "Cards that travelled together"
    yield "-" * width
    yield (
        f"(used by the same player in the same game, at least"
        f" {TOGETHER_AT_LEAST} times."
    )
    yield " Lift is how much more often than chance would have them meet."
    yield ""
    yield " With hundreds of cards there are tens of thousands of pairs, so the"
    yield " top of this table is striking by arithmetic alone. Every row here is"
    yield " a hypothesis to test with `fsme test-card`, not a synergy.)"
    yield ""

    if not study.pairs:
        yield "  no pair met often enough to be worth printing"
        yield ""

        return

    yield f"  {'':<46}{'together':>10}{'lift':>8}{'won':>8}"

    for pair in study.pairs[:top]:
        one, other = pair.names
        together = f"{one[:21]} + {other[:21]}"

        yield (
            f"  {together:<46}{pair.together:>10}"
            f"{(pair.lift or 0):>8.1f}"
            f"{(pair.rate or 0) * 100:>7.0f}%"
        )

    yield ""


def _thinking(study: Study) -> Iterator[str]:
    thinking = study.thinking

    if not thinking.seats:
        return

    yield "-" * WIDTH
    yield "The bot"
    yield "-" * WIDTH
    yield ""

    rate = thinking.won / thinking.seats if thinking.seats else 0.0
    forced = thinking.forced / thinking.moves if thinking.moves else 0.0

    yield f"  seats played      {thinking.seats}"
    yield f"  games won         {thinking.won} ({rate * 100:.0f}%)"
    yield f"  moves made        {thinking.moves}"

    if thinking.forced:
        yield (
            f"  forced moves      {thinking.forced} ({forced * 100:.0f}%) — the"
            f" engine offered one thing"
        )

    yield ""


def _suspects(study: Study, *, top: int, width: int) -> Iterator[str]:
    """
    What to measure next, and the command that measures it.

    The point of the section: everything above it is a correlation inside one
    run, and a card test is the only thing in this package that can turn one
    into a difference. Printing the command is not a convenience — it is the
    section saying that its own numbers are not the answer.
    """
    yield "-" * width
    yield "Worth testing next"
    yield "-" * width
    yield (
        f"(cards a named rule picked out, each used by at least"
        f" {SEEN_AT_LEAST} seats."
    )
    yield " Nothing here is a finding. A card test plays the game with the card"
    yield " and without it, and that is what decides whether there is an"
    yield " effect.)"
    yield ""

    if not study.suspects:
        yield "  no card stood out far enough from the rest to be worth the run"
        yield ""

        return

    for suspect in study.suspects[:top]:
        yield f"  {suspect.name} ({suspect.card}) — {suspect.rule}"
        yield f"    {suspect.saying}"
        yield f"    $ {suspect.command}"
        yield ""

    if len(study.suspects) > top:
        yield f"  … and {len(study.suspects) - top} more"
        yield ""


def _oddities(study: Study, *, top: int, width: int) -> Iterator[str]:
    yield "-" * width
    yield "Games worth a look"
    yield "-" * width
    yield "(each flagged by a named rule; `fsme explain` the seed to see why)"
    yield ""

    if not study.oddities:
        yield "  nothing looked unusual"
        yield ""

        return

    for oddity in study.oddities[:top]:
        yield f"  seed {oddity.seed:<8} {oddity.rule:<28} {oddity.saying}"

    if len(study.oddities) > top:
        yield f"  … and {len(study.oddities) - top} more"

    yield ""
