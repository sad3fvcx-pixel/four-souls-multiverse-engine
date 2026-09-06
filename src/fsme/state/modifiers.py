# src/fsme/state/modifiers.py

"""
Temporary modifiers for Four Souls Multiverse Engine.

A static modifier lasts as long as its card is in play and is recomputed from
the board, so nothing has to remember it. "+1 attack till end of turn" has no
card to hang on: the card that granted it is in the discard pile before the
bonus expires. Such a bonus is therefore stored, and stored in GameState like
everything else the game is made of, so that a saved game and a replayed game
carry it exactly as the live one did.

Expiry is the engine's, not the card's. A modifier says when it ends; the turn
ends it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

ATTACK = "attack"
"""Damage a player deals on a successful attack roll."""

MAX_HP = "max_hp"
"""A player's hit point maximum."""

ATTACKS = "attacks"
"""Attacks a player may declare per turn."""

LOOT_PLAYS = "loot_plays"
"""Loot cards a player may play per turn."""

PURCHASES = "purchases"
"""Items a player may buy per turn."""

ROLL = "roll"
"""
What a player adds to a die they roll.

Only temporary modifiers carry it. An item that improves rolls for as long as
it is in play is written as a replacement ability on ``roll_modified``, which is
the window the rules give for changing a roll; this stat is for the bonuses that
have no card left in play to hang on, such as "+1 to dice rolls till end of
turn".
"""

SHOP_COST = "shop_cost"
"""
What a player pays for an item in the shop, before the shop's own price.

A card that makes shopping cheaper changes a number the rules read, which is
what a statistic is for.
"""

LOOT_STEP = "loot_step"
"""
Cards drawn by the loot step at the start of a turn.

COMPREHENSIVE_RULES.md §3.1 has the turn begin by looting one card, and cards
add to that — "Loot +1 during your loot step" is this statistic and not an
extra loot card played.
"""

STATS = (
    ATTACK,
    MAX_HP,
    ATTACKS,
    LOOT_PLAYS,
    PURCHASES,
    ROLL,
    SHOP_COST,
    LOOT_STEP,
)
"""
Every statistic a modifier may change.

The names live here, below both the rules and the effects, so that the code
that grants a bonus and the code that adds bonuses up cannot drift apart.
"""


class Duration(StrEnum):
    """
    How long a temporary modifier lasts.
    """

    END_OF_TURN = "end_of_turn"
    """Until the current turn finishes, however many turns away that is."""

    GAME = "game"
    """Until the game ends: a permanent change with no card behind it."""


DIFFICULTY = "difficulty"
"""
What a player must roll to hit a monster.

Monsters have their own two numbers — the damage they deal and the roll they
demand — and cards change both. They are listed apart from the player statistics
because nothing else can carry them: a monster is not a player and has no seat.
"""

MONSTER_STATS = (ATTACK, DIFFICULTY)

STAT_WORDS = {
    ATTACK: "how much damage an attack does",
    MAX_HP: "the most hit points it can have",
    ATTACKS: "how many attacks a turn allows",
    LOOT_PLAYS: "how many loot cards a turn allows",
    PURCHASES: "how many items a turn allows buying",
    ROLL: "what is added to a die rolled",
    SHOP_COST: "what an item in the shop costs",
    LOOT_STEP: "how many cards the loot step draws",
    DIFFICULTY: "the roll needed to hit it",
}
"""
What each statistic is, in the words a person would use for it.

The same sentence each constant above carries, said to an author instead of to
whoever reads this file. Beside them on purpose: a name and its explanation
kept in different files drift, and the drift shows up as a dropdown offering
`loot_step` to somebody who has never read the source.
"""


@dataclass(slots=True)
class CardModifier:
    """
    A change to one card's own numbers, lasting beyond the card that made it.

    "This gains +1 AT till end of turn" belongs to the monster, not to any
    player, so it is kept on the monster and the turn takes it away.
    """

    stat: str
    amount: int
    duration: Duration = Duration.END_OF_TURN

    def expires_at_end_of_turn(self) -> bool:
        return self.duration is Duration.END_OF_TURN

    def __str__(self) -> str:
        sign = "+" if self.amount >= 0 else ""

        return f"{sign}{self.amount} {self.stat}"


@dataclass(slots=True)
class DamageShield:
    """
    Damage a player will not take, waiting for the damage to arrive.

    "Prevent the next instance of up to 2 damage they would take this turn" is
    not a replacement ability on a card: the card is in the discard pile, and
    the shield outlives it exactly as a temporary modifier does. It is spent by
    the first instance of damage it meets — the whole instance, however small —
    and what is left of it expires with the turn.
    """

    player_id: int
    amount: int | None = None
    """
    How much damage this stops, or None for the whole instance.

    Cards say both: "prevent the next 1 damage" names a number, and "prevent the
    next instance of damage" does not care how big the instance is.
    """

    label: str = ""
    """
    What the card that promised this calls it.

    A card that acts "when you prevent damage this way" means this shield and
    not another, so the announcement of a prevention carries the name back.
    """

    duration: Duration = Duration.END_OF_TURN

    def expires_at_end_of_turn(self) -> bool:
        return self.duration is Duration.END_OF_TURN

    def stops(self, damage: int) -> int:
        """
        Return how much of an incoming instance this shield takes.
        """
        return damage if self.amount is None else min(damage, self.amount)

    def __str__(self) -> str:
        size = "all" if self.amount is None else str(self.amount)

        return f"prevent {size} damage to player {self.player_id}"


@dataclass(slots=True)
class TemporaryModifier:
    """
    One stored change to one player's statistic.

    ``stat`` is a name from the static vocabulary — attack, max_hp, attacks,
    loot_plays, roll — so that a temporary bonus and a printed one are added up
    by the same code and can never disagree about what a number is.
    """

    stat: str
    amount: int
    player_id: int
    duration: Duration = Duration.END_OF_TURN

    def expires_at_end_of_turn(self) -> bool:
        return self.duration is Duration.END_OF_TURN

    def __str__(self) -> str:
        sign = "+" if self.amount >= 0 else ""

        return f"{sign}{self.amount} {self.stat} for player {self.player_id}"
