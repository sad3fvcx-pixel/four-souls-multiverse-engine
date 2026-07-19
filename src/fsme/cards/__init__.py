# src/fsme/cards/__init__.py

"""
Card subsystem exports.
"""

from .card import Card
from .constants import (
    DEFAULT_HAND_LIMIT,
    DEFAULT_MAX_COUNTERS,
    DEFAULT_MONSTER_SLOTS,
    DEFAULT_ROOM_SLOTS,
    DEFAULT_SHOP_SIZE,
    DEFAULT_SOULS_TO_WIN,
)
from .context import CardContext
from .dispatcher import CardDispatcher
from .errors import (
    CardError,
    CardExecutionError,
    CardResolutionError,
    InvalidCardError,
    UnknownCardError,
)
from .handler import CardHandler
from .resolver import CardResolver
from .result import CardResult
from .types import CardType
from .utils import (
    card_name,
    ensure_card,
    ensure_cards,
    is_card,
)

__all__ = [
    "Card",
    "CardType",
    "CardContext",
    "CardDispatcher",
    "CardHandler",
    "CardResolver",
    "CardResult",
    "CardError",
    "CardResolutionError",
    "CardExecutionError",
    "InvalidCardError",
    "UnknownCardError",
    "DEFAULT_HAND_LIMIT",
    "DEFAULT_SHOP_SIZE",
    "DEFAULT_MONSTER_SLOTS",
    "DEFAULT_ROOM_SLOTS",
    "DEFAULT_SOULS_TO_WIN",
    "DEFAULT_MAX_COUNTERS",
    "ensure_card",
    "ensure_cards",
    "card_name",
    "is_card",
]