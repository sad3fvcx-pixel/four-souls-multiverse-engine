# src/fsme/rules/death.py

"""
What happens when a player dies.

COMPREHENSIVE_RULES.md §10: a death goes into the queue, the curses on the
player are discarded, and then the penalty is paid — a loot card, a cent, an
item, every activated item and the character deactivated, and the turn ended if
it was theirs. The player stays dead until everyone heals at the end of the
turn.

The penalty is written in the same language as a card, and for the same reason
as the hand limit is: the player chooses which loot card and which item they
lose, and asking a question mid-resolution is something abilities already know
how to do.
"""

from __future__ import annotations

from fsme.cards import Ability
from fsme.effects import EffectContext
from fsme.events import EventType
from fsme.stack import StackItem, StackItemType
from fsme.state import GameState, PlayerState

DEATH_PENALTY = "death_penalty"
"""The stack object that makes a dead player pay."""


def death_penalty_ability() -> Ability:
    """
    Build the penalty a dying player owes.

    Every part of it is "as much as you can": a player with no loot card
    discards none, and a player whose only item is eternal destroys none. That
    is how the rules read an instruction that cannot be carried out, and it is
    what the targets do when there is nothing to choose from.
    """
    return Ability(
        trigger=str(EventType.DEATH_PENALTY),
        targets=(
            {"target_loot": {"as": "given_up", "prompt": "Discard a loot card."}},
            {
                "target_treasure": {
                    "owner": "controller",
                    "exclude_eternal": True,
                    "as": "broken",
                    "prompt": "Destroy one of your items.",
                }
            },
        ),
        effects=(
            {"effect": "discard_cards", "target": "given_up"},
            {"effect": "lose_coins", "amount": 1},
            {"effect": "destroy_treasure", "target": "broken"},
            {
                "effect": "deactivate",
                "target": {"all_treasures": {"owner": "controller"}},
            },
            {"effect": "deactivate", "target": "character"},
            {"if": ["player_active"], "then": [{"end_turn": {}}]},
        ),
        description=(
            "Discard a loot card, lose 1¢, destroy an item, deactivate your "
            "items and your character, and end your turn if it is yours."
        ),
    )


def kill_player(context: EffectContext, player: PlayerState) -> None:
    """
    Carry out a death: announce it, clear the curses, and owe the penalty.
    """
    from .combat import end_combat

    player.kill()
    player.died_this_turn = True

    if context.state.combat.attacker == player.player_id:
        # COMPREHENSIVE_RULES.md §7: an attack ends the moment either fighter
        # dies, and the rounds still queued have nobody to fight.
        end_combat(context)

    context.emit(
        EventType.PLAYER_DIED,
        controller=player.player_id,
        targets=[player],
    )

    _discard_curses(context, player)

    context.emit(
        EventType.BEFORE_DEATH_PENALTY,
        controller=player.player_id,
        targets=[player],
    )

    context.push(
        StackItem(
            kind=StackItemType.ENGINE_EFFECT,
            label=DEATH_PENALTY,
            ability=death_penalty_ability(),
            source=player.character,
            controller=player.player_id,
        )
    )


def _discard_curses(context: EffectContext, player: PlayerState) -> None:
    """
    A curse is on the player, not on the game: it goes when they do.
    """
    cursed = list(player.curses.cards)

    if not cursed:
        return

    context.apply("remove_curse", [player])


def restore_everyone(context: EffectContext) -> None:
    """
    Heal every player and every monster, and bring back whoever died.

    COMPREHENSIVE_RULES.md §3.3: this happens in the end phase, before the
    effects that last "till end of turn" stop applying — which is why a player
    who bought hit points this turn heals to the larger number and only then
    loses the difference.
    """
    state = context.state

    for player in state.players:
        if not player.alive:
            context.apply("revive", [player], hp=max(1, player.max_hp))

            continue

        if player.hp < player.max_hp:
            context.apply("heal", [player], full=True)

    for monster in state.active_monsters.cards:
        printed = getattr(getattr(monster, "definition", None), "health", None)

        if printed is None or not getattr(monster, "alive", False):
            continue

        if int(monster.hp or 0) < int(printed):
            context.apply("heal", [monster], amount=int(printed))


def dies_again(state: GameState, player: PlayerState) -> bool:
    """
    Whether this player may die again right now.

    A player dies once per turn. One who is standing at no hit points because
    they already died — or because a card prevented the death — is not killed
    a second time by the same nothing.
    """
    return not player.died_this_turn
