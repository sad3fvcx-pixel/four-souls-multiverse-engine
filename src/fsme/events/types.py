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
    DAMAGE_PREVENTED = "damage_prevented"
    """Damage that was promised away, and did not land."""

    AFTER_DAMAGE = "after_damage"
    ATTACK_END = "attack_end"

    ATTACK_FIZZLED = "attack_fizzled"
    """
    A declared attack that found nothing to fight.

    COMPREHENSIVE_RULES.md §12: the monster is no longer active. The attack
    does not begin and is not spent.
    """
    MONSTER_KILLED = "monster_killed"

    BEFORE_REWARDS = "before_rewards"
    """
    What a defeated monster is about to pay, offered for replacement first.

    A card that doubles a monster's rewards is editing this, not paying a
    second reward of its own.
    """
    BEFORE_DEATH = "before_death"
    """A player about to die, offered for replacement first."""

    PLAYER_DIED = "player_died"
    BEFORE_DEATH_PENALTY = "before_death_penalty"
    """A death about to be paid for, which cards answer before it is."""

    DEATH_PENALTY = "death_penalty"
    """The penalty itself, resolving."""

    DEATH_PENALTY_PAID = "death_penalty_paid"
    """The penalty, once it has been paid."""


    # Dice
    BEFORE_ROLL = "before_roll"
    AFTER_ROLL = "after_roll"
    ROLL_MODIFIED = "roll_modified"
    REROLL = "reroll"

    # Shop
    BEFORE_PURCHASE = "before_purchase"
    AFTER_PURCHASE = "after_purchase"
    TREASURE_BOUGHT = "treasure_bought"

    PURCHASE_FIZZLED = "purchase_fizzled"
    """
    A declared purchase that found nothing to buy.

    COMPREHENSIVE_RULES.md §12: the item left its slot, or the money went. The
    purchase does not happen and is not spent.
    """

    # Loot
    BEFORE_LOOT = "before_loot"
    BEFORE_LOOT_DRAW = "before_loot_draw"
    """Loot about to be drawn: how many, and from which pile."""

    AFTER_LOOT = "after_loot"
    LOOT_DRAWN = "loot_drawn"

    DECK_REBUILT = "deck_rebuilt"
    """
    A deck ran out and was rebuilt from its discard pile.

    Announced because it is a thing that happened to the game rather than
    bookkeeping: the order of a deck is most of what a player is guessing at,
    and the moment it is reshuffled is the moment every guess is void.
    """
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



WHEN_IT_HAPPENS: dict[EventType, str] = {
    EventType.GAME_START: "the game begins",
    EventType.GAME_END: "the game ends",
    EventType.WINNER_DECLARED: "somebody wins",
    EventType.TURN_START: "a turn begins",
    EventType.TURN_END: "a turn ends",
    EventType.TURN_CLEANUP: "a turn is tidied away",
    EventType.PHASE_CHANGED: "a turn moves on",
    EventType.ON_ENTER: "this card comes into play",
    EventType.ON_LEAVE: "this card leaves play",
    EventType.BEFORE_DESTROY: "an item is about to be destroyed",
    EventType.ON_DESTROY: "this card is destroyed",
    EventType.ON_DISCARD: "a card is discarded",
    EventType.ON_GAIN: "a card is gained",
    EventType.ON_LOSE: "a card is lost",
    EventType.ON_PLAY: "this card is played",
    EventType.BEFORE_ACTIVATE: "an item is about to be used",
    EventType.ON_ACTIVATE: "somebody uses this item",
    EventType.AFTER_ACTIVATE: "an item has been used",
    EventType.ATTACK_START: "an attack begins",
    EventType.BEFORE_ATTACK_ROLL: "an attack roll is about to be made",
    EventType.AFTER_ATTACK_ROLL: "an attack roll has been made",
    EventType.BEFORE_DAMAGE: "damage is about to be dealt",
    EventType.DAMAGE_PREVENTED: "damage is stopped",
    EventType.AFTER_DAMAGE: "damage has finished being dealt",
    EventType.ATTACK_END: "an attack finishes",
    EventType.ATTACK_FIZZLED: "an attack comes to nothing",
    EventType.MONSTER_KILLED: "a monster dies",
    EventType.BEFORE_REWARDS: "rewards are about to be paid",
    EventType.BEFORE_DEATH: "somebody is about to die",
    EventType.PLAYER_DIED: "a player dies",
    EventType.BEFORE_DEATH_PENALTY: "a death penalty is about to be paid",
    EventType.DEATH_PENALTY: "a death penalty is set",
    EventType.DEATH_PENALTY_PAID: "a death penalty is paid",
    EventType.BEFORE_ROLL: "a die is about to be rolled",
    EventType.AFTER_ROLL: "somebody rolls a die",
    EventType.ROLL_MODIFIED: "a roll is changed",
    EventType.REROLL: "a die is rolled again",
    EventType.BEFORE_PURCHASE: "somebody is about to buy",
    EventType.AFTER_PURCHASE: "a purchase is finished",
    EventType.TREASURE_BOUGHT: "an item is bought",
    EventType.PURCHASE_FIZZLED: "a purchase comes to nothing",
    EventType.BEFORE_LOOT: "the loot step is about to happen",
    EventType.BEFORE_LOOT_DRAW: "a loot card is about to be drawn",
    EventType.AFTER_LOOT: "the loot step is over",
    EventType.LOOT_DRAWN: "a loot card is drawn",
    EventType.DECK_REBUILT: "a deck runs out and is shuffled again",
    EventType.LOOT_DISCARDED: "a loot card is discarded",
    EventType.REVEALED: "a card is shown to everybody",
    EventType.TREASURE_CHARGED: "an item is made ready again",
    EventType.TREASURE_DEACTIVATED: "an item is used up",
    EventType.TREASURE_DESTROYED: "an item is destroyed",
    EventType.TREASURE_STOLEN: "an item is stolen",
    EventType.BEFORE_COINS_GAINED: "cents are about to be gained",
    EventType.STAT_MODIFIED: "one of a player's numbers changes",
    EventType.STAT_EXPIRED: "a temporary bonus runs out",
    EventType.SOUL_GAINED: "somebody gains a soul",
    EventType.SOUL_LOST: "somebody loses a soul",
    EventType.STACK_PUSH: "something is put on the stack",
    EventType.STACK_RESOLVE: "something on the stack resolves",
    EventType.STACK_CANCEL: "something on the stack is cancelled",
    EventType.COINS_GAINED: "somebody gains cents",
    EventType.COINS_LOST: "somebody loses cents",
    EventType.DAMAGE_DEALT: "somebody or something takes damage",
    EventType.BEFORE_HEAL: "somebody is about to be healed",
    EventType.HEALED: "somebody is healed",
    EventType.PLAYER_REVIVED: "a player comes back",
}
"""
Every event above, in the words somebody would use to describe it.

Kept in this file rather than anywhere else so that the two cannot drift: a
member added to the enum without a sentence here fails a test. Anything that
offers an author a list of moments to react to reads this — without it, such
a list would have to invent words of its own, and that is a second table.
"""
