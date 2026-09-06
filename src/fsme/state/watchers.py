# src/fsme/state/watchers.py

"""
Abilities waiting for an event without a card to wait on.

A triggered ability belongs to a card in play: the engine finds it by looking at
the table. Some cards set up a trigger that outlives the moment they resolved —
"before a dice is rolled, choose a number; if the next roll is that number, loot
3" — and by the time the roll comes, the item is tapped and its ability long
finished. What is waiting is not the card. It is this.

A watcher is therefore kept on the game, like a promise and for the same reason,
and the difference between the two is what they do when the event arrives: a
promise edits the event, a watcher resolves an ability on the stack. Which is
exactly the difference between a replacement and a trigger.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .modifiers import Duration


@dataclass(slots=True)
class Watcher:
    """
    One ability waiting for one kind of event.

    ``controller`` is who it answers to when it resolves, and ``source`` is the
    card that set it up — a card in the discard pile is still the reason this
    is here.
    """

    event: str

    controller: int | None = None

    source: Any = None
    """
    The card that set this up, if it still exists anywhere.

    It is kept so the ability can say where it came from — targets like
    ``self`` and conditions about the source still mean the same card — not so
    that the card can do anything: by now it may be tapped, discarded or gone.
    """

    label: str = ""

    conditions: tuple[Any, ...] = ()
    effects: tuple[Any, ...] = ()

    player_id: int | None = None
    """
    Whose event this is about, when the card says whose.

    "The next time *you* would loot" is not the next time anybody would.
    """

    uses: int | None = 1
    duration: Duration = Duration.END_OF_TURN

    waits: bool = False
    """
    Whether an event that does not meet the conditions leaves this waiting.

    "If the next roll is that number" is spent by the next roll whatever it
    shows; "the next time you play a loot card that is not a trinket" waits for
    one that is not. Both are printed on cards, and the difference is only
    this.
    """

    fired: list[str] = field(default_factory=list)
    """
    Events this watcher has already answered, by identity.

    An event is offered to the watchers once, but the engine may pass the same
    event through more than one path; answering it twice would be a second
    ability nobody wrote.
    """

    def expires_at_end_of_turn(self) -> bool:
        return self.duration is Duration.END_OF_TURN

    def concerns(self, player_id: int | None) -> bool:
        return self.player_id is None or self.player_id == player_id

    def spend(self) -> bool:
        """
        Use the watcher up by one, and say whether anything is left of it.
        """
        if self.uses is None:
            return True

        self.uses -= 1

        return self.uses > 0

    def __str__(self) -> str:
        return f"{self.label or self.source} waiting for {self.event}"
