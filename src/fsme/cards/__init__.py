# src/fsme/cards/__init__.py

"""
Card subsystem exports.

Cards are data. A definition describes what a card does; the Runtime decides
how it happens.
"""

from .card import CardInstance, SoulToken
from .definition import Ability, CardDefinition, Static
from .errors import (
    CardError,
    DuplicateCardError,
    InvalidCardError,
    UnknownCardError,
)
from .loader import CardLoader
from .registry import CardRegistry
from .types import CardType
from .validator import validate_card, validate_cards

__all__ = [
    "Ability",
    "CardDefinition",
    "CardInstance",
    "CardLoader",
    "CardRegistry",
    "CardType",
    "SoulToken",
    "Static",
    "CardError",
    "DuplicateCardError",
    "InvalidCardError",
    "UnknownCardError",
    "validate_card",
    "validate_cards",
]
