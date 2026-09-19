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
from fsme.effects.builtin.decks import draw_from
from fsme.effects.builtin.dice import natural_roll
from fsme.events import EventType
from fsme.stack import (
    ATTACK_DECLARATION,
    COMBAT_ROUND,
    COMBAT_STRIKE,
    StackItem,
    StackItemType,
)
from fsme.state import GamePhase, GameState
from fsme.state.obligations import MONSTER_DECK

from .constants import BASE_PLAYER_ATTACK, DICE_SIDES, STALLED_COMBAT_ROUNDS
from .obligations import pay as pay_obligation
from .restrictions import ATTACK as ATTACK_ACTION
from .restrictions import refuse
from .slots import cover, empty_slot, open_area, place
from .statics import ATTACK, DIFFICULTY, monster_value, static_value

DEFAULT_MONSTER_ROLL = 4
"""Roll a player must meet when a monster card does not print one."""

DEFAULT_MONSTER_ATTACK = 1
"""Damage a monster deals when its card does not print an attack value."""


DECK = "deck"
"""What a player attacks when they attack the monster deck rather than a slot."""

SLOT = "slot"
"""What a player attacks when they attack a monster that is face up."""


class AttackHandler:
    """
    Declares an attack against an active monster or against the monster deck.
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

        if command.get("source") == DECK:
            if not state.monster_deck.cards:
                return "the monster deck is empty"

            return refuse(state, ATTACK_ACTION, player=command.player)

        index = command.get("index", 0)
        monsters = state.active_monsters.cards

        if not isinstance(index, int) or not 0 <= index < len(monsters):
            return f"no monster at index {index!r}"

        if not getattr(monsters[index], "alive", False):
            return "that monster is already dead"

        return refuse(state, ATTACK_ACTION, player=command.player, card=monsters[index])

    def execute(self, command: Command, context: EffectContext) -> None:
        """
        Declare the attack and put the declaration in the queue.

        COMPREHENSIVE_RULES.md §7: the attack begins when the declaration
        resolves, not when it is made. Which is why a card may answer an
        attack before a die is rolled, and why an attack can arrive at its own
        resolution to find the monster gone.
        """
        state = context.state
        player = state.player(command.player)

        # Declaring spends the turn's attack; §12 hands it back if the
        # declaration finds nothing to fight.
        player.spend_attack()
        state.turn.record_attack()

        monsters = state.active_monsters.cards
        index = int(command.get("index", 0) or 0)

        context.push(
            StackItem(
                kind=StackItemType.ENGINE_EFFECT,
                label=ATTACK_DECLARATION,
                controller=player.player_id,
                source=None if command.get("source") == DECK else monsters[index],
                payload={"source": str(command.get("source", SLOT))},
            )
        )


def attack_declaration(item: StackItem, context: EffectContext) -> None:
    """
    Begin a declared attack, or let it fizzle.

    COMPREHENSIVE_RULES.md §12: an attack fizzles when the monster it named is
    no longer active, and an attack that fizzles is not spent.
    """
    state = context.state
    seat = item.controller

    if seat is None or not 0 <= seat < len(state.players):
        return

    player = state.player(seat)

    if not player.alive or state.combat.active:
        _give_the_attack_back(player)

        return

    attacked_the_deck = str(item.payload.get("source", SLOT)) == DECK

    if attacked_the_deck:
        monster = _reveal_for_attack(context, seat)
    else:
        monster = item.source

        if monster not in state.active_monsters.cards or not getattr(
            monster, "alive", False
        ):
            _give_the_attack_back(player)

            context.emit(
                EventType.ATTACK_FIZZLED,
                source=monster,
                controller=seat,
                targets=[player],
            )

            return

    # The debt is to the deck, and turning a card over pays it whether or not
    # there was a monster under it.
    pay_obligation(
        state,
        ATTACK_ACTION,
        seat,
        monster,
        card_id=MONSTER_DECK if attacked_the_deck else None,
    )

    if monster is None:
        # COMPREHENSIVE_RULES.md §7: the card turned over was not a monster.
        # It has been played, and the attack is over — but it was made, so it
        # is not handed back.
        return

    state.combat.begin(seat, monster)

    context.emit(
        EventType.ATTACK_START,
        source=monster,
        controller=seat,
        targets=[monster],
    )

    push_combat_round(context, seat, monster)


def _give_the_attack_back(player: Any) -> None:
    """
    Return the turn's attack to a player whose declaration came to nothing.
    """
    player.attacks_left += 1


def _reveal_for_attack(context: EffectContext, attacker: int) -> Any | None:
    """
    Turn over the top card of the monster deck and see what was attacked.

    COMPREHENSIVE_RULES.md §7: a monster comes into the monster area and the
    attack goes on against it. Anything else is played instead, and the attack
    is over before a die is rolled.

    Where exactly the new monster stands is the one thing the engine cannot say
    faithfully: the rules put it in a slot on top of the monster already there,
    and the engine's monster area is a list with a count rather than a row of
    slots. So it joins the area, is attacked, and the area returns to its usual
    size once it is dealt with.
    """
    state = context.state
    card = draw_from(context, "monster")

    if card is None:
        return None

    kind = getattr(getattr(card, "definition", None), "type", None)

    if kind is CardType.EVENT:
        _resolve_event(context, card)

        return None

    if kind is CardType.CURSE:
        _attach_curse(context, card)

        return None

    _turn_face_up(card)

    # COMPREHENSIVE_RULES.md §7: it goes into a slot, on top of the monster
    # standing there, and the attack goes on against it.
    cover(state, card)

    context.emit(EventType.ON_ENTER, source=card, controller=attacker)

    return card


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
    Roll for one round of an attack, and let the table answer the roll.

    The round is two stack objects, not one. A roll can be responded to, and a
    response is an ability that has to resolve before the roll counts — so the
    blow is pushed first and waits underneath, and the roll is settled above
    it. With nobody to answer, the roll settles at once and the two steps run
    back to back.
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

    context.push(
        StackItem(
            kind=StackItemType.COMBAT,
            label=COMBAT_STRIKE,
            source=monster,
            controller=attacker.player_id,
        )
    )

    if context.answerable_rolls:
        context.request_roll(DICE_SIDES, attack=True)

        return

    combat.settled_roll = natural_roll(context, DICE_SIDES, attack=True)


def combat_strike(item: StackItem, context: EffectContext) -> None:
    """
    Apply the roll the table has finished answering.
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

    roll = combat.settled_roll if combat.settled_roll is not None else 1
    combat.settled_roll = None

    before = (attacker.hp, getattr(monster, "hp", 0))

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

    if (attacker.hp, getattr(monster, "hp", 0)) == before:
        combat.stalled_rounds += 1
    else:
        combat.stalled_rounds = 0

    if combat.stalled_rounds >= STALLED_COMBAT_ROUNDS:
        # Neither side can hurt the other, and an attack that cannot progress
        # is over. Nothing on a card says so; the engine says so, because a
        # command has to finish.
        end_combat(context)

        return

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

    The reveal stops once every card there is has been turned over without a
    monster among them. That is not a step budget: a deck that runs out is
    rebuilt from its discard, so an event revealed, discarded and reshuffled
    would otherwise be revealed again for ever, and a table whose whole monster
    deck was events would sit there turning the same card over. It is the same
    reasoning `_first_monster` uses when it lays the game out, said again here
    because the deck is now refilled behind the reveal rather than running dry.
    """
    state = context.state

    open_area(state)

    # Everything that could still be turned over. A card that leaves the deck
    # and comes back through the discard is the same card, counted once.
    left = len(state.monster_deck) + len(state.monster_discard)

    while empty_slot(state) is not None and left > 0:
        card = draw_from(context, "monster")

        if card is None:
            break

        left -= 1

        kind = getattr(getattr(card, "definition", None), "type", None)

        if kind is CardType.EVENT:
            _resolve_event(context, card)
        elif kind is CardType.CURSE:
            _attach_curse(context, card)
        else:
            _turn_face_up(card)

            place(state, card)

            context.emit(EventType.ON_ENTER, source=card)


def _turn_face_up(card: Any) -> None:
    """
    Bring a monster into a slot as the card it is printed as.

    A monster that was beaten and later shuffled back into the deck is a card
    in a deck, not a corpse: whatever the last fight did to it — its wounds,
    its counters, the effects that were on it — belonged to the monster that
    was on the table, and that monster is gone. It comes back up with its
    printed health, like every other card revealed from the deck.
    """
    printed = getattr(getattr(card, "definition", None), "health", None)

    if printed is not None:
        card.hp = int(printed)

    card.alive = True
    card.tapped = False
    card.last_damaged_by = None
    card.counters.clear()
    card.modifiers.clear()


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
