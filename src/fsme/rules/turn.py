# src/fsme/rules/turn.py

"""
Turn structure for Four Souls Multiverse Engine.

The official turn runs start → loot → action → end. The engine represents every
phase explicitly, and the phase is always part of GameState so that a save
taken mid-turn restores mid-turn.
"""

from __future__ import annotations

from fsme.cards import Ability
from fsme.commands import Command
from fsme.effects import EffectContext
from fsme.events import EventType
from fsme.stack import StackItem, StackItemType
from fsme.state import GamePhase, GameState

from .constants import (
    ATTACKS_PER_TURN,
    HAND_LIMIT,
    LOOT_PLAYS_PER_TURN,
    STARTING_HAND_SIZE,
)
from .statics import ATTACKS, LOOT_PLAYS, expire_turn_modifiers, static_value

ADVANCE_TURN = "advance_turn"

DISCARD_TO_HAND_LIMIT = "discard_to_hand_limit"


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

        state.started = True
        state.turn.turn_number = 1
        state.turn.active_player = 0
        state.turn.priority_player = 0
        state.turn.phase = GamePhase.START

        context.emit(EventType.GAME_START)

        for player in state.players:
            context.apply("draw_loot", [player], count=STARTING_HAND_SIZE)

        _begin_turn(context, active_player=0)


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

        return None

    def execute(self, command: Command, context: EffectContext) -> None:
        state = context.state
        player = state.player(command.player)

        state.turn.phase = GamePhase.END

        context.emit(
            EventType.PHASE_CHANGED,
            controller=player.player_id,
            phase=str(GamePhase.END),
        )

        # Pushed first, so it resolves last: the turn only passes once the
        # player has finished discarding.
        context.push(
            StackItem(
                kind=StackItemType.ENGINE_EFFECT,
                label=ADVANCE_TURN,
                controller=player.player_id,
            )
        )

        surplus = player.hand_size - HAND_LIMIT

        if surplus > 0:
            context.push(
                StackItem(
                    kind=StackItemType.ENGINE_EFFECT,
                    label=DISCARD_TO_HAND_LIMIT,
                    ability=discard_to_hand_limit(surplus),
                    source=player.character,
                    controller=player.player_id,
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

    context.emit(EventType.TURN_END, controller=item.controller)
    context.emit(EventType.TURN_CLEANUP, controller=item.controller)

    for modifier in expire_turn_modifiers(state):
        context.emit(
            EventType.STAT_EXPIRED,
            controller=modifier.player_id,
            stat=modifier.stat,
            amount=modifier.amount,
        )

    following = state.next_player(item.controller)

    state.turn.reset_for_new_turn(following)

    _begin_turn(context, active_player=following)


def _begin_turn(context: EffectContext, *, active_player: int) -> None:
    """
    Run the start of a turn: recharge, refresh allowances, announce.

    Recharging happens before the start-of-turn trigger so that an ability
    reacting to ``turn_start`` sees items already untapped, which is the order
    the rulebook uses.
    """
    state = context.state
    player = state.player(active_player)

    player.reset_turn()

    player.attacks_left = static_value(
        state, ATTACKS, active_player, ATTACKS_PER_TURN
    )
    player.additional_loot_plays = static_value(
        state, LOOT_PLAYS, active_player, LOOT_PLAYS_PER_TURN
    ) - LOOT_PLAYS_PER_TURN

    tapped = [card for card in player.treasures.cards if getattr(card, "tapped", False)]

    if tapped:
        context.apply("recharge", tapped)

    state.turn.phase = GamePhase.START

    context.emit(EventType.TURN_START, controller=active_player)

    state.turn.phase = GamePhase.LOOT

    context.emit(
        EventType.PHASE_CHANGED,
        controller=active_player,
        phase=str(GamePhase.LOOT),
    )
