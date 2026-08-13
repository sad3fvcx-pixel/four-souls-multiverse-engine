# src/fsme/effects/builtin/decks.py

"""
Deck effects: shuffling, revealing and taking.

Searching a deck is two steps, not one. The player chooses a card — which is a
target, and targets already know how to stop and ask — and then something is
done with what they chose. Writing it that way means "search the treasure deck
and take it" and "search the loot deck and discard it" share everything except
the last word.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fsme.events import EventType
from fsme.state import GameState, PlayerState, Zone

from ..context import EffectContext
from ..errors import EffectExecutionError
from ..registry import EffectRegistry

DECKS = ("loot", "treasure", "monster", "room")


def deck_zone(state: GameState, name: str) -> Zone[Any]:
    """
    Return a deck by name.
    """
    zone: Zone[Any] | None = getattr(state, f"{name}_deck", None)

    if zone is None:
        raise EffectExecutionError(
            f"unknown deck '{name}'; the decks are {', '.join(DECKS)}"
        )

    return zone


def shuffle_deck(ctx: EffectContext, targets: Sequence[Any], deck: str = "loot") -> int:
    """
    Shuffle a deck through the engine RNG.
    """
    cards = deck_zone(ctx.state, deck).cards

    ctx.rng.shuffle(cards)

    return len(cards)


def reveal_cards(
    ctx: EffectContext,
    targets: Sequence[Any],
    deck: str = "loot",
    count: int = 1,
) -> list[Any]:
    """
    Show the top cards of a deck without moving them.

    Revealing changes nothing except what everybody knows, so the cards stay
    where they are and the fact is announced as an event.
    """
    if count < 0:
        raise EffectExecutionError("reveal_cards count must be non-negative")

    cards = deck_zone(ctx.state, deck).cards
    revealed = list(reversed(cards[-count:])) if count else []

    ctx.emit(
        EventType.REVEALED,
        controller=ctx.actor,
        deck=deck,
        cards=list(revealed),
    )

    return revealed


def take_card(
    ctx: EffectContext,
    targets: Sequence[Any],
    to: str = "hand",
    shuffle: str = "",
) -> int:
    """
    Move chosen cards out of wherever they are and into a player's keeping.

    ``to`` is ``hand`` or ``treasures``. ``shuffle`` names a deck to shuffle
    afterwards, which is what stops a search from telling everybody the order
    of what was left behind.
    """
    state = ctx.state
    owner = ctx.actor

    if owner is None or not 0 <= owner < len(state.players):
        return 0

    player = state.player(owner)
    destination = _destination(player, to)

    taken = 0

    for card in targets:
        if not _remove_from_anywhere(state, card):
            continue

        if to == "treasures":
            card.owner = owner
            card.controller = owner

        destination.add_top(card)
        taken += 1

        ctx.emit(
            EventType.ON_GAIN,
            source=card,
            controller=owner,
            targets=[player],
        )

    if shuffle:
        ctx.rng.shuffle(deck_zone(state, shuffle).cards)

    return taken


def _destination(player: PlayerState, to: str) -> Zone[Any]:
    if to == "hand":
        return player.hand

    if to == "treasures":
        return player.treasures

    raise EffectExecutionError(
        f"unknown destination '{to}'; use 'hand' or 'treasures'"
    )


def _remove_from_anywhere(state: GameState, card: Any) -> bool:
    """
    Take a card out of whichever deck or pile currently holds it.
    """
    for name in DECKS:
        zone = getattr(state, f"{name}_deck", None)

        if zone is not None and card in zone.cards:
            zone.cards.remove(card)
            return True

    for player in state.players:
        if card in player.hand.cards:
            player.hand.cards.remove(card)
            return True

    return False


def move_cards(
    ctx: EffectContext,
    targets: Sequence[Any],
    deck: str = "loot",
    position: str = "bottom",
) -> int:
    """
    Put chosen cards on the top or the bottom of a deck.

    The order of a deck is information, and this is the only effect allowed to
    change it without shuffling. Cards are moved in the order they were chosen,
    so "put these two on the bottom" leaves them in a knowable order rather than
    an accidental one.
    """
    if position not in ("top", "bottom"):
        raise EffectExecutionError(
            f"unknown position '{position}'; use 'top' or 'bottom'"
        )

    state = ctx.state
    zone = deck_zone(state, deck)

    moved = 0

    for card in targets:
        if not _remove_from_anywhere(state, card):
            continue

        if position == "top":
            zone.add_top(card)
        else:
            zone.cards.insert(0, card)

        moved += 1

    return moved


def register(registry: EffectRegistry) -> None:
    """
    Register every deck effect.
    """
    registry.register(
        "move_cards",
        move_cards,
        needs_target=True,
        primary="deck",
        description="Put cards on the top or bottom of a deck.",
    )
    registry.register(
        "shuffle_deck",
        shuffle_deck,
        primary="deck",
        description="Shuffle a deck.",
    )
    registry.register(
        "reveal_cards",
        reveal_cards,
        primary="count",
        description="Show the top cards of a deck.",
    )
    registry.register(
        "take_card",
        take_card,
        needs_target=True,
        primary="to",
        description="Take chosen cards into a hand or into play.",
    )
