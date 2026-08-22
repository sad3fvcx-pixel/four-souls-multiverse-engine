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

from fsme.content.vocabulary import WHOM
from fsme.events import EventType
from fsme.state import GameState, PlayerState, Zone

from ..context import EffectContext
from ..errors import EffectExecutionError
from ..registry import EffectRegistry

POSITIONS = ("top", "bottom", "discard")
"""
Where `move_cards` may put a card.

Named so that the guard below and the check a card file gets are the same list.
Two lists is how they come to disagree.
"""

DESTINATIONS = ("hand", "treasures")
"""
Where `take_card` may put a card it has taken.
"""

DECKS = ("loot", "treasure", "monster", "room")
"""
Every deck in the game, and the only four there are.

They behave the same way. That is the point of naming them in one place: a rule
about decks is a rule about all of them, and the alternative — the loot deck
knowing how to rebuild itself while the other three did not — is what let a
game run for ever.
"""


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


def restock(ctx: EffectContext, name: str) -> bool:
    """
    Rebuild a deck that has just run out, from its own discard pile.

    ``COMPREHENSIVE_RULES.md`` §9: "A deck that runs out is rebuilt by
    shuffling its discard pile. This does not use the queue." All four decks,
    the same way.

    **Call this where a card leaves a deck, not where a deck is found empty.**
    Running out is something a deck does — the last card leaves it — and not a
    state it sits in. The difference is what a discard pile is for: an empty
    deck beside a growing discard is an ordinary position at a table, and if
    the discard became the deck the moment anything was put in it, a monster
    killed with the deck already out would be shuffled up and turned straight
    back over. Nobody does that. What they do is shuffle when the deck runs
    out, and again when somebody needs a card and there is none.

    The timing within that is the whole of the fix. Rebuilding lazily —
    waiting for a draw to find the deck empty — is indistinguishable from this
    in every game where nothing is put into a deck between it emptying and the
    next draw. Where something is, the two readings part company completely: a
    card that puts itself on the bottom of an empty deck is the only card in it
    and is drawn straight back, for ever, while a full discard pile sits beside
    it untouched. That happened, to six games in a thousand.

    Returns whether anything was rebuilt, so a caller can tell "the deck was
    refilled" from "there was nothing to refill it with". A deck and a discard
    pile that are both empty is a legal position, not an error.
    """
    deck = deck_zone(ctx.state, name)

    if deck.cards:
        return False

    discard = discard_zone(ctx.state, name)

    if not discard.cards:
        return False

    deck.cards.extend(discard.cards)
    discard.clear()

    ctx.rng.shuffle(deck.cards)

    ctx.emit(EventType.DECK_REBUILT, deck=name, cards=len(deck.cards))

    return True


def draw_from(ctx: EffectContext, name: str) -> Any | None:
    """
    Take the top card of a deck, and leave the deck stocked behind it.

    ``None`` when there is nothing left anywhere: a deck that has run dry and a
    discard pile that is empty mean the same thing to whoever was drawing,
    which is that they do not get a card.

    Two restocks, for the two ways a deck comes back. The one before the draw
    is somebody needing a card from a deck that ran out while its discard was
    empty and has since filled: they shuffle, then draw. The one after is the
    draw itself having taken the last card, which is the deck running out — §9
    rebuilds it then, not when somebody next asks. Effects read deck state
    between actions, and a deck that is briefly empty when the rules say it is
    full is a deck that lies to them.
    """
    deck = deck_zone(ctx.state, name)

    if not deck.cards and not restock(ctx, name):
        return None

    card = deck.draw()

    restock(ctx, name)

    return card


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


def reveal_hand(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Show target players' hands to the table.

    Looking at a hand changes nothing about the game, only about what is known,
    so the cards stay where they are and the fact is announced.
    """
    shown = 0

    for player in targets:
        if not isinstance(player, PlayerState):
            raise EffectExecutionError("reveal_hand expects player targets")

        ctx.emit(
            EventType.REVEALED,
            controller=player.player_id,
            targets=[player],
            zone="hand",
            cards=list(player.hand.cards),
        )

        shown += 1

    return shown


def take_card(
    ctx: EffectContext,
    targets: Sequence[Any],
    to: str = "hand",
    shuffle: str = "",
    player: Any = None,
) -> int:
    """
    Move chosen cards out of wherever they are and into a player's keeping.

    ``to`` is ``hand`` or ``treasures``. ``shuffle`` names a deck to shuffle
    afterwards, which is what stops a search from telling everybody the order
    of what was left behind.

    ``player`` says who ends up with the card when it is not the player doing
    it: "give a loot card to another player" is this effect pointed elsewhere.
    """
    state = ctx.state
    owner = ctx.actor if player is None else int(player)

    if owner is None or not 0 <= owner < len(state.players):
        return 0

    player = state.player(owner)
    destination = _destination(player, to)

    taken = 0

    for card in targets:
        came_from = _deck_holding(state, card)

        if not _remove_from_anywhere(state, card):
            continue

        if to == "treasures":
            card.owner = owner
            card.controller = owner

        destination.add_top(card)
        taken += 1

        if came_from is not None:
            # A search that takes the last card of a deck is that deck running
            # out, the same as a draw would be.
            restock(ctx, came_from)

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
        f"unknown destination '{to}'; use {' or '.join(DESTINATIONS)}"
    )


def _zones_holding_cards(state: GameState) -> list[Zone[Any]]:
    """
    Every zone a card could be sitting in, deck first.

    The monster area is not here, and that is deliberate. It is a row of slots
    rather than a zone, and `active_monsters` — which looks like a zone and is
    one — is only the face-up view of that row, rebuilt from it by
    `rules.slots.sync`. Taking a card out of the view leaves it in the slot it
    is really in, and the next sync puts it straight back. Monsters leave
    through `_remove_from_anywhere`, which knows to go to the slots.
    """
    zones: list[Zone[Any]] = []

    for name in DECKS:
        zone = getattr(state, f"{name}_deck", None)

        if zone is not None:
            zones.append(zone)

    zones.extend(
        (
            state.loot_discard,
            state.treasure_discard,
            state.treasure_shop,
            state.monster_discard,
            state.room_area,
            state.room_discard,
        )
    )

    for player in state.players:
        zones.extend((player.hand, player.treasures, player.curses))

    return zones


def _deck_holding(state: GameState, card: Any) -> str | None:
    """
    Name the deck a card is sitting in, or ``None`` if it is somewhere else.

    Asked before a card is moved, so that whoever moved it can tell whether
    they have just emptied a deck. A deck runs out when its last card leaves,
    whichever effect took it — a search, a card put somewhere, a sweep — and
    not only when somebody draws.
    """
    for name in DECKS:
        deck: Zone[Any] | None = getattr(state, f"{name}_deck", None)

        if deck is not None and card in deck.cards:
            return name

    return None


def _remove_from_anywhere(state: GameState, card: Any) -> bool:
    """
    Take a card out of wherever it really is, and say whether it was anywhere.

    Two kinds of place, because the game has two. Most cards sit in a zone and
    are removed from it. A monster sits in a slot of the monster area, which is
    a row of piles and not a zone at all, and it leaves through
    `rules.slots.remove` — the one piece of code allowed to write the row and
    the face-up view of it together. That also brings back whatever the monster
    was covering, which is the slot's business and not this function's.

    Removing a monster any other way is how a card ended up in two places at
    once: put on the bottom of a deck by one effect, and still standing in its
    slot because the row was never told.
    """
    for zone in _zones_holding_cards(state):
        if card in zone.cards:
            zone.cards.remove(card)
            return True

    # Imported here rather than at the top: the rules are built on the effects,
    # so an effect reaching back into them has to do it at the moment it needs
    # them. `damage.py` does the same for the same reason.
    from fsme.rules.slots import remove as leave_slot

    return leave_slot(state, card) is not None


def params_depth(depth: int | None) -> int | None:
    """
    Normalise a depth, treating a missing or negative one as no depth at all.
    """
    return depth if depth is not None and depth >= 0 else None


def move_cards(
    ctx: EffectContext,
    targets: Sequence[Any],
    deck: str = "loot",
    position: str = "bottom",
    depth_from: int | None = None,
) -> int:
    """
    Put chosen cards on the top or the bottom of a deck.

    The order of a deck is information, and this is the only effect allowed to
    change it without shuffling. Cards are moved in the order they were chosen,
    so "put these two on the bottom" leaves them in a knowable order rather than
    an accidental one.

    A card that is in no zone at all is still moved: a loot card that says "put
    this on the bottom of the loot deck" is resolving, which means it is on the
    stack and nowhere else.
    """
    if position not in POSITIONS:
        raise EffectExecutionError(
            f"unknown position '{position}'; use "
            f"{', '.join(POSITIONS[:-1])} or {POSITIONS[-1]}"
        )

    state = ctx.state
    zone = (
        discard_zone(state, deck) if position == "discard" else deck_zone(state, deck)
    )

    moved = 0

    depth = params_depth(depth_from)

    for card in targets:
        came_from = _deck_holding(state, card)

        _remove_from_anywhere(state, card)

        if position == "bottom":
            zone.cards.insert(0, card)
        elif depth is not None:
            # Counted from the top, which is how a card says it: "six cards
            # from the top" is six cards that stay above it.
            zone.cards.insert(max(0, len(zone.cards) - depth), card)
        else:
            zone.add_top(card)

        moved += 1

        if came_from is not None:
            # The move finishes, and then the deck it came out of is asked
            # whether it has run out. Asking first would get the wrong answer
            # twice over: a card put back on the same deck never left it as far
            # as the deck is concerned, and a card put into that deck's discard
            # belongs in the shuffle that rebuilds it.
            restock(ctx, came_from)

    return moved


def discard_zone(state: GameState, name: str) -> Zone[Any]:
    """
    Return the discard pile belonging to a deck.
    """
    zone: Zone[Any] | None = getattr(state, f"{name}_discard", None)

    if zone is None:
        raise EffectExecutionError(f"deck '{name}' has no discard pile")

    return zone


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
        values={"deck": DECKS, "position": POSITIONS},
        unless={"depth_from": "position"},
    )
    registry.register(
        "shuffle_deck",
        shuffle_deck,
        primary="deck",
        description="Shuffle a deck.",
        values={"deck": DECKS},
    )
    registry.register(
        "reveal_cards",
        reveal_cards,
        primary="count",
        description="Show the top cards of a deck.",
        values={"deck": DECKS},
        least={"count": 0},
        asks={
            "count": "how many cards",
        },
    )
    registry.register(
        "reveal_hand",
        reveal_hand,
        needs_target=True,
        description="Show a player's hand.",
    )
    registry.register(
        "take_card",
        take_card,
        needs_target=True,
        primary="to",
        description="Take chosen cards into a hand or into play.",
        values={"shuffle": ("",) + DECKS, "to": DESTINATIONS},
        roles={"player": WHOM},
    )
