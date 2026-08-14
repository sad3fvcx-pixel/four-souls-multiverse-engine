# src/fsme/rules/__init__.py

"""
The official Four Souls rules, expressed as command handlers.

A handler answers two questions: whether an action is legal, and what happens
when it is taken. Nothing here knows about a specific card — cards describe
themselves through the Effect DSL, and these rules describe the game they are
played in.
"""

from __future__ import annotations

from fsme.commands import CommandRegistry, CommandType
from fsme.stack import (
    ADVANCE_TURN,
    COMBAT_ROUND,
    COMBAT_STRIKE,
    DISCARD_PLAYED_LOOT,
    DISCARD_TO_HAND_LIMIT,
)
from fsme.stack import (
    LOOT_STEP as LOOT_STEP_LABEL,
)

from .activation import ActivateTreasureHandler
from .combat import (
    AttackHandler,
    combat_round,
    combat_strike,
    end_combat,
    refill_monsters,
)
from .constants import (
    ATTACKS_PER_TURN,
    BASE_PLAYER_ATTACK,
    BASE_PLAYER_HP,
    DICE_SIDES,
    HAND_LIMIT,
    LOOT_PLAYS_PER_TURN,
    MONSTER_SLOTS,
    SHOP_SLOTS,
    SOULS_TO_WIN,
    STARTING_HAND_SIZE,
    TREASURE_COST,
)
from .counters import record_trigger, times_this_turn, trigger_key
from .death import DEATH_PENALTY, kill_player, restore_everyone
from .decisions import ChooseTargetHandler
from .errors import RuleError, RuleRegistrationError, UnknownRuleError
from .loot import PlayLootHandler, discard_played_loot
from .obligations import owed_by, refuse_to_stop
from .priority import PassPriorityHandler
from .procedures import ProcedureRegistry, StackProcedure
from .restrictions import ACTIONS, forbidden_by, refuse
from .setup import SetupError, new_game
from .shop import BuyTreasureHandler, refill_shop
from .statics import (
    ATTACK,
    ATTACKS,
    DIFFICULTY,
    LOOT_PLAYS,
    LOOT_STEP,
    MAX_HP,
    ROLL,
    STATS,
    bonus,
    cards_in_play,
    expire_turn_modifiers,
    monster_value,
    refresh_derived,
    static_value,
)
from .turn import (
    FIRST_PLAYER,
    EndPhaseHandler,
    EndTurnHandler,
    StartGameHandler,
    advance_turn,
    discard_to_hand_limit,
    first_seat,
    loot_step,
)


def default_command_registry() -> CommandRegistry:
    """
    Build the command registry of the official rule set.

    """
    registry = CommandRegistry()

    registry.register(CommandType.START_GAME, StartGameHandler())
    registry.register(CommandType.END_PHASE, EndPhaseHandler())
    registry.register(CommandType.END_TURN, EndTurnHandler())
    registry.register(CommandType.PLAY_LOOT, PlayLootHandler())
    registry.register(CommandType.ACTIVATE_TREASURE, ActivateTreasureHandler())
    registry.register(CommandType.BUY_TREASURE, BuyTreasureHandler())
    registry.register(CommandType.ATTACK, AttackHandler())
    registry.register(CommandType.PASS_PRIORITY, PassPriorityHandler())
    registry.register(CommandType.CHOOSE_TARGET, ChooseTargetHandler())

    return registry


def default_procedure_registry() -> ProcedureRegistry:
    """
    Build the registry of stack procedures the official rules use.
    """
    registry = ProcedureRegistry()

    registry.register(COMBAT_ROUND, combat_round)
    registry.register(COMBAT_STRIKE, combat_strike)
    registry.register(DISCARD_PLAYED_LOOT, discard_played_loot)
    registry.register(ADVANCE_TURN, advance_turn)
    registry.register(LOOT_STEP_LABEL, loot_step)

    return registry


__all__ = [
    "ActivateTreasureHandler",
    "AttackHandler",
    "BuyTreasureHandler",
    "ChooseTargetHandler",
    "EndPhaseHandler",
    "EndTurnHandler",
    "PassPriorityHandler",
    "PlayLootHandler",
    "SetupError",
    "DEATH_PENALTY",
    "kill_player",
    "restore_everyone",
    "bonus",
    "cards_in_play",
    "expire_turn_modifiers",
    "monster_value",
    "record_trigger",
    "refresh_derived",
    "ACTIONS",
    "forbidden_by",
    "owed_by",
    "refuse_to_stop",
    "refuse",
    "static_value",
    "times_this_turn",
    "trigger_key",
    "ATTACK",
    "ATTACKS",
    "LOOT_PLAYS",
    "LOOT_STEP",
    "DIFFICULTY",
    "MAX_HP",
    "ROLL",
    "STATS",
    "ProcedureRegistry",
    "StackProcedure",
    "StartGameHandler",
    "FIRST_PLAYER",
    "first_seat",
    "ADVANCE_TURN",
    "COMBAT_ROUND",
    "COMBAT_STRIKE",
    "DISCARD_TO_HAND_LIMIT",
    "advance_turn",
    "discard_to_hand_limit",
    "DISCARD_PLAYED_LOOT",
    "combat_round",
    "default_command_registry",
    "new_game",
    "default_procedure_registry",
    "discard_played_loot",
    "end_combat",
    "refill_monsters",
    "refill_shop",
    "RuleError",
    "RuleRegistrationError",
    "UnknownRuleError",
    "ATTACKS_PER_TURN",
    "BASE_PLAYER_ATTACK",
    "BASE_PLAYER_HP",
    "DICE_SIDES",
    "HAND_LIMIT",
    "LOOT_PLAYS_PER_TURN",
    "MONSTER_SLOTS",
    "SHOP_SLOTS",
    "SOULS_TO_WIN",
    "STARTING_HAND_SIZE",
    "TREASURE_COST",
]
