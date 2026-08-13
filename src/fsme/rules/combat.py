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

from fsme.commands import Command
from fsme.effects import EffectContext
from fsme.effects.builtin.dice import rolled
from fsme.events import EventType
from fsme.stack import StackItem, StackItemType
from fsme.state import GamePhase, GameState

from .constants import BASE_PLAYER_ATTACK, DICE_SIDES
from .statics import ATTACK, static_value

COMBAT_ROUND = "combat_round"

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

    roll = rolled(context, DICE_SIDES)
    required = _required_roll(monster)

    context.emit(
        EventType.AFTER_ATTACK_ROLL,
        source=monster,
        controller=attacker.player_id,
        value=roll,
        required=required,
        hit=roll >= required,
    )

    if roll >= required:
        damage = static_value(
            state, ATTACK, attacker.player_id, BASE_PLAYER_ATTACK
        )

        context.apply("deal_damage", [monster], amount=damage)
    else:
        context.apply("deal_damage", [attacker], amount=_monster_attack(monster))

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


def _required_roll(monster: Any) -> int:
    definition = getattr(monster, "definition", None)
    required = getattr(definition, "roll", None)

    return int(required) if required else DEFAULT_MONSTER_ROLL


def _monster_attack(monster: Any) -> int:
    definition = getattr(monster, "definition", None)
    attack = getattr(definition, "attack", None)

    return int(attack) if attack else DEFAULT_MONSTER_ATTACK
