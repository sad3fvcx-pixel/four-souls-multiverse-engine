# src/fsme/cards/types.py

"""
Card type definitions for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from enum import Enum


class CardType(str, Enum):
    """
    Top-level card categories.
    """

    CHARACTER = "character"

    TREASURE = "treasure"

    LOOT = "loot"

    MONSTER = "monster"

    ROOM = "room"

    BONUS_SOUL = "bonus_soul"

    EVENT = "event"

    CURSE = "curse"

    STARTING_ITEM = "starting_item"

    SOUL = "soul"

    TOKEN = "token"

    OTHER = "other"