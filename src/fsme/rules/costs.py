# src/fsme/rules/costs.py

"""
What an activated ability costs, and whether it can be paid.

Four Souls prints two kinds of activated ability. ``↷`` taps the item: the cost
is the item's own readiness, and it is the default. ``$`` charges something
else — cents, a discarded card, a counter — and leaves the item untapped, which
is why an item with a paid ability can be used more than once in a turn.

Checking and paying are separate on purpose. An ability nobody can afford must
be refused before anything happens to the game, and a command that is refused
must leave no trace at all.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fsme.cards import Ability
from fsme.effects import EffectContext
from fsme.state import GameState, PlayerState

TAP = "tap"
COINS = "coins"
DISCARD = "discard"
COUNTERS = "counters"
HP = "hp"

KINDS = (TAP, COINS, DISCARD, COUNTERS, HP)


def cost_of(ability: Ability) -> Mapping[str, Any]:
    """
    Return what an ability costs, filling in the unwritten default.

    An activated ability with nothing written is a ``↷`` ability: tapping is
    what most items charge, and the cards that charge something else say so.
    """
    return ability.cost if ability.cost else {TAP: True}


def unpayable(
    ability: Ability,
    card: Any,
    player: PlayerState,
    state: GameState,
) -> str | None:
    """
    Return why this ability cannot be paid for, or None if it can.
    """
    cost = cost_of(ability)

    for kind in cost:
        if kind not in KINDS:
            return f"unknown cost '{kind}'"

    if cost.get(TAP) and getattr(card, "tapped", False):
        return f"'{_name(card)}' is already tapped"

    coins = int(cost.get(COINS, 0))

    if coins > player.pennies:
        return f"paying {coins}¢ needs {coins - player.pennies}¢ more"

    cards = int(cost.get(DISCARD, 0))

    if cards > player.hand_size:
        return f"discarding {cards} loot card(s) needs a bigger hand"

    counters = int(cost.get(COUNTERS, 0))

    if counters > int(getattr(card, "counters", {}).get("charge", 0)):
        return f"'{_name(card)}' does not have {counters} counters"

    hp = int(cost.get(HP, 0))

    if hp >= player.hp:
        # Paying the last hit point would be paying with your life, which is
        # not what "pay 1 HP" offers.
        return f"paying {hp} HP needs more than {player.hp} hit point(s)"

    return None


def pay(ability: Ability, card: Any, context: EffectContext) -> None:
    """
    Pay an ability's cost.

    Only ever called after :func:`unpayable` has said it can be paid, so a
    half-paid cost is not a state the game can reach.
    """
    cost = cost_of(ability)
    state = context.state

    if context.actor is None:
        return

    player = state.player(context.actor)

    if cost.get(TAP):
        context.apply("deactivate", [card])

    coins = int(cost.get(COINS, 0))

    if coins:
        context.apply("lose_coins", [player], amount=coins)

    cards = int(cost.get(DISCARD, 0))

    if cards:
        context.apply("discard_loot", [player], count=cards)

    counters = int(cost.get(COUNTERS, 0))

    if counters:
        context.apply("add_counter", [card], counter="charge", amount=-counters)

    hp = int(cost.get(HP, 0))

    if hp:
        context.apply("deal_damage", [player], amount=hp)


def _name(card: Any) -> str:
    return str(getattr(card, "name", card))
