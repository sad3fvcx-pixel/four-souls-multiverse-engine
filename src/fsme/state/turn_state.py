# src/fsme/state/turn_state.py

"""
Turn state for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .obligations import Obligation
from .phase import GamePhase


@dataclass(slots=True)
class TurnState:
    """
    Stores information about the current turn.

    This object contains only mutable turn-related data.
    """

    turn_number: int = 1
    active_player: int = 0
    priority_player: int = 0

    phase: GamePhase = GamePhase.START

    stack_depth: int = 0

    loot_played: int = 0
    attacks_declared: int = 0

    extra_turn_for: int | None = None
    """
    Who takes another turn when this one ends.

    A card that grants an extra turn resolves long before the turn is over, so
    the promise has to wait somewhere until the turn actually ends.
    """

    obligations: list[Obligation] = field(default_factory=list)
    """
    What the players still owe this turn, in the order it was owed.

    "Must attack that monster this turn if able" is a debt the turn cannot end
    while it can still be paid, and it lasts exactly one turn.
    """

    triggers_fired: dict[str, int] = field(default_factory=dict)
    """
    How often each ability has answered its trigger this turn.

    A card that says "the first time you take damage each turn" or "every other
    time this takes damage each turn" is counting occurrences within a turn, and
    nothing else in the game keeps that count. It is cleared when a turn ends,
    which is the whole of what "each turn" means.
    """

    monster_died: bool = False
    """
    Whether a monster has died during this turn.

    COMPREHENSIVE_RULES.md §12: the room may be changed at the end of a turn in
    which a monster died, so the turn has to remember that it happened — by the
    end phase the monster is long gone from the table.
    """

    attack_rolls: int = 0
    """
    Attack rolls made this turn, counted as they are made.

    A card that says "for your first attack roll each turn" needs to know which
    roll it is looking at, and the roll itself is the only place that knows.
    """

    def next_phase(self) -> None:
        """
        Advance to the next phase.
        """
        match self.phase:
            case GamePhase.START:
                self.phase = GamePhase.LOOT

            case GamePhase.LOOT:
                self.phase = GamePhase.ACTION

            case GamePhase.ACTION:
                self.phase = GamePhase.END

            case GamePhase.END:
                raise RuntimeError("turn is already in END phase")

    def reset_for_new_turn(self, active_player: int) -> None:
        """
        Prepare state for a new turn.
        """
        self.turn_number += 1
        self.active_player = active_player
        self.priority_player = active_player

        self.phase = GamePhase.START

        self.stack_depth = 0
        self.loot_played = 0
        self.attacks_declared = 0
        self.attack_rolls = 0
        self.monster_died = False

        self.triggers_fired.clear()
        self.obligations.clear()

    def record_loot_play(self) -> None:
        self.loot_played += 1

    def record_attack(self) -> None:
        self.attacks_declared += 1

    def record_attack_roll(self) -> None:
        self.attack_rolls += 1

    @property
    def is_action_phase(self) -> bool:
        return self.phase is GamePhase.ACTION

    @property
    def is_finished(self) -> bool:
        return self.phase is GamePhase.END