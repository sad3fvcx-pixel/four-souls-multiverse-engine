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

        register("attack_roll", _attack_roll)
        register("is_attacked", _is_attacked)
        register("card_counters", _card_counters)
        register("combat_damage", _combat_damage)
        register("is_damage_source", _is_event_source)
        register("is_event_source", _is_event_source)
        register("event_value", _event_value)
        register("is_damage_target", _is_damage_target)
        register("is_damage_actor", _is_damage_actor)
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
        register("nth_time_this_turn", _nth_time_this_turn)
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


def _has(
    player: Any,
    amount: int,
    params: Mapping[str, Any],
) -> bool:
    """
    Compare what a player has with what the card asks about.

    "Has 3 cents" means three or more, which is why that is the default. A card
    that means something else — "if you have 0 cents" — says so with an
    operator, and then the comparison is the one it named.
    """
    if player is None:
        return False

    if "operator" not in params:
        return amount >= int(params.get("amount", params.get("count", params.get("value", 1))))

    return _compare(amount, params)


def _player_has_coins(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    return _has(_subject_player(state, context, params), _pennies(state, context, params), params)


def _pennies(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> int:
    player = _subject_player(state, context, params)

    return int(player.pennies) if player is not None else 0


def _player_has_loot(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    player = _subject_player(state, context, params)

    return _has(player, int(player.hand_size) if player else 0, params)


def _player_has_treasure(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    """
    Compare how many items a player controls with what the card asks about.

    ``tag`` narrows it to one family of items — "2 or more Guppy items" is not
    two or more items.
    """
    player = _subject_player(state, context, params)

    if player is None:
        return False

    tag = params.get("tag")

    if tag is None:
        held = int(player.treasure_count)
    else:
        held = sum(
            1
            for card in player.treasures.cards
            if str(tag) in getattr(getattr(card, "definition", None), "tags", ())
        )

    return _has(player, held, params)


def _player_has_souls(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    player = _subject_player(state, context, params)

    return _has(player, int(player.soul_count) if player else 0, params)


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


TIMES_THIS_TURN = "__times_this_turn__"
"""
Where the runtime leaves the occurrence number an ability is looking at.

A condition may not count anything itself — counting is a change to the game,
and conditions only read — so the count is made when the trigger matches and
handed to the condition along with everything else it knows.
"""


def _nth_time_this_turn(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    """
    True on the occurrence a card is talking about.

    "The first time you take damage each turn" is occurrence one.
    "Every other time this takes damage each turn" is ``{"every": 2}``: the
    second, the fourth, and so on, counting from the start of the turn.
    """
    counted = context.get(TIMES_THIS_TURN)
    number = int(counted) if isinstance(counted, int) else 0

    every = params.get("every")

    if every is not None:
        return int(every) > 0 and number % int(every) == 0

    return _compare(number, dict(params) or {"operator": "==", "value": 1})


def _dice_value(context: AbilityContext) -> int | None:
    """
    The roll a condition is talking about.

    An ability that rolled its own die reads that. An ability reacting to
    somebody else's roll — "each time a player rolls a 6" — has no die of its
    own and reads the one the event is announcing.
    """
    value = context.get("dice")

    if isinstance(value, int):
        return value

    if context.event is not None:
        for key in ("value", "roll"):
            rolled = context.event.get(key)

            if isinstance(rolled, int):
                return rolled

    return None


def _combat_damage(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    """
    True when the damage being answered came from an attack.
    """
    return bool(context.event is not None and context.event.get("combat", False))


def _event_value(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    """
    Compare something the event carries with what the card expects.

    Events carry more than the engine has conditions for, and a card that cares
    about one of those values should not need a condition of its own written
    for it. "When you prevent damage this way" is this: the announcement says
    which promise was spent, and the card asks whether it was theirs.
    """
    if context.event is None:
        return False

    carried = context.event.get(str(params.get("key", "")))
    expected = params.get("value")

    if isinstance(expected, int) and not isinstance(expected, bool):
        number = int(carried) if isinstance(carried, int) else 0

        return _compare(number, params)

    return bool(carried == expected)


def _is_event_source(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    """
    True when this card is what the event is about.

    "When another monster dies" is this condition negated: the card asking is
    in play, the event names a monster, and the two must not be the same one.
    Damage asks the same question and calls it ``is_damage_source``, which is
    the same test under the name the damage cards use.
    """
    return bool(
        context.event is not None
        and context.source is not None
        and context.event.source is context.source
    )


def _is_damage_target(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    """
    True when this card is what the damage landed on.
    """
    return bool(
        context.event is not None
        and context.source is not None
        and any(target is context.source for target in context.event.targets)
    )


def _is_damage_actor(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    """
    True when this card's controller is who dealt the damage.

    "Each time you deal combat damage to a monster" is about the player holding
    the card, not about the card itself: the item does not swing, its owner does.
    """
    return bool(
        context.event is not None
        and context.controller is not None
        and context.event.get("actor") == context.controller
    )


def _card_counters(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    """
    Compare the counters on this card with a number.
    """
    source = context.source

    if source is None:
        return False

    counters = getattr(source, "counters", {})
    name = str(params.get("counter", "charge"))

    return _compare(int(counters.get(name, 0)), dict(params))


def _is_attacked(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    """
    True when the monster this ability belongs to is the one under attack.

    A monster's ability talks about its own fight. Two monsters are in play at
    once, and a roll made against one of them is not a roll against the other.
    """
    return bool(
        state.combat.active
        and context.source is not None
        and state.combat.monster is context.source
    )


def _attack_roll(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    """
    True when the roll being answered is an attack roll.

    Cards distinguish the two: "+1 to attack rolls" is not "+1 to rolls", and
    only the roll itself knows which kind it is.
    """
    return bool(context.event is not None and context.event.get("attack", False))


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
