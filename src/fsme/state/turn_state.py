# src/fsme/state/turn_state.py

"""
Turn state for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass

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

    def record_loot_play(self) -> None:
        self.loot_played += 1

    def record_attack(self) -> None:
        self.attacks_declared += 1

    @property
    def is_action_phase(self) -> bool:
        return self.phase is GamePhase.ACTION

    @property
    def is_finished(self) -> bool:
        return self.phase is GamePhase.END