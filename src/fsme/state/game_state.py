# src/fsme/state/game_state.py

"""
Root game state for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .player_state import PlayerState
from .turn_state import TurnState
from .zones import Zone, ZoneType


@dataclass(slots=True)
class GameState:
    """
    Root mutable game state.

    Stores every mutable object required to run a game.
    Does not implement game rules.
    """

    players: list[PlayerState] = field(default_factory=list)

    turn: TurnState = field(default_factory=TurnState)

    monster_deck: Zone = field(default_factory=lambda: Zone(ZoneType.DECK))
    monster_discard: Zone = field(default_factory=lambda: Zone(ZoneType.DISCARD))

    treasure_deck: Zone = field(default_factory=lambda: Zone(ZoneType.DECK))
    treasure_discard: Zone = field(default_factory=lambda: Zone(ZoneType.DISCARD))

    room_deck: Zone = field(default_factory=lambda: Zone(ZoneType.DECK))
    room_discard: Zone = field(default_factory=lambda: Zone(ZoneType.DISCARD))

    stack: list[object] = field(default_factory=list)

    seed: int = 0

    winner: int | None = None

    game_over: bool = False

    def player(self, player_id: int) -> PlayerState:
        """
        Return a player by identifier.
        """
        return self.players[player_id]

    @property
    def active_player(self) -> PlayerState:
        """
        Return the player whose turn it is.
        """
        return self.player(self.turn.active_player)

    @property
    def player_count(self) -> int:
        return len(self.players)

    def add_player(self, player: PlayerState) -> None:
        self.players.append(player)

    def living_players(self) -> list[PlayerState]:
        return [player for player in self.players if player.alive]

    def is_finished(self) -> bool:
        return self.game_over

    def finish(self, winner: int) -> None:
        self.game_over = True
        self.winner = winner

    def reset_stack(self) -> None:
        self.stack.clear()

    def push(self, item: object) -> None:
        self.stack.append(item)

    def pop(self) -> object:
        if not self.stack:
            raise IndexError("stack is empty")
        return self.stack.pop()