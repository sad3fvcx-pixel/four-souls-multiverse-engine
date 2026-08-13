# src/fsme/state/game_state.py

"""
Root game state for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fsme.events import EventQueue
from fsme.stack import Stack
from fsme.util.ids import IdSequence

from .combat_state import CombatState
from .decision import PendingDecision
from .modifiers import DamageShield, TemporaryModifier
from .player_state import PlayerState
from .priority import PriorityState
from .roll import PendingRoll
from .turn_state import TurnState
from .zones import Zone, ZoneType


@dataclass(slots=True)
class GameState:
    """
    Root mutable game state.

    Stores every mutable object required to run a game and implements no game
    rules. GAME_STATE.md requires the whole game to be reconstructible from a
    single instance, which is why the stack, the event queue and the identifier
    allocator live here rather than inside the Runtime: they must survive
    save/load and replay exactly as they were.

    Only the Runtime may mutate this object during gameplay.
    """

    players: list[PlayerState] = field(default_factory=list)

    turn: TurnState = field(default_factory=TurnState)

    loot_deck: Zone[Any] = field(default_factory=lambda: Zone(ZoneType.DECK))
    loot_discard: Zone[Any] = field(default_factory=lambda: Zone(ZoneType.DISCARD))

    monster_deck: Zone[Any] = field(default_factory=lambda: Zone(ZoneType.DECK))
    monster_discard: Zone[Any] = field(default_factory=lambda: Zone(ZoneType.DISCARD))
    active_monsters: Zone[Any] = field(default_factory=lambda: Zone(ZoneType.MONSTER))

    treasure_deck: Zone[Any] = field(default_factory=lambda: Zone(ZoneType.DECK))
    treasure_discard: Zone[Any] = field(default_factory=lambda: Zone(ZoneType.DISCARD))
    treasure_shop: Zone[Any] = field(default_factory=lambda: Zone(ZoneType.SHOP))

    bonus_souls: Zone[Any] = field(default_factory=lambda: Zone(ZoneType.SOUL))
    """
    Souls sitting on the table, waiting for whoever earns them first.
    """

    room_deck: Zone[Any] = field(default_factory=lambda: Zone(ZoneType.DECK))
    room_discard: Zone[Any] = field(default_factory=lambda: Zone(ZoneType.DISCARD))
    room_area: Zone[Any] = field(default_factory=lambda: Zone(ZoneType.ROOM))

    stack: Stack = field(default_factory=Stack)
    events: EventQueue = field(default_factory=EventQueue)

    priority: PriorityState = field(default_factory=PriorityState)
    combat: CombatState = field(default_factory=CombatState)

    shields: list[DamageShield] = field(default_factory=list)
    """
    Damage waiting to be prevented, in the order it was promised.
    """

    modifiers: list[TemporaryModifier] = field(default_factory=list)
    """
    Bonuses that outlive the card that granted them.

    A card in play carries its own static modifiers and needs no record here;
    "till end of turn" has nowhere else to live.
    """

    pending_decision: PendingDecision | None = None

    pending_roll: PendingRoll | None = None
    """
    A roll that has landed and is waiting to be answered.
    """

    ids: IdSequence = field(default_factory=IdSequence)

    seed: int = 0
    rng_state: Any = None

    souls_to_win: int = 4

    monster_slots: int = 2
    shop_slots: int = 2
    """
    How many monsters and shop items are face up.

    Cards expand both, so the number belongs to the game rather than to the
    rules: a constant cannot be changed mid-game and a game that was expanded
    has to reload expanded.
    """

    skipped_players: list[int] = field(default_factory=list)
    """
    Players whose next turn is taken away from them.
    """

    started: bool = False
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

    def next_player(self, after: int) -> int:
        """
        Return the seat that acts after the given one, skipping the dead.
        """
        if not self.players:
            raise IndexError("game has no players")

        for step in range(1, len(self.players) + 1):
            candidate = (after + step) % len(self.players)

            if self.players[candidate].alive:
                return candidate

        return after

    def is_stable(self) -> bool:
        """
        Return True when no gameplay work is pending.

        ENGINE_EXECUTION_MODEL.md allows a new command only in this condition,
        and it names a pending player decision as one of the things that must
        be settled first.
        """
        return (
            self.events.is_empty()
            and self.stack.is_empty()
            and self.pending_decision is None
        )
