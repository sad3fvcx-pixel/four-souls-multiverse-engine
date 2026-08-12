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

from .activation import ActivateTreasureHandler
from .combat import COMBAT_ROUND, AttackHandler, combat_round, end_combat
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
from .decisions import ChooseTargetHandler
from .errors import RuleError, RuleRegistrationError, UnknownRuleError
from .loot import DISCARD_PLAYED_LOOT, PlayLootHandler, discard_played_loot
from .priority import PassPriorityHandler
from .procedures import ProcedureRegistry, StackProcedure
from .setup import SetupError, new_game
from .shop import BuyTreasureHandler, refill_shop
from .turn import EndPhaseHandler, EndTurnHandler, StartGameHandler


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
    registry.register(DISCARD_PLAYED_LOOT, discard_played_loot)

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
    "ProcedureRegistry",
    "StackProcedure",
    "StartGameHandler",
    "COMBAT_ROUND",
    "DISCARD_PLAYED_LOOT",
    "combat_round",
    "default_command_registry",
    "new_game",
    "default_procedure_registry",
    "discard_played_loot",
    "end_combat",
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
