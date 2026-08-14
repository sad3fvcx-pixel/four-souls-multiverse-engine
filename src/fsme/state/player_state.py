# src/fsme/state/player_state.py

"""
Player state for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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

    loot_limit_lifted: bool = False
    """
    Whether this player may play as much loot as they like this turn.

    "You may play any number of additional loot cards till end of turn" is not
    a bigger allowance; it is no allowance at all, and a number cannot say that.
    """

    loot_played: int = 0
    """
    Loot cards this player has played during the current turn.

    Counted per player rather than per turn: a player who answers somebody
    else's card has spent their own allowance, not the turn's.
    """

    alive: bool = True

    died_this_turn: bool = False
    """
    Whether this player has already died this turn.

    A player dies once per turn, and one who is standing at no hit points
    because they already died is not killed again by the same nothing.
    """

    hp_before_lethal: int = 0
    """
    The hit points this player had before the blow that would kill them.

    COMPREHENSIVE_RULES.md §10: a prevented death gives back the health the
    player had before the lethal damage or effect, so the number has to be kept
    from the moment it is about to be lost.
    """

    character: Any | None = None
    """
    The character card this player is playing.

    Hit points, the starting item and any printed ability come from it, so a
    player without one is a player the rules cannot fully describe.
    """

    hand: Zone[Any] = field(default_factory=lambda: Zone(ZoneType.HAND))
    treasures: Zone[Any] = field(default_factory=lambda: Zone(ZoneType.TREASURE))
    souls: Zone[Any] = field(default_factory=lambda: Zone(ZoneType.SOUL))

    curses: Zone[Any] = field(default_factory=lambda: Zone(ZoneType.CURSE))
    """
    Curses attached to this player.

    A curse is in play the way an item is: its abilities answer events and its
    statics count, but it belongs to the player it afflicts rather than to
    whoever played it.
    """

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
        self.loot_played = 0
        self.loot_limit_lifted = False

    @property
    def soul_count(self) -> int:
        return len(self.souls)

    @property
    def hand_size(self) -> int:
        return len(self.hand)

    @property
    def treasure_count(self) -> int:
        return len(self.treasures)

    @property
    def curse_count(self) -> int:
        return len(self.curses)

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