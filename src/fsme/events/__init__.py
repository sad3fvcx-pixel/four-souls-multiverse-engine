# src/fsme/events/__init__.py

"""
Event subsystem exports.
"""

from .bus import EventBus
from .constants import (
    CARD_EVENT_SOURCE,
    DEFAULT_EVENT_PRIORITY,
    MAX_EVENT_DEPTH,
    PLAYER_EVENT_SOURCE,
    SYSTEM_EVENT_SOURCE,
)
from .context import EventContext
from .dispatcher import EventDispatcher
from .errors import (
    EventDispatchError,
    EventHandlerError,
    EventQueueError,
    EventRegistrationError,
)
from .event import Event
from .filter import (
    EventFilter,
    accept_all,
    active_only,
    cancelled_only,
)
from .listener import EventListener
from .priority import EventPriority
from .queue import EventQueue
from .result import EventResult
from .subscription import EventSubscription
from .types import EventType
from .utils import (
    create_event,
    ensure_not_cancelled,
    is_cancelled,
)

__all__ = [
    "Event",
    "EventBus",
    "EventContext",
    "EventDispatcher",
    "EventFilter",
    "EventListener",
    "EventPriority",
    "EventQueue",
    "EventResult",
    "EventSubscription",
    "EventType",
    "EventDispatchError",
    "EventHandlerError",
    "EventRegistrationError",
    "EventQueueError",
    "accept_all",
    "active_only",
    "cancelled_only",
    "create_event",
    "ensure_not_cancelled",
    "is_cancelled",
    "DEFAULT_EVENT_PRIORITY",
    "MAX_EVENT_DEPTH",
    "SYSTEM_EVENT_SOURCE",
    "PLAYER_EVENT_SOURCE",
    "CARD_EVENT_SOURCE",
]