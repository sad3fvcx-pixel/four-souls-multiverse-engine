# src/fsme/state/player_state.py

"""
Player state for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .zones import Zone, ZoneType


@dataclass(slots=True)
class PlayerState:
    """
    Mutable state belonging to a single player.

    This class stores data only.
    Game logic belongs to the engine.
    """

    player_id: int
    name: str

    hp: int = 2
    max_hp: int = 2
    pennies: int = 0

    attacks_left: int = 1
    additional_loot_plays: int = 0

    alive: bool = True

    hand: Zone = field(default_factory=lambda: Zone(ZoneType.HAND))
    treasures: Zone = field(default_factory=lambda: Zone(ZoneType.TREASURE))
    souls: Zone = field(default_factory=lambda: Zone(ZoneType.SOUL))

    def can_attack(self) -> bool:
        return self.alive and self.attacks_left > 0

    def spend_attack(self) -> None:
        if self.attacks_left <= 0:
            raise ValueError("player has no attacks remaining")
        self.attacks_left -= 1

    def reset_turn(self) -> None:
        """
        Restore values refreshed at the beginning of a turn.
        """
        self.attacks_left = 1
        self.additional_loot_plays = 0

    @property
    def soul_count(self) -> int:
        return len(self.souls)

    @property
    def hand_size(self) -> int:
        return len(self.hand)

    @property
    def treasure_count(self) -> int:
        return len(self.treasures)

    def heal(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("heal amount must be non-negative")
        self.hp = min(self.max_hp, self.hp + amount)

    def damage(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("damage amount must be non-negative")
        self.hp = max(0, self.hp - amount)

    def kill(self) -> None:
        self.hp = 0
        self.alive = False

    def revive(self, hp: int = 1) -> None:
        if hp <= 0:
            raise ValueError("revive hp must be positive")
        self.hp = min(hp, self.max_hp)
        self.alive = True