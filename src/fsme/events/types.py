# src/fsme/events/types.py

"""
Core event types for Four Souls Multiverse Engine.

Event type values are identical to the trigger names used by the Effect DSL.
This keeps TRIGGER_REGISTRY.md and the engine event vocabulary as a single
source of truth: a card that declares ``"trigger": "after_damage"`` reacts to
``EventType.AFTER_DAMAGE`` with no translation table in between.
"""

from __future__ import annotations

from enum import StrEnum


class EventType(StrEnum):
    """
    Every event the engine is able to emit.
    """

    # Game
    GAME_START = "game_start"
    GAME_END = "game_end"
    WINNER_DECLARED = "winner_declared"

    # Turn
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    TURN_CLEANUP = "turn_cleanup"
    PHASE_CHANGED = "phase_changed"

    # Card lifecycle
    ON_ENTER = "on_enter"
    ON_LEAVE = "on_leave"
    BEFORE_DESTROY = "before_destroy"
    """An item about to be destroyed, offered for replacement first."""

    ON_DESTROY = "on_destroy"
    ON_DISCARD = "on_discard"
    ON_GAIN = "on_gain"
    ON_LOSE = "on_lose"

    # Play and activation
    ON_PLAY = "on_play"
    BEFORE_ACTIVATE = "before_activate"
    ON_ACTIVATE = "on_activate"
    AFTER_ACTIVATE = "after_activate"

    # Attack
    ATTACK_START = "attack_start"
    BEFORE_ATTACK_ROLL = "before_attack_roll"
    AFTER_ATTACK_ROLL = "after_attack_roll"
    BEFORE_DAMAGE = "before_damage"
    AFTER_DAMAGE = "after_damage"
    ATTACK_END = "attack_end"
    MONSTER_KILLED = "monster_killed"
    BEFORE_DEATH = "before_death"
    """A player about to die, offered for replacement first."""

    PLAYER_DIED = "player_died"

    # Dice
    BEFORE_ROLL = "before_roll"
    AFTER_ROLL = "after_roll"
    ROLL_MODIFIED = "roll_modified"
    REROLL = "reroll"

    # Shop
    BEFORE_PURCHASE = "before_purchase"
    AFTER_PURCHASE = "after_purchase"
    TREASURE_BOUGHT = "treasure_bought"

    # Loot
    BEFORE_LOOT = "before_loot"
    BEFORE_LOOT_DRAW = "before_loot_draw"
    """Loot about to be drawn: how many, and from which pile."""

    AFTER_LOOT = "after_loot"
    LOOT_DRAWN = "loot_drawn"
    LOOT_DISCARDED = "loot_discarded"
    REVEALED = "revealed"

    # Treasure
    TREASURE_CHARGED = "treasure_charged"
    TREASURE_DEACTIVATED = "treasure_deactivated"
    TREASURE_DESTROYED = "treasure_destroyed"
    TREASURE_STOLEN = "treasure_stolen"

    # Coins
    BEFORE_COINS_GAINED = "before_coins_gained"

    # Statistics
    STAT_MODIFIED = "stat_modified"
    STAT_EXPIRED = "stat_expired"

    # Souls
    SOUL_GAINED = "soul_gained"
    SOUL_LOST = "soul_lost"

    # Stack
    STACK_PUSH = "stack_push"
    STACK_RESOLVE = "stack_resolve"
    STACK_CANCEL = "stack_cancel"

    # Economy
    COINS_GAINED = "coins_gained"
    COINS_LOST = "coins_lost"

    # Health
    DAMAGE_DEALT = "damage_dealt"
    BEFORE_HEAL = "before_heal"
    HEALED = "healed"
    PLAYER_REVIVED = "player_revived"

