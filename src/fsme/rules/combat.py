# src/fsme/rules/combat.py

"""
Combat for Four Souls Multiverse Engine.

An attack is a sequence of rounds, not a single action: the attacker rolls, one
side takes damage, and if both are still standing it happens again. Each round
is pushed onto the stack as its own object, so abilities may resolve between
rounds exactly as the official rules allow. The Runtime resolving the stack is
therefore what drives combat forward — nothing here loops.
"""

from __future__ import annotations

from typing import Any

from fsme.cards import CardType
from fsme.commands import Command
from fsme.effects import EffectContext
from fsme.effects.builtin.dice import rolled
from fsme.events import EventType
from fsme.stack import COMBAT_ROUND, StackItem, StackItemType
from fsme.state import GamePhase, GameState

from .constants import BASE_PLAYER_ATTACK, DICE_SIDES
from .statics import ATTACK, DIFFICULTY, monster_value, static_value

DEFAULT_MONSTER_ROLL = 4
"""Roll a player must meet when a monster card does not print one."""

DEFAULT_MONSTER_ATTACK = 1
"""Damage a monster deals when its card does not print an attack value."""


class AttackHandler:
    """
    Declares an attack against an active monster.
    """

    def validate(self, command: Command, state: GameState) -> str | None:
        if not state.started:
            return "the game has not started"

        if state.game_over:
            return "the game is over"

        if command.player != state.turn.active_player:
            return "only the active player may attack"

        if state.turn.phase is not GamePhase.ACTION:
            return f"attacks are not allowed during the {state.turn.phase} phase"

        player = state.player(command.player)

        if not player.alive:
            return "a dead player may not attack"

        if not player.can_attack():
            return "no attacks remaining this turn"

        if state.combat.active:
            return "an attack is already in progress"

        index = command.get("index", 0)
        monsters = state.active_monsters.cards

        if not isinstance(index, int) or not 0 <= index < len(monsters):
            return f"no monster at index {index!r}"

        if not getattr(monsters[index], "alive", False):
            return "that monster is already dead"

        return None

    def execute(self, command: Command, context: EffectContext) -> None:
        state = context.state
        player = state.player(command.player)

        monster = state.active_monsters.cards[int(command.get("index", 0))]

        player.spend_attack()
        state.turn.record_attack()
        state.combat.begin(player.player_id, monster)

        context.emit(
            EventType.ATTACK_START,
            source=monster,
            controller=player.player_id,
            targets=[monster],
        )

        push_combat_round(context, player.player_id, monster)


def push_combat_round(
    context: EffectContext,
    attacker: int,
    monster: Any,
) -> StackItem:
    """
    Queue the next round of an ongoing attack.
    """
    return context.push(
        StackItem(
            kind=StackItemType.COMBAT,
            label=COMBAT_ROUND,
            source=monster,
            controller=attacker,
        )
    )


def combat_round(item: StackItem, context: EffectContext) -> None:
    """
    Resolve one round: roll, then damage one side.
    """
    state = context.state
    combat = state.combat

    if not combat.active or combat.attacker is None:
        return

    attacker = state.player(combat.attacker)
    monster = combat.monster

    if not attacker.alive or monster is None or not getattr(monster, "alive", False):
        end_combat(context)
        return

    combat.next_round()

    context.emit(
        EventType.BEFORE_ATTACK_ROLL,
        source=monster,
        controller=attacker.player_id,
        round=combat.round_number,
    )

    state.turn.record_attack_roll()

    roll = rolled(context, DICE_SIDES, attack=True)
    required = _required_roll(monster, state)

    context.emit(
        EventType.AFTER_ATTACK_ROLL,
        source=monster,
        controller=attacker.player_id,
        value=roll,
        required=required,
        hit=roll >= required,
        attack=True,
    )

    if roll >= required:
        damage = static_value(
            state, ATTACK, attacker.player_id, BASE_PLAYER_ATTACK
        )

        context.apply(
            "deal_damage", [monster], amount=damage, combat=True, roll=roll
        )
    else:
        context.apply(
            "deal_damage",
            [attacker],
            amount=_monster_attack(monster, state),
            combat=True,
            dealt_by=monster,
            roll=roll,
        )

    # The next round waits behind anything the damage triggered. If either side
    # died, State-Based Actions run first and this round ends the attack.
    push_combat_round(context, attacker.player_id, monster)


def end_combat(context: EffectContext) -> None:
    """
    Finish the current attack.
    """
    state = context.state
    combat = state.combat

    if not combat.active:
        return

    monster = combat.monster
    attacker = combat.attacker

    combat.end()

    context.emit(
        EventType.ATTACK_END,
        source=monster,
        controller=attacker,
    )


def _required_roll(monster: Any, state: GameState) -> int:
    definition = getattr(monster, "definition", None)
    required = getattr(definition, "roll", None)
    printed = int(required) if required else DEFAULT_MONSTER_ROLL

    return monster_value(state, DIFFICULTY, monster, printed)


def _monster_attack(monster: Any, state: GameState) -> int:
    definition = getattr(monster, "definition", None)
    attack = getattr(definition, "attack", None)
    printed = int(attack) if attack else DEFAULT_MONSTER_ATTACK

    return monster_value(state, ATTACK, monster, printed)


def refill_monsters(context: EffectContext) -> None:
    """
    Reveal cards until the monster slots are full again.

    A monster that leaves — defeated, discarded, replaced by a card — leaves a
    hole, and the rules fill it from the top of the monster deck. Doing it here
    rather than in whatever removed the monster means every way of removing one
    is followed by the same refill.

    The monster deck is not only monsters. An event happens at once and goes to
    the discard pile; a curse attaches to the active player and stays. Neither
    fills the slot, so the reveal continues.
    """
    state = context.state

    while len(state.active_monsters) < state.monster_slots and state.monster_deck.cards:
        card = state.monster_deck.draw()
        kind = getattr(getattr(card, "definition", None), "type", None)

        if kind is CardType.EVENT:
            _resolve_event(context, card)
        elif kind is CardType.CURSE:
            _attach_curse(context, card)
        else:
            state.active_monsters.add_top(card)

            context.emit(EventType.ON_ENTER, source=card)


def _resolve_event(context: EffectContext, card: Any) -> None:
    """
    Let a revealed event happen, then put it in the discard pile.

    The card reaches the discard before its ability resolves, which is where a
    played card goes anyway: the ability is already on its way and holds what it
    needs. Nothing is left half in play.
    """
    state = context.state
    active = state.turn.active_player

    card.controller = active
    card.owner = active

    state.monster_discard.add_top(card)

    context.emit(EventType.ON_PLAY, source=card, controller=active)


def _attach_curse(context: EffectContext, card: Any) -> None:
    """
    Put a revealed curse on the active player.
    """
    context.apply("attach_curse", [context.state.active_player], card=card)
