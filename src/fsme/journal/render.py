# src/fsme/journal/render.py

"""
A journal, read out loud.

The file is for machines: every event, every payload, every fingerprint. This
is the same journal for a person — turns as headings, one block per decision,
and the events underneath the choice that caused them.

Nothing is summarised away that would change the account. Where a roll is
mentioned it is the roll the game made, and where a card is named it is the
name the engine used, because the point of reading a journal is to be able to
say why a game went the way it did — and a retelling that smooths anything is
worse than no retelling at all.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from .entry import Entry, Happening, Journal

QUIET = frozenset(
    {
        "stack_push",
        "stack_resolve",
        "priority_passed",
        "priority_opened",
        "phase_changed",
    }
)
"""
Events that are the engine keeping house rather than the game happening.

They are in the file, and they are not in the reading: a page of stack pushes
buries the roll that decided the fight. ``full`` puts them back.
"""


def render(journal: Journal, *, full: bool = False, width: int = 78) -> str:
    """
    Write the whole journal out as text.
    """
    return "\n".join(_lines(journal, full=full, width=width))


def _lines(journal: Journal, *, full: bool, width: int) -> Iterator[str]:
    yield "=" * width
    yield f"FSME journal — seed {journal.seed}"
    yield "=" * width
    yield ""

    for seat, name in enumerate(journal.players):
        character = (
            journal.characters[seat] if seat < len(journal.characters) else ""
        )

        yield f"  {name}" + (f" as {character}" if character else "")

    if journal.engine_version or journal.content_version:
        yield ""
        yield f"  engine {journal.engine_version or '?'}" + (
            f", content {journal.content_version}" if journal.content_version else ""
        )

    yield ""

    turn = None

    for entry in journal.entries:
        if entry.before.turn != turn:
            turn = entry.before.turn

            yield "-" * width
            yield f"Turn {turn}"
            yield "-" * width
            yield ""

        yield from _entry(entry, journal, full=full)

    yield from _ending(journal, width=width)


def _entry(entry: Entry, journal: Journal, *, full: bool) -> Iterator[str]:
    who = _name(journal, entry.player)

    yield f"[{entry.index}] {who} — {entry.before.phase} phase"

    if entry.before.waiting_kind == "decision":
        yield f"    the game was asking {_name(journal, entry.before.waiting_player)}"

    if entry.before.stack:
        yield "    queue: " + " / ".join(reversed(entry.before.stack))

    if entry.offered:
        yield ""
        yield "    could have:"

        for move in entry.offered:
            yield f"      - {move}"

    yield ""
    yield f"    did: {entry.label or _spell(entry)}"

    yield from _working(entry)

    happenings = [
        event
        for event in entry.events
        if full or event.type not in QUIET
    ]

    if happenings:
        yield ""
        yield "    then:"

        for event in happenings:
            yield f"      {_read(event, journal)}"

    yield ""


def _working(entry: Entry) -> Iterator[str]:
    """
    Say what a bot was thinking, when a bot was thinking.

    The chosen move first with its own arithmetic, then what it was chosen
    over. A reader disagreeing with the choice can see which number to argue
    with, which is the only thing a decision log is for.
    """
    decision = entry.decision

    if not decision:
        return

    chosen = decision.get("chosen") or {}
    reasons = chosen.get("reasons") or []

    yield ""
    yield f"    {decision.get('by', 'a bot')} scored it {_score(chosen)}:"

    for reason in reasons:
        worth = _amount(reason.get("worth"))
        value = reason.get("value")

        yield (
            f"      {reason.get('what', '')}"
            + (f" — {value:g}" if isinstance(value, (int, float)) else "")
            + (f"  {worth:+.1f}" if worth else "")
        )

    others = [
        other
        for other in (decision.get("considered") or [])
        if other.get("move") != chosen.get("move")
    ]

    if others:
        yield ""
        yield "    over:"

        for other in sorted(others, key=lambda item: -_amount(item.get("score")))[:4]:
            yield f"      {_score(other)}  {other.get('move', '')}"

    for note in decision.get("notes") or ():
        yield f"      ({note})"


def _score(evaluation: Mapping[str, Any]) -> str:
    return f"{_amount(evaluation.get('score')):+.1f}"


def _amount(value: Any) -> float:
    """
    Read a number out of a journal, which holds whatever was written into it.
    """
    return float(value) if isinstance(value, (int, float)) else 0.0


def _spell(entry: Entry) -> str:
    """
    Say a command in words when nobody labelled it.
    """
    said = entry.command.replace("_", " ")

    detail = ", ".join(
        f"{key} {value}" for key, value in sorted(entry.payload.items())
    )

    return f"{said} ({detail})" if detail else said


def _read(event: Happening, journal: Journal) -> str:
    """
    Say one event in words.
    """
    said = event.type.replace("_", " ")

    parts: list[str] = []

    if event.source:
        parts.append(str(event.source))

    if event.targets:
        parts.append("→ " + ", ".join(event.targets))

    for key, value in event.payload.items():
        if value in (None, "", False):
            continue

        parts.append(f"{key} {value}")

    return f"{said}" + (f": {' · '.join(parts)}" if parts else "")


def _ending(journal: Journal, *, width: int) -> Iterator[str]:
    yield "=" * width

    if not journal.outcome:
        yield f"Unfinished after {len(journal)} commands."
        yield "=" * width

        return

    winner = journal.outcome.get("winner_name") or "nobody"

    yield (
        f"{winner} won on turn {journal.outcome.get('turns', '?')} "
        f"after {journal.outcome.get('commands', len(journal))} commands."
    )

    souls = journal.outcome.get("souls")

    if isinstance(souls, Sequence):
        yield "Souls: " + ", ".join(
            f"{_name(journal, seat)} {count}" for seat, count in enumerate(souls)
        )

    yield "=" * width


def _name(journal: Journal, seat: int | None) -> str:
    if seat is None or not 0 <= seat < len(journal.players):
        return "nobody"

    return journal.players[seat]
