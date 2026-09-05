# src/fsme/state/promises.py

"""
Promises: changes waiting for an event that has not happened yet.

A replacement ability lives on a card and is found when the event arrives. Some
cards make the same kind of change without staying around to make it: "the next
time a player would loot, they loot from the discard pile instead" is written on
an item that is tapped and done, and the change it promised has to outlive the
resolution that promised it.

Such a promise is therefore stored on the game, like a temporary modifier and
for the same reason: a saved game has to reload still owing it. It names the
event it is waiting for, whom it concerns, and what it changes about it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .modifiers import Duration

VALUE = "value"
"""Replace what the event carries outright."""

DELTA = "delta"
"""Add to a number the event carries."""

FACTOR = "factor"
"""Multiply a number the event carries — "they loot double that number"."""

CAP = "cap"
"""Lower a number to at most this — "reduced to 1"."""

FLOOR = "floor"
"""Raise a number to at least this."""

FLIP = "flip"
"""Read a number from the other side: the flip value less what it was."""

CHANGES = (VALUE, DELTA, FACTOR, CAP, FLOOR, FLIP)


@dataclass(slots=True)
class Promise:
    """
    One stored change to the next event of a kind.

    ``player_id`` and ``card_id`` say who the promise is about. Both left out
    means anybody: "the next time *a player* would loot" does not care which
    player it turns out to be, and the promise is spent by whoever loots first.

    ``uses`` counts down as the promise is kept. ``None`` means it keeps being
    kept until its duration runs out, which is the difference between "the next
    time" and "each time till end of turn".
    """

    event: str

    changes: dict[str, dict[str, Any]] = field(default_factory=dict)

    player_id: int | None = None
    card_id: str | None = None

    when: dict[str, Any] = field(default_factory=dict)
    """
    What the event must carry for this promise to be about it.

    "The next attack roll" and "the next roll" are different promises, and the
    only thing that tells them apart is a value the event carries.
    """

    uses: int | None = 1

    duration: Duration = Duration.END_OF_TURN

    def expires_at_end_of_turn(self) -> bool:
        return self.duration is Duration.END_OF_TURN

    def concerns(self, player_id: int | None, card_ids: frozenset[str]) -> bool:
        """
        Return whether this promise is about the thing an event is about.
        """
        if self.player_id is not None:
            return self.player_id == player_id

        if self.card_id is not None:
            return self.card_id in card_ids

        return True

    def about(self, payload: Mapping[str, Any]) -> bool:
        """
        Return whether an event is the kind this promise was made about.
        """
        return all(payload.get(key) == value for key, value in self.when.items())

    def spend(self) -> bool:
        """
        Use the promise up by one, and say whether anything is left of it.
        """
        if self.uses is None:
            return True

        self.uses -= 1

        return self.uses > 0

    def apply_to(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """
        Return what the event carries once this promise has had its say.
        """
        changed: dict[str, Any] = {}

        for key, change in self.changes.items():
            current = payload.get(key)

            if VALUE in change:
                changed[key] = change[VALUE]
                continue

            number = int(current) if isinstance(current, int) else 0

            if DELTA in change:
                number += int(change[DELTA])

            if FACTOR in change:
                number *= int(change[FACTOR])

            if CAP in change:
                number = min(number, int(change[CAP]))

            if FLOOR in change:
                number = max(number, int(change[FLOOR]))

            if FLIP in change:
                number = int(change[FLIP]) - number

            changed[key] = number

        return changed

    def __str__(self) -> str:
        about = (
            f"player {self.player_id}"
            if self.player_id is not None
            else self.card_id or "anybody"
        )

        return f"{self.event} for {about}: {self.changes}"
