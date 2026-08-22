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
from types import MappingProxyType
from typing import Any

from fsme.content.vocabulary import (
    OPEN,
    UNCHECKED,
    VALUES,
    ConditionShape,
    ParamShape,
)
from fsme.state import GameState, PlayerState

from .ability_context import AbilityContext
from .errors import UnknownConditionError

ConditionFn = Callable[[GameState, AbilityContext, Mapping[str, Any]], bool]

WHOLE = "a whole number"
TEXT = "text"


def _shape(*parts: Mapping[str, ParamShape]) -> dict[str, ParamShape]:
    """
    Join the parameter sets a condition inherits from the helpers it calls.

    Every condition here has the same signature, so what one takes cannot be
    read off it the way an effect's can. What can be read is which helper it
    hands its parameters to, and the helper is where the parameters are
    actually understood — so that is where each set is written, one per
    helper, beside the code that reads it.
    """
    joined: dict[str, ParamShape] = {}

    for part in parts:
        joined.update(part)

    return joined

_COMPARISONS: dict[str, Callable[[int, int], bool]] = {
    "==": lambda left, right: left == right,
    "!=": lambda left, right: left != right,
    ">": lambda left, right: left > right,
    ">=": lambda left, right: left >= right,
    "<": lambda left, right: left < right,
    "<=": lambda left, right: left <= right,
}


COMPARISON = {
    "operator": ParamShape(
        "operator", TEXT, values=tuple(_COMPARISONS), describes="how to compare"
    ),
    "value": ParamShape("value", WHOLE, describes="what to compare against"),
}
"""
What ``_compare`` reads: how to compare, and what to compare against.

The operators are the keys of the table above rather than a list written out
again, so a comparison the engine cannot make is refused at load time by the
same fact that makes it fail at run time.
"""


def _compare(value: int, params: Mapping[str, Any]) -> bool:
    operator = str(params.get("operator", "=="))
    expected = int(params.get("value", 0))

    try:
        comparison = _COMPARISONS[operator]
    except KeyError:
        raise UnknownConditionError(f"unknown operator '{operator}'") from None

    return comparison(value, expected)


SUBJECT_PLAYER = {"player": ParamShape("player", WHOLE, least=0)}
"""
What ``_subject_player`` reads: which seat, when the card names one.
"""


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


SUBJECT_MONSTER = {"monster": ParamShape("monster", WHOLE, least=0)}
"""
What ``_subject_monster`` reads: which slot, when the card names one.
"""


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
        self._shapes: dict[str, ConditionShape] = {}
        self._register_builtin()

    def register(
        self,
        name: str,
        function: ConditionFn,
        takes: Mapping[str, ParamShape] | None = None,
        describes: str = "",
    ) -> None:
        """
        Add a condition implementation, and say what it takes and asks.

        ``describes`` is the question in a person's words. Anything offering
        an author a list of conditions had no way to label them before this,
        and would have had to keep words of its own — a second table, and
        second tables drift.

        ``takes`` is what a card file may write inside this condition. Leaving
        it out does not mean the condition accepts anything: it means whoever
        registered it did not say, so nothing outside a game may judge its
        parameters. Every condition the engine ships says.
        """
        if name in self._conditions:
            raise UnknownConditionError(f"condition '{name}' is already registered")

        self._conditions[name] = function
        self._shapes[name] = ConditionShape(
            name=name,
            params=MappingProxyType(dict(takes or {})),
            open_ended=takes is None,
            describes=describes,
        )

    def names(self) -> frozenset[str]:
        return frozenset(self._conditions)

    def shapes(self) -> Mapping[str, ConditionShape]:
        """
        What each condition takes, as plain data.

        The functions stay here. What leaves is names and kinds, because the
        content pipeline that asks this question runs before a game exists and
        must not be handed anything that could start one.
        """
        return MappingProxyType(dict(self._shapes))

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

        register("player_alive", _player_alive, SUBJECT_PLAYER, "the player is alive")
        register("player_dead", _player_dead, SUBJECT_PLAYER, "the player is dead")
        register("player_active", _player_active, SUBJECT_PLAYER, "it is that player's turn")
        register(
            "player_not_active",
            _player_not_active, SUBJECT_PLAYER,
            "it is not that player's turn",
        )
        register(
            "player_has_coins",
            _player_has_coins, HAS_SOMETHING,
            "the player has that many cents",
        )
        register(
            "player_has_loot",
            _player_has_loot, HAS_SOMETHING,
            "the player holds that many loot cards",
        )
        register(
            "player_has_treasure",
            _player_has_treasure, HAS_TREASURE,
            "the player controls that many items",
        )
        register(
            "player_has_souls",
            _player_has_souls, HAS_SOMETHING,
            "the player has that many souls",
        )
        register("player_hp", _player_hp, ABOUT_A_PLAYER, "the player's health compares as you say")

        register("monster_alive", _monster_alive, SUBJECT_MONSTER, "the monster is still alive")
        register("monster_dead", _monster_dead, SUBJECT_MONSTER, "the monster is dead")
        register("monster_boss", _monster_boss, SUBJECT_MONSTER, "the monster is a boss")
        register(
            "monster_hp",
            _monster_hp, ABOUT_A_MONSTER,
            "the monster's health compares as you say",
        )

        register("attack_roll", _attack_roll, NOTHING, "the roll being answered is an attack roll")
        register("is_attacked", _is_attacked, NOTHING, "this monster is the one under attack")
        register(
            "card_counters",
            _card_counters, COUNTERS,
            "the counters on this card compare as you say",
        )
        register(
            "player_counters",
            _player_counters, PLAYER_COUNTERS,
            "the counters on the player compare as you say",
        )
        register("card_in_zone", _card_in_zone, IN_ZONE, "this card is in the place you name")
        register("combat_damage", _combat_damage, NOTHING, "the damage came from an attack")
        register(
            "is_damage_source",
            _is_event_source, NOTHING,
            "this card is what the damage came from",
        )
        register(
            "is_event_source",
            _is_event_source, NOTHING,
            "this card is what the event is about",
        )
        register(
            "event_value",
            _event_value, EVENT_VALUE,
            "something the event carries is what you expect",
        )
        register(
            "values_equal",
            _values_equal, NAMED_VALUES,
            "two things kept earlier are the same",
        )
        register(
            "is_damage_target",
            _is_damage_target, NOTHING,
            "this card is what the damage landed on",
        )
        register(
            "is_damage_actor",
            _is_damage_actor, NOTHING,
            "this card's controller dealt the damage",
        )
        register("dice_equals", _dice_equals, DICE, "the roll is exactly that")
        register("dice_not_equals", _dice_not_equals, DICE, "the roll is anything but that")
        register("dice_greater", _dice_greater, DICE, "the roll is higher than that")
        register("dice_less", _dice_less, DICE, "the roll is lower than that")
        register("dice_even", _dice_even, NOTHING, "the roll is even")
        register("dice_odd", _dice_odd, NOTHING, "the roll is odd")

        register("item_charged", _item_charged, NOTHING, "this item is ready to use")
        register("item_depleted", _item_depleted, NOTHING, "this item has been used")

        register("stack_empty", _stack_empty, NOTHING, "nothing is waiting to resolve")
        register("stack_not_empty", _stack_not_empty, NOTHING, "something is waiting to resolve")
        register(
            "stack_size",
            _stack_size, COMPARISON,
            "the number waiting to resolve compares as you say",
        )

        register("first_turn", _first_turn, NOTHING, "it is the first turn of the game")
        register(
            "first_attack_roll",
            _first_attack_roll, NOTHING,
            "this is the turn's first attack roll",
        )
        register(
            "nth_time_this_turn",
            _nth_time_this_turn, NTH_TIME_SHAPE,
            "this is the occurrence you mean this turn",
        )
        register(
            "last_effect_did",
            _last_effect_did, COMPARISON,
            "the effect before this one did something",
        )
        register("game_finished", _game_finished, NOTHING, "the game is over")


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


HOW_MANY = _shape(
    COMPARISON,
    {
        "amount": ParamShape("amount", WHOLE),
        "count": ParamShape("count", WHOLE),
    },
)
"""
What ``_has`` reads: a number, however the card chose to spell it.
"""


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


NOTHING: dict[str, ParamShape] = {}
"""
A condition that reads nothing. A card writing parameters into one is not
narrowing it — it is being ignored, which is worth saying before a game.
"""

ABOUT_A_PLAYER = _shape(SUBJECT_PLAYER, COMPARISON)
HAS_SOMETHING = _shape(SUBJECT_PLAYER, HOW_MANY)
HAS_TREASURE = _shape(HAS_SOMETHING, {"tag": ParamShape("tag", TEXT)})
ABOUT_A_MONSTER = _shape(SUBJECT_MONSTER, COMPARISON)
COUNTERS = _shape(COMPARISON, {"counter": ParamShape("counter", TEXT)})
PLAYER_COUNTERS = _shape(SUBJECT_PLAYER, COUNTERS)
IN_ZONE = {"zone": ParamShape("zone", TEXT)}
NAMED_VALUES = {
    "of": ParamShape(
        "of",
        UNCHECKED,
        refers_to=VALUES,
        describes="the name an earlier step stored the value under",
    )
}
"""
What ``values_equal`` reads, and the one place ``of`` means the other thing.

Everywhere else ``of`` names a group of objects an ability chose. Here it
names what an ability *stored* — two dice kept apart under names so that they
can be compared. The two namespaces never meet, and a checker that read `of`
as one thing would be wrong about the other.
"""
EVENT_VALUE = _shape(
    COMPARISON,
    {
        "key": ParamShape(
            "key", TEXT, required=True, describes="which of the event's values"
        ),
        "value": ParamShape(
            "value", UNCHECKED, role=OPEN, describes="what it should be"
        ),
    },
)
"""
The one condition whose ``value`` this layer cannot judge.

Events carry numbers, flags and names, and the card is comparing against
whichever the event holds. A rule that made this a number would refuse
``{"key": "hit", "value": false}``, which is a card asking a fair question.
"""


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


NTH_TIME = "nth_time_this_turn"
"""
The condition that asks which occurrence this is.
"""

TIMES_THIS_TURN = "__times_this_turn__"
"""
Where the runtime leaves the occurrence number an ability is looking at.

A condition may not count anything itself — counting is a change to the game,
and conditions only read — so the count is made when the trigger matches and
handed to the condition along with everything else it knows.
"""


NTH_TIME_SHAPE = _shape(
    COMPARISON, {"every": ParamShape("every", WHOLE, least=1)}
)
"""
Every other time is a period, and a period of zero is not a period.
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


DICE = {"value": ParamShape("value", WHOLE, describes="the number on the face")}
"""
What the four ``dice_`` comparisons read: the number on the face.

Not ``COMPARISON``: each of them names its own comparison, so an operator
written on one would be silently ignored rather than obeyed.
"""


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


def _values_equal(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    """
    True when everything the ability stored under these names is the same.

    "They roll 2 dice- if the results are the same" is two rolls kept apart and
    then compared, which is why the rolls had to be named in the first place.
    """
    names = params.get("of", ())

    if isinstance(names, str):
        names = [names]

    if len(names) < 2:
        return False

    values = [context.get(str(name)) for name in names]

    if any(value is None for value in values):
        # Nothing was stored under one of these names, and two absences are
        # not a match: a comparison nobody set up is simply false.
        return False

    return all(value == values[0] for value in values[1:])


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


def _player_counters(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    """
    Compare the counters on a player with a number.

    A counter on a player is not on any card they own: it stays when their
    items are destroyed and travels with nothing. Which player is asked about
    is the ability's controller unless the card names somebody else.
    """
    seat = params.get("player", context.controller)

    if seat is None or not 0 <= int(seat) < len(state.players):
        return False

    counters = state.player(int(seat)).counters
    name = str(params.get("counter", "charge"))

    return _compare(int(counters.get(name, 0)), dict(params))


def _card_in_zone(
    state: GameState, context: AbilityContext, params: Mapping[str, Any]
) -> bool:
    """
    Whether the card this ability belongs to is sitting in a named zone.

    An ability that only works from the discard pile has to be able to ask —
    "when a player dies and this is in discard" is a card watching the table
    from somewhere it is not in play.
    """
    source = context.source

    if source is None:
        return False

    zone = getattr(state, str(params.get("zone", "")), None)

    if zone is None:
        return False

    return any(card is source for card in getattr(zone, "cards", ()))


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
