# src/fsme/state/priority.py

"""
Priority tracking for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PriorityState:
    """
    Who may act while something waits on the stack.

    STACK.md section 9: after every push players receive a priority window, and
    the top object resolves only once everyone has passed consecutively. Any
    response resets the count, because the players who already passed must be
    given the chance to answer the new object.
    """

    holder: int | None = None

    passes: int = 0

    is_open: bool = False

    def open_window(self, holder: int) -> None:
        """
        Give priority to a player and start counting passes.
        """
        self.holder = holder
        self.passes = 0
        self.is_open = True

    def close(self) -> None:
        """
        End the window.
        """
        self.holder = None
        self.passes = 0
        self.is_open = False

    def record_pass(self, player_count: int) -> bool:
        """
        Record a pass and report whether everyone has now passed.
        """
        if player_count <= 0:
            raise ValueError("player count must be positive")

        self.passes += 1

        if self.passes >= player_count:
            self.close()
            return True

        if self.holder is not None:
            self.holder = (self.holder + 1) % player_count

        return False

    def interrupt(self, holder: int) -> None:
        """
        Restart the count after a player responded instead of passing.
        """
        self.open_window(holder)
