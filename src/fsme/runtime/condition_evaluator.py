# src/fsme/runtime/condition_evaluator.py

"""
Condition evaluation for Four Souls Multiverse Engine.

Conditions are pure. They read GameState and return a boolean; they never
write, never queue events and never consume randomness. That is what makes it
safe to test an ability before deciding whether it happens at all.

CONDITION_REGISTRY.md lists ``chance`` among the conditions. It is not
implemented here and cannot be: drawing a random value advances the RNG, which
is part of GameState, so a "condition" that rolls would mutate the game while
merely being asked a question. Probabilistic behaviour belongs to an effect.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from fsme.state import GameState, PlayerState

from .ability_context import AbilityContext
from .errors import UnknownConditionError

ConditionFn = Callable[[GameState, AbilityContext, Mapping[str, Any]], bool]

_COMPARISONS: dict[str, Callable[[int, int], bool]] = {
    "==": lambda left, right: left == right,
    "!=": lambda left, right: left != right,
    ">": lambda left, right: left > right,
    ">=": lambda left, right: left >= right,
    "<": lambda left, right: left < right,
    "<=": lambda left, right: left <= right,
}


def _compare(value: int, params: Mapping[str, Any]) -> bool:
    operator = str(params.get("operator", "=="))
    expected = int(params.get("value", 0))

    try:
        comparison = _COMPARISONS[operator]
    except KeyError:
        raise UnknownConditionError(f"unknown operator '{operator}'") from None

    return comparison(value, expected)


def _subject_player(
    state: GameState,
    context: AbilityContext,
    params: Mapping[str, Any],
) -> PlayerState | None:
    """
    Return the player a condition talks about.

    Conditions run before targets are resolved, so the subject is the ability's
    controller unless the card names a player explicitly.
    """
    index = params.get("player", context.controller)

    if index is None or not isinstance(index, int):
        return None

    if not 0 <= index < len(state.players):
        return None

    return state.player(index)


def _subject_monster(
    state: GameState,
    context: AbilityContext,
    params: Mapping[str, Any],
) -> Any | None:
    """
    Return the monster a condition talks about.
    """
    if "monster" in params:
        index = int(params["monster"])

        if 0 <= index < len(state.active_monsters.cards):
            return state.active_monsters.cards[index]

        return None

    monsters = state.active_monsters.cards

    if context.source is not None and context.source in monsters:
        return context.source

    return monsters[-1] if monsters else None


class ConditionEvaluator:
    """
    Evaluates the condition vocabulary used by card definitions.
    """

    def __init__(self) -> None:
        self._conditions: dict[str, ConditionFn] = {}
        self._register_builtin()

    def register(self, name: str, function: ConditionFn) -> None:
        """
        Add a condition implementation.
        """
        if name in self._conditions:
            raise UnknownConditionError(f"condition '{name}' is already registered")

        self._conditions[name] = function

    def names(self) -> frozenset[str]:
        return frozenset(self._conditions)

    def evaluate_all(
        self,
        nodes: Sequence[Any],
        state: GameState,
        context: AbilityContext,
    ) -> bool:
        """
        Evaluate a list of conditions joined by AND.
        """
        return all(self.evaluate(node, state, context) for node in nodes)

    def evaluate(
        self,
        node: Any,
        state: GameState,
        context: AbilityContext,
    ) -> bool:
        """
        Evaluate one condition node.
        """
        name, params = normalise(node)

        if name == "and":
            return self.evaluate_all(params.get("of", ()), state, context)

        if name == "or":
            return any(
                self.evaluate(item, state, context) for item in params.get("of", ())
            )

        if name == "not":
            return not self.evaluate_all(params.get("of", ()), state, context)

        try:
            condition = self._conditions[name]
        except KeyError:
            raise UnknownConditionError(f"unknown condition '{name}'") from None

        return condition(state, context, params)

    def _register_builtin(self) -> None:
        register = self.register

        register("player_alive", _player_alive)
        register("player_dead", _player_dead)
        register("player_active", _player_active)
        register("player_not_active", _player_not_active)
        register("player_has_coins", _player_has_coins)
        register("player_has_loot", _player_has_loot)
        register("player_has_treasure", _player_has_treasure)
        register("player_has_souls", _player_has_souls)
        register("player_hp", _player_hp)

        register("monster_alive", _monster_alive)
        register("monster_dead", _monster_dead)
        register("monster_boss", _monster_boss)
        register("monster_hp", _monster_hp)

        register("dice_equals", _dice_equals)
        register("dice_not_equals", _dice_not_equals)
        register("dice_greater", _dice_greater)
        register("dice_less", _dice_less)
        register("dice_even", _dice_even)
        register("dice_odd", _dice_odd)

        register("item_charged", _item_charged)
        register("item_depleted", _item_depleted)

        register("stack_empty", _stack_empty)
        register("stack_not_empty", _stack_not_empty)
        register("stack_size", _stack_size)

        register("first_turn", _first_turn)
        register("first_attack_roll", _first_attack_roll)
        register("last_effect_did", _last_effect_did)
        register("game_finished", _game_finished)


def normalise(node: Any) -> tuple[str, Mapping[str, Any]]:
    """
    Reduce every accepted condition spelling to a name and parameters.

    Accepted forms::

        "player_alive"
        {"player_has_coins": 3}
        {"player_hp": {"operator": "<", "value": 2}}
        {"condition": "player_hp", "operator": "<", "value": 2}
        {"not": ["player_alive"]}
    """
    if isinstance(node, str):
        return node, {}

    if not isinstance(node, Mapping):
        raise UnknownConditionError(f"invalid condition node: {node!r}")

    if "condition" in node:
        params = {key: value for key, value in node.items() if key != "condition"}

        return str(node["condition"]), params

    if len(node) != 1:
        raise UnknownConditionError(
            f"condition node must name exactly one condition: {dict(node)!r}"
        )

    name, value = next(iter(node.items()))

    if name in {"and", "or", "not"}:
        items = value if isinstance(value, (list, tuple)) else [value]

        return str(name), {"of": tuple(items)}

    if isinstance(value, Mapping):
        return str(name), value

    return str(name), {"value": value}


def _player_alive(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    player = _subject_player(state, context, params)

    return player is not None and player.alive


def _player_dead(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    player = _subject_player(state, context, params)

    return player is not None and not player.alive


def _player_active(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    player = _subject_player(state, context, params)

    return player is not None and player.player_id == state.turn.active_player


def _player_not_active(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    return not _player_active(state, context, params)


def _player_has_coins(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    player = _subject_player(state, context, params)
    amount = int(params.get("amount", params.get("value", 1)))

    return player is not None and player.pennies >= amount


def _player_has_loot(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    player = _subject_player(state, context, params)
    count = int(params.get("count", params.get("value", 1)))

    return player is not None and player.hand_size >= count


def _player_has_treasure(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    player = _subject_player(state, context, params)
    count = int(params.get("count", params.get("value", 1)))

    return player is not None and player.treasure_count >= count


def _player_has_souls(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    player = _subject_player(state, context, params)
    count = int(params.get("count", params.get("value", 1)))

    return player is not None and player.soul_count >= count


def _player_hp(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    player = _subject_player(state, context, params)

    return player is not None and _compare(player.hp, params)


def _monster_alive(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    monster = _subject_monster(state, context, params)

    return monster is not None and bool(getattr(monster, "alive", False))


def _monster_dead(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    monster = _subject_monster(state, context, params)

    return monster is not None and not getattr(monster, "alive", False)


def _monster_boss(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    monster = _subject_monster(state, context, params)
    has_tag = getattr(monster, "has_tag", None)

    return callable(has_tag) and bool(has_tag("boss"))


def _monster_hp(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    monster = _subject_monster(state, context, params)

    if monster is None or getattr(monster, "hp", None) is None:
        return False

    return _compare(int(monster.hp), params)


def _last_effect_did(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    """
    True when the effect just before this one actually did something.

    "Destroy an item you control. If you do, steal an item" turns on whether
    the destruction happened, and an effect reports that by what it returns:
    zero items destroyed is an instruction that could not be carried out.
    """
    value = context.last_value
    done = int(value) if isinstance(value, int) else 0

    return _compare(done, dict(params) or {"operator": ">", "value": 0})


def _first_attack_roll(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    """
    True while the turn's first attack roll is being resolved.

    The roll is counted as it is made, so the damage it leads to is still
    looking at roll number one.
    """
    return state.turn.attack_rolls <= 1


def _dice_value(context: AbilityContext) -> int | None:
    value = context.get("dice")

    return int(value) if isinstance(value, int) else None


def _dice_equals(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    value = _dice_value(context)

    return value is not None and value == int(params.get("value", 0))


def _dice_not_equals(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    value = _dice_value(context)

    return value is not None and value != int(params.get("value", 0))


def _dice_greater(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    value = _dice_value(context)

    return value is not None and value > int(params.get("value", 0))


def _dice_less(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    value = _dice_value(context)

    return value is not None and value < int(params.get("value", 0))


def _dice_even(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    value = _dice_value(context)

    return value is not None and value % 2 == 0


def _dice_odd(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    value = _dice_value(context)

    return value is not None and value % 2 == 1


def _item_charged(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    source = context.source

    return source is not None and not getattr(source, "tapped", False)


def _item_depleted(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    return not _item_charged(state, context, params)


def _stack_empty(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    return state.stack.is_empty()


def _stack_not_empty(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    return not state.stack.is_empty()


def _stack_size(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    return _compare(len(state.stack), params)


def _first_turn(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    return state.turn.turn_number == 1


def _game_finished(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    return state.game_over
