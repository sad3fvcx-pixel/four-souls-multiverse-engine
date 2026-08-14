# src/fsme/effects/builtin/loot.py

"""
Loot and soul effects.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fsme.cards import SoulToken
from fsme.events import EventType
from fsme.state import GameState, PlayerState

from ..context import EffectContext
from ..errors import EffectExecutionError
from ..registry import EffectRegistry


def _players(targets: Sequence[Any], effect: str) -> list[PlayerState]:
    players = [target for target in targets if isinstance(target, PlayerState)]

    if len(players) != len(targets):
        raise EffectExecutionError(f"'{effect}' expects player targets")

    return players


def _refill_loot_deck(ctx: EffectContext, state: GameState) -> bool:
    """
    Shuffle the discard pile back into the loot deck.

    Returns False when there is nothing left to reshuffle, which lets the
    caller stop drawing instead of raising: running out of cards is a legal
    game situation, not an engine error.
    """
    if not state.loot_discard.cards:
        return False

    state.loot_deck.cards.extend(state.loot_discard.cards)
    state.loot_discard.clear()

    ctx.rng.shuffle(state.loot_deck.cards)

    return True


DECK = "deck"
"""Where loot normally comes from."""

DISCARD = "discard"
"""Where a card can make it come from instead."""


def _next_loot(ctx: EffectContext, state: GameState, source: str) -> Any | None:
    """
    Take the top card of wherever this loot is coming from.

    Nothing left is not an error: a deck that has run dry and a discard pile
    that is empty both mean the same thing to the player looting, which is that
    they do not get a card.
    """
    if source == DISCARD:
        if not state.loot_discard.cards:
            return None

        return state.loot_discard.draw()

    if not state.loot_deck.cards and not _refill_loot_deck(ctx, state):
        return None

    return state.loot_deck.draw()


def draw_loot(ctx: EffectContext, targets: Sequence[Any], count: int = 1) -> int:
    """
    Draw loot cards into each target player's hand.

    Looting is offered for replacement before it happens, because cards change
    it: "they loot double that number instead" and "they loot from the top of
    the discard pile instead" both edit a loot that is about to happen rather
    than doing anything themselves. So the number and the pile are read back
    off the proposal instead of being taken for granted.
    """
    if count < 0:
        raise EffectExecutionError("draw_loot count must be non-negative")

    state = ctx.state
    drawn = 0

    for player in _players(targets, "draw_loot"):
        proposal = ctx.propose(
            EventType.BEFORE_LOOT_DRAW,
            controller=player.player_id,
            targets=[player],
            count=count,
            source=DECK,
        )

        if proposal.cancelled:
            continue

        wanted = max(0, int(proposal.get("count", count)))
        source = str(proposal.get("source", DECK))

        for _ in range(wanted):
            card = _next_loot(ctx, state, source)

            if card is None:
                break

            player.hand.add_top(card)
            drawn += 1

            ctx.emit(
                EventType.LOOT_DRAWN,
                controller=player.player_id,
                targets=[player],
                card=card,
            )

    return drawn


LEFT = "left"
RIGHT = "right"


def pass_hands(ctx: EffectContext, targets: Sequence[Any], direction: str = LEFT) -> int:
    """
    Every living player hands their whole hand to a neighbour, all at once.

    At once is the point: a hand passed on and a hand received are the same
    moment, so every hand is lifted before any is put down. Passing them one
    player at a time would give the second player the first player's cards and
    then pass those on again.
    """
    if direction not in (LEFT, RIGHT):
        raise EffectExecutionError(
            f"unknown direction '{direction}'; a hand goes left or right"
        )

    state = ctx.state
    seats = [player for player in state.players if player.alive]

    if len(seats) < 2:
        return 0

    step = 1 if direction == LEFT else -1

    lifted = [list(player.hand.cards) for player in seats]

    for player in seats:
        player.hand.cards.clear()

    passed = 0

    for index, cards in enumerate(lifted):
        receiver = seats[(index + step) % len(seats)]

        for card in cards:
            card.owner = receiver.player_id
            card.controller = receiver.player_id

            receiver.hand.add_top(card)
            passed += 1

        ctx.emit(
            EventType.ON_GAIN,
            controller=receiver.player_id,
            targets=[receiver],
        )

    return passed


def discard_loot(ctx: EffectContext, targets: Sequence[Any], count: int = 1) -> int:
    """
    Discard loot cards from the top of each target player's hand.
    """
    if count < 0:
        raise EffectExecutionError("discard_loot count must be non-negative")

    state = ctx.state
    discarded = 0

    for player in _players(targets, "discard_loot"):
        for _ in range(count):
            if not player.hand.cards:
                break

            card = player.hand.draw()
            state.loot_discard.add_top(card)
            discarded += 1

            ctx.emit(
                EventType.LOOT_DISCARDED,
                controller=player.player_id,
                targets=[player],
                card=card,
            )

    return discarded


def discard_cards(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Discard specific cards from whichever hand holds them.

    This is the chosen-card counterpart to ``discard_loot``, which takes from
    the top. A player told to discard down to the hand limit picks; a player
    told to discard at random does not.
    """
    state = ctx.state
    discarded = 0

    for card in targets:
        for player in state.players:
            if card not in player.hand.cards:
                continue

            player.hand.cards.remove(card)
            state.loot_discard.add_top(card)
            discarded += 1

            ctx.emit(
                EventType.LOOT_DISCARDED,
                controller=player.player_id,
                targets=[player],
                card=card,
            )

            break

    return discarded


def gain_soul(
    ctx: EffectContext,
    targets: Sequence[Any],
    count: int = 1,
    card: Any | None = None,
) -> int:
    """
    Give souls to each target player.

    When a card is supplied it becomes the soul, which is how a killed monster
    or a bonus soul card is awarded. Otherwise the engine mints soul tokens.
    """
    if count < 0:
        raise EffectExecutionError("gain_soul count must be non-negative")

    gained = 0

    for player in _players(targets, "gain_soul"):
        for _ in range(count):
            soul = card if card is not None else SoulToken(
                token_id=ctx.state.ids.allocate("soul")
            )

            player.souls.add_top(soul)
            gained += 1

            ctx.emit(
                EventType.SOUL_GAINED,
                controller=player.player_id,
                targets=[player],
                soul=soul,
            )

    return gained


def claim_soul(
    ctx: EffectContext,
    targets: Sequence[Any],
    card: Any | None = None,
) -> int:
    """
    Give a soul card itself to the players who earned it.

    A bonus soul is a card that becomes a soul rather than granting one, so it
    moves out of play and into the winner's pile. Which is the difference
    between it and a token: it can be taken away again.
    """
    soul = card if card is not None else ctx.source

    if soul is None:
        raise EffectExecutionError(
            "claim_soul needs a card; none was given and there is no source"
        )

    state = ctx.state
    claimed = 0

    for player in _players(targets, "claim_soul"):
        _detach(state, soul)

        player.souls.add_top(soul)
        claimed += 1

        ctx.emit(
            EventType.SOUL_GAINED,
            source=soul,
            controller=player.player_id,
            targets=[player],
            soul=soul,
        )

    return claimed


def _detach(state: Any, card: Any) -> None:
    """
    Take a card out of whichever zone currently holds it.
    """
    zones = [
        state.loot_deck,
        state.loot_discard,
        state.treasure_deck,
        state.treasure_shop,
        state.treasure_discard,
        state.bonus_souls,
        state.active_monsters,
        state.monster_deck,
        state.monster_discard,
        state.room_area,
        state.room_deck,
    ]

    for player in state.players:
        zones.extend((player.hand, player.treasures, player.curses, player.souls))

    for zone in zones:
        if card in zone.cards:
            zone.cards.remove(card)
            return


def steal_soul(ctx: EffectContext, targets: Sequence[Any], **_: Any) -> int:
    """
    Move a soul from each target player to whoever is doing the stealing.

    A soul taken is not a soul destroyed: it keeps counting, for somebody else.
    """
    state = ctx.state
    thief_id = ctx.actor

    if thief_id is None or not 0 <= thief_id < len(state.players):
        return 0

    thief = state.player(thief_id)
    stolen = 0

    for player in _players(targets, "steal_soul"):
        if player.player_id == thief_id or not player.souls.cards:
            continue

        soul = player.souls.draw()
        thief.souls.add_top(soul)
        stolen += 1

        ctx.emit(
            EventType.SOUL_LOST,
            controller=player.player_id,
            targets=[player],
            soul=soul,
        )
        ctx.emit(
            EventType.SOUL_GAINED,
            controller=thief_id,
            targets=[thief],
            soul=soul,
        )

    return stolen


def lose_soul(ctx: EffectContext, targets: Sequence[Any], count: int = 1) -> int:
    """
    Remove souls from each target player.
    """
    if count < 0:
        raise EffectExecutionError("lose_soul count must be non-negative")

    lost = 0

    for player in _players(targets, "lose_soul"):
        for _ in range(count):
            if not player.souls.cards:
                break

            soul = player.souls.draw()
            lost += 1

            ctx.emit(
                EventType.SOUL_LOST,
                controller=player.player_id,
                targets=[player],
                soul=soul,
            )

    return lost


def register(registry: EffectRegistry) -> None:
    """
    Register every loot and soul effect.
    """
    registry.register(
        "draw_loot",
        draw_loot,
        needs_target=True,
        primary="count",
        description="Draw loot cards."
    )
    registry.register(
        "pass_hands",
        pass_hands,
        primary="direction",
        description="Every player hands their whole hand to a neighbour.",
    )
    registry.register(
        "discard_loot",
        discard_loot,
        needs_target=True,
        primary="count",
        description="Discard loot cards.",
    )
    registry.register(
        "discard_cards",
        discard_cards,
        needs_target=True,
        description="Discard specific cards from hand.",
    )
    registry.register(
        "gain_soul",
        gain_soul,
        needs_target=True,
        primary="count",
        description="Gain souls."
    )
    registry.register(
        "claim_soul",
        claim_soul,
        needs_target=True,
        description="Give a bonus soul card itself to a player.",
    )
    registry.register(
        "steal_soul",
        steal_soul,
        needs_target=True,
        description="Take a soul from another player.",
    )
    registry.register(
        "lose_soul",
        lose_soul,
        needs_target=True,
        primary="count",
        description="Lose souls."
    )
