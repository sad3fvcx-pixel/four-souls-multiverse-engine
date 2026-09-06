# src/fsme/rules/turn.py

"""
Turn structure for Four Souls Multiverse Engine.

The official turn runs start → loot → action → end. The engine represents every
phase explicitly, and the phase is always part of GameState so that a save
taken mid-turn restores mid-turn.
"""

from __future__ import annotations

from typing import Any

from fsme.cards import Ability
from fsme.commands import Command
from fsme.effects import EffectContext
from fsme.events import EventType
from fsme.stack import (
    ADVANCE_TURN,
    CHANGE_ROOMS,
    DISCARD_TO_HAND_LIMIT,
    StackItem,
    StackItemType,
)
from fsme.stack import LOOT_STEP as LOOT_STEP_LABEL
from fsme.state import GamePhase, GameState

from .combat import end_combat
from .constants import (
    ATTACKS_PER_TURN,
    HAND_LIMIT,
    LOOT_PLAYS_PER_TURN,
    LOOT_STEP_CARDS,
    PURCHASES_PER_TURN,
)
from .death import restore_everyone
from .obligations import refuse_to_stop
from .statics import (
    ATTACKS,
    LOOT_PLAYS,
    LOOT_STEP,
    PURCHASES,
    expire_turn_modifiers,
    static_value,
)


class StartGameHandler:
    """
    Begins the game and hands the first turn to the first seat.
    """

    def validate(self, command: Command, state: GameState) -> str | None:
        if state.started:
            return "the game has already started"

        if not state.players:
            return "the game has no players"

        return None

    def execute(self, command: Command, context: EffectContext) -> None:
        state = context.state

        first = first_seat(state)

        state.started = True
        state.turn.turn_number = 1
        state.turn.active_player = first
        state.turn.priority_player = first
        state.turn.phase = GamePhase.START

        context.emit(EventType.GAME_START)

        # Read off the seat, then off the game, and never off the constants.
        # The rulebook's numbers are still the defaults — GameState starts with
        # them — but a game set up asking for others has to be dealt with them,
        # and a process playing a thousand games must not carry one game's
        # answer into the next.
        #
        # One loop, not two: a scenario that gives one player five cents is
        # dealt by the same code that gives everybody three, because a second
        # way of dealing an opening is a second thing that can be wrong.
        for player in state.players:
            context.apply(
                "draw_loot",
                [player],
                count=_opening(player.starting_hand, state.starting_hand),
            )
            context.apply(
                "gain_coins",
                [player],
                amount=_opening(player.starting_coins, state.starting_coins),
            )

        _begin_turn(context, active_player=first)


def _opening(seat: int | None, table: int) -> int:
    """
    What one player is dealt: their own number, or the table's.
    """
    return table if seat is None else seat


FIRST_PLAYER = "first_player"
"""
The tag a character carries when it decides who starts.

"If you control this as the game starts, you go first" is not an ability: it
resolves nothing and happens before there is anything to resolve into. It is a
question the setup asks of the characters that were dealt, and the answer is
printed on one of them.
"""


def first_seat(state: GameState) -> int:
    """
    Return the seat that takes the first turn.

    The first seat unless a character says otherwise, and the earliest such
    character if somehow two do: a game must start with exactly one player,
    however the content is arranged.
    """
    for player in state.players:
        character = player.character

        if character is not None and character.has_tag(FIRST_PLAYER):
            return player.player_id

    return 0


class EndPhaseHandler:
    """
    Moves the turn on to its next phase.

    A player who plays no loot still has to reach the action phase, so leaving
    a phase is an explicit choice rather than a side effect of acting.
    """

    def validate(self, command: Command, state: GameState) -> str | None:
        if not state.started:
            return "the game has not started"

        if state.game_over:
            return "the game is over"

        if command.player != state.turn.active_player:
            return "only the active player may end a phase"

        if state.turn.phase is GamePhase.END:
            return "the turn is already in its end phase; end the turn instead"

        if not state.stack.is_empty():
            return "the stack must resolve before the phase ends"

        if state.turn.phase is GamePhase.ACTION:
            # Leaving the action phase is where an unpaid "must attack" stops
            # a player: before it there is nothing to pay it with.
            return refuse_to_stop(state, command.player)

        return None

    def execute(self, command: Command, context: EffectContext) -> None:
        state = context.state

        state.turn.next_phase()

        context.emit(
            EventType.PHASE_CHANGED,
            controller=command.player,
            phase=str(state.turn.phase),
        )


class EndTurnHandler:
    """
    Ends the active player's turn and starts the next one.
    """

    def validate(self, command: Command, state: GameState) -> str | None:
        if not state.started:
            return "the game has not started"

        if state.game_over:
            return "the game is over"

        if command.player != state.turn.active_player:
            return "only the active player may end the turn"

        if not state.stack.is_empty():
            return "the stack must resolve before the turn ends"

        return refuse_to_stop(state, command.player)

    def execute(self, command: Command, context: EffectContext) -> None:
        state = context.state
        player = state.player(command.player)

        state.turn.phase = GamePhase.END

        context.emit(
            EventType.PHASE_CHANGED,
            controller=player.player_id,
            phase=str(GamePhase.END),
        )

        # COMPREHENSIVE_RULES.md §3.3 opens the end phase with the effects that
        # answer it, so they are announced here rather than while the turn is
        # being passed: their abilities go on the stack above the work below
        # and resolve while this is still the player's turn.
        context.emit(EventType.TURN_END, controller=player.player_id)
        context.emit(EventType.TURN_CLEANUP, controller=player.player_id)

        # Pushed first, so it resolves last: the turn only passes once the
        # player has finished discarding.
        context.push(
            StackItem(
                kind=StackItemType.ENGINE_EFFECT,
                label=ADVANCE_TURN,
                controller=player.player_id,
            )
        )

        # No count, because there is no count yet. How many cards are over the
        # limit is a question about the hand at the moment this resolves, and
        # the end phase exists to let things happen in between: §3.3 puts "at
        # the end of your turn" effects at step 1 and the discard at step 3, so
        # a card that draws in step 1 is a card that has to be discarded in
        # step 3. Deciding the number here would answer it before those effects
        # had run, and a player who was at ten when the phase opened would
        # carry away whatever they were dealt afterwards.
        context.push(
            StackItem(
                kind=StackItemType.ENGINE_EFFECT,
                label=DISCARD_TO_HAND_LIMIT,
                source=player.character,
                controller=player.player_id,
            )
        )

        if _rooms_may_change(state):
            # Pushed last, so it resolves first: the change of rooms is offered
            # before the hand is trimmed, and after the effects that answered
            # the end of the turn — which is why a room arriving now with "at
            # the end of the turn, discard this" is discarded at the end of the
            # next one (COMPREHENSIVE_RULES.md §12).
            context.push(
                StackItem(
                    kind=StackItemType.ENGINE_EFFECT,
                    label=CHANGE_ROOMS,
                    ability=change_rooms(),
                    source=state.room_area.cards[0] if state.room_area.cards else None,
                    controller=player.player_id,
                )
            )


def _rooms_may_change(state: GameState) -> bool:
    """
    Whether the active player is offered a change of rooms at all.

    COMPREHENSIVE_RULES.md §12: only in a turn where a monster died, and only
    in a game that has rooms in it — asking a table playing without them would
    be asking about a card nobody put in the box.
    """
    if not state.turn.monster_died:
        return False

    return bool(state.room_area.cards or state.room_deck.cards)


def change_rooms() -> Ability:
    """
    Build the offer to change rooms.

    Written as an ability for the same reason the hand limit and the death
    penalty are: "may" is a question, and asking one mid-resolution is
    something abilities already know how to do.

    Discarding and refilling are one instruction here because the rules make
    them one: if the slot is empty after the room goes, it *must* be filled.
    A room deck with nothing left in it simply leaves the slot empty, which is
    what "the top card of the room deck" means when there is no top card.
    """
    return Ability(
        trigger=str(EventType.TURN_CLEANUP),
        effects=(
            {
                "may": [
                    {"effect": "leave_room"},
                    {"effect": "enter_room"},
                ],
                "as": "changed_rooms",
                "prompt": "Put the room into the discard and turn over another?",
            },
        ),
        description="You may change rooms, a monster having died this turn.",
    )


def trim_to_hand_limit(item: StackItem, context: EffectContext) -> None:
    """
    Look at the hand, and ask for a discard if it is over the limit.

    COMPREHENSIVE_RULES.md §3.3 step 3. Two objects rather than one because
    they answer two different questions at two different moments: this one asks
    *how many*, once everything ahead of it in the end phase has resolved, and
    the ability it pushes asks the player *which*. A hand at or under the limit
    pushes nothing and the turn passes.
    """
    state = context.state
    seat = item.controller

    if seat is None or not 0 <= seat < len(state.players):
        return

    player = state.player(seat)
    surplus = player.hand_size - HAND_LIMIT

    if surplus <= 0:
        return

    context.push(
        StackItem(
            kind=StackItemType.ENGINE_EFFECT,
            label=DISCARD_TO_HAND_LIMIT,
            ability=discard_to_hand_limit(surplus),
            source=player.character,
            controller=seat,
        )
    )


def discard_to_hand_limit(count: int) -> Ability:
    """
    Build the rule that trims a hand down to the limit.

    It is written in the same language as a card, which is what lets the
    player choose which cards to lose: asking a question mid-resolution is
    something abilities already know how to do, and a rule expressed as an
    ability inherits it for free.
    """
    return Ability(
        trigger=str(EventType.TURN_CLEANUP),
        targets=(
            {"target_loot": {"count": count, "as": "discarded"}},
        ),
        effects=(
            {"effect": "discard_cards", "target": "discarded"},
        ),
        description=f"Discard {count} card(s) down to the hand limit.",
    )


def advance_turn(item: StackItem, context: EffectContext) -> None:
    """
    Close the current turn and open the next one.
    """
    state = context.state

    if item.controller is None:
        return

    # An attack belongs to the turn that declared it. A card that ends the turn
    # mid-fight — or cancels everything that has not resolved — leaves the
    # combat behind, and a combat nobody is resolving would refuse every attack
    # from then on.
    end_combat(context)

    # COMPREHENSIVE_RULES.md §3.3: everybody and every monster heals fully, and
    # whoever died this turn comes back. This happens before the bonuses that
    # last "till end of turn" lapse, so a player who bought hit points heals to
    # the larger number and only then loses the difference.
    restore_everyone(context)

    for modifier in expire_turn_modifiers(state):
        context.emit(
            EventType.STAT_EXPIRED,
            controller=modifier.player_id,
            stat=modifier.stat,
            amount=modifier.amount,
        )

    following = state.next_player(item.controller)

    while following in state.skipped_players:
        # A skipped turn is a turn nobody takes: the seat is passed over once
        # and the debt is paid.
        state.skipped_players.remove(following)
        following = state.next_player(following)

    promised = state.turn.extra_turn_for

    if promised is not None and state.player(promised).alive:
        # An extra turn is the same turn structure over again, not a special
        # case: the seat simply does not pass.
        following = promised

    state.turn.extra_turn_for = None

    state.turn.reset_for_new_turn(following)

    _begin_turn(context, active_player=following)


def loot_step(item: StackItem, context: EffectContext) -> None:
    """
    Draw the cards a turn opens with.

    "Loot +1 during your loot step" is counted here rather than written into
    the number: a card that adds to the draw is a static like any other.
    """
    state = context.state
    seat = item.controller

    if seat is None or not 0 <= seat < len(state.players):
        return

    player = state.player(seat)

    if not player.alive:
        return

    drawn = static_value(state, LOOT_STEP, seat, LOOT_STEP_CARDS)

    if drawn > 0:
        context.apply("draw_loot", [player], count=drawn)


def _character_to_recharge(player: Any) -> list[Any]:
    """
    A character card recharges with the items, being tapped like one.
    """
    character = player.character

    if character is None or not getattr(character, "tapped", False):
        return []

    return [character]


def _begin_turn(context: EffectContext, *, active_player: int) -> None:
    """
    Run the start of a turn: recharge, refresh allowances, announce.

    Recharging happens before the start-of-turn trigger so that an ability
    reacting to ``turn_start`` sees items already untapped, which is the order
    the rulebook uses.
    """
    state = context.state
    player = state.player(active_player)

    for seat in state.players:
        # Every player's allowance refreshes, not only the active one's: a
        # player may answer a card on somebody else's turn.
        seat.loot_played = 0

        # A death is once per turn, and this is the turn it stops being this
        # turn.
        seat.died_this_turn = False

    player.reset_turn()

    player.attacks_left = static_value(
        state, ATTACKS, active_player, ATTACKS_PER_TURN
    )
    player.purchases_left = static_value(
        state, PURCHASES, active_player, PURCHASES_PER_TURN
    )
    player.additional_loot_plays = static_value(
        state, LOOT_PLAYS, active_player, LOOT_PLAYS_PER_TURN
    ) - LOOT_PLAYS_PER_TURN

    tapped = [] if player.character is None else _character_to_recharge(player)

    for card in player.treasures.cards:
        if not getattr(card, "tapped", False):
            continue

        if getattr(card, "recharge_skipped", False):
            # One recharge is missed, not every recharge: the card is let off
            # as it is passed over.
            card.recharge_skipped = False
            continue

        tapped.append(card)

    if tapped:
        context.apply("recharge", tapped)

    state.turn.phase = GamePhase.START

    context.emit(EventType.TURN_START, controller=active_player)

    state.turn.phase = GamePhase.LOOT

    # COMPREHENSIVE_RULES.md §3.1: the start phase ends by looting, and the
    # loot goes into the queue rather than being drawn here — the effects that
    # answer the turn starting resolve first, and a card that looks at the top
    # of the loot deck must look before this draws from it.
    context.push(
        StackItem(
            kind=StackItemType.ENGINE_EFFECT,
            label=LOOT_STEP_LABEL,
            controller=active_player,
        )
    )

    context.emit(
        EventType.PHASE_CHANGED,
        controller=active_player,
        phase=str(GamePhase.LOOT),
    )
