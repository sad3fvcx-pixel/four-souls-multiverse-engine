# src/fsme/cards/utils.py

"""
Utility functions for the card subsystem.
"""

from __future__ import annotations

from collections.abc import Iterable

from .card import Card


def ensure_card(obj: object) -> Card:
    """
    Ensure that an object is a Card.
    """
    if not isinstance(obj, Card):
        raise TypeError(
            f"Expected Card, got {type(obj).__name__}."
        )

    return obj


def ensure_cards(
    cards: Iterable[object],
) -> list[Card]:
    """
    Validate an iterable of cards.
    """
    return [ensure_card(card) for card in cards]


def card_name(card: Card) -> str:
    """
    Return a human-readable card name.
    """
    return card.name


def is_card(obj: object) -> bool:
    """
    Check whether an object is a Card.
    """
    return isinstance(obj, Card)