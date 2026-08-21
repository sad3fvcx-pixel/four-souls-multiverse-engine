# src/fsme/rules/statics.py

"""
Static modifiers.

A static changes a number for as long as its card is in play. It is never
triggered and never resolved: when the rules need a value they ask, and every
card in play contributes. Recomputing on demand means the answer cannot drift
out of step with the board — a card leaving play stops mattering immediately,
with nothing to undo.
"""

from __future__ import annotations

from typing import Any

from fsme.cards import CardInstance, Static
from fsme.runtime.ability_context import AbilityContext
from fsme.runtime.condition_evaluator import ConditionEvaluator
from fsme.state import GameState, TemporaryModifier
from fsme.state.modifiers import (
    ATTACK,
    ATTACKS,
    DIFFICULTY,
    LOOT_PLAYS,
    LOOT_STEP,
    MAX_HP,
    PURCHASES,
    ROLL,
    STATS,
)

from .constants import DICE_SIDES

_CONDITIONS = ConditionEvaluator()
"""
One evaluator, built once.

It holds no game state — only the table of condition implementations — so
sharing it is safe and rebuilding it for every value read would be waste.
"""

__all__ = [
    "ATTACK",
    "ATTACKS",
    "LOOT_PLAYS",
    "LOOT_STEP",
    "DIFFICULTY",
    "MAX_HP",
    "MONSTER_SCOPES",
    "PURCHASES",
    "ROLL",
    "STATS",
    "bonus",
    "cards_in_play",
    "expire_card_modifiers",
    "expire_turn_modifiers",
    "monster_value",
    "refresh_derived",
    "static_amount",
    "static_conditions_hold",
    "static_value",
]


def cards_in_play(state: GameState) -> list[CardInstance]:
    """
    Every card that is in play, in a fixed order.

    This is the engine's single answer to "what is on the table": triggered
    abilities and static modifiers both read it, so a card cannot be live for
    one and dead for the other. A character, an item, a curse afflicting a
    player, an active monster and the current room are all in play; a card in
    hand, in a deck or in a discard pile is not.
    """
    cards: list[CardInstance] = []

    for player in state.players:
        if isinstance(player.character, CardInstance):
            cards.append(player.character)

        cards.extend(
            card for card in player.treasures.cards if isinstance(card, CardInstance)
        )
        cards.extend(
            card for card in player.curses.cards if isinstance(card, CardInstance)
        )

    cards.extend(
        card for card in state.active_monsters.cards if isinstance(card, CardInstance)
    )
    cards.extend(
        card for card in state.room_area.cards if isinstance(card, CardInstance)
    )
    cards.extend(
        card for card in state.bonus_souls.cards if isinstance(card, CardInstance)
    )

    return cards


def _applies_to(
    static: Static,
    source: CardInstance,
    player_id: int,
    state: GameState,
) -> bool:
    """
    Decide whether one card's static reaches one player right now.
    """
    if not _in_scope(static, source, player_id):
        return False

    if not static.conditions:
        return True

    return _CONDITIONS.evaluate_all(
        static.conditions,
        state,
        AbilityContext(
            source=source,
            controller=player_id,
            owner=source.owner,
        ),
    )


def _in_scope(static: Static, source: CardInstance, player_id: int) -> bool:
    if static.scope == "all_players":
        return True

    if source.controller is None:
        return False

    if static.scope == "opponents":
        return source.controller != player_id

    return source.controller == player_id


def static_amount(static: Static, source: CardInstance) -> int:
    """
    What one static is worth right now.

    Usually its printed amount. A static that is worth something per counter is
    worth nothing while the card carries none, which is why counting happens
    here rather than when the card is written.
    """
    if not static.per_counter:
        return static.amount

    counters = int(getattr(source, "counters", {}).get(static.per_counter, 0))

    return static.amount * counters


def bonus(state: GameState, stat: str, player_id: int) -> int:
    """
    Return the total modifier to a stat for one player.

    Printed statics and temporary bonuses are added up together, because they
    are the same thing to whoever is asking: a card that says "you have +1
    attack" and a card that says "+1 attack till end of turn" must not be able
    to disagree about what a player's attack is.
    """
    total = 0

    for card in cards_in_play(state):
        for static in card.face.statics:
            if static.stat != stat:
                continue

            if _applies_to(static, card, player_id, state):
                total += static_amount(static, card)

    for modifier in state.modifiers:
        if modifier.stat == stat and modifier.player_id == player_id:
            total += modifier.amount

    return total


MONSTER_SCOPES = ("all_monsters", "other_monsters")
"""
Static scopes that reach monsters rather than players.

"Monsters have +1 DC" is a static like any other; what differs is who it lands
on, and a monster has no seat for the player scopes to match against.
"""


PLAYER_SCOPES = ("controller", "opponents", "all_players", "self")
"""
Static scopes that reach players, in the words a card writes them.

``self`` is here because a card in play says "this" and means its own holder;
on a monster there is no holder, and ``monster_value`` reads the same static
instead. Both spellings arrive at the branch below, and a fifth word would
fall through it and quietly mean ``controller``.
"""

STATIC_SCOPES = PLAYER_SCOPES + MONSTER_SCOPES


def monster_value(state: GameState, stat: str, monster: Any, base: int) -> int:
    """
    Return one of a monster's numbers with everything that changes it applied.

    Three things can: the monster's own printed statics, statics on other cards
    that reach monsters, and modifiers sitting on the monster until the turn
    ends. They are added up here so that combat asks one question and cannot
    get two answers.
    """
    total = base

    for static in monster.face.statics:
        if static.stat != stat or static.scope == "other_monsters":
            # A monster's own static reaches itself unless it says otherwise,
            # and "other monsters" says otherwise.
            continue

        if static_conditions_hold(static, monster, state):
            total += static_amount(static, monster)

    for card in cards_in_play(state):
        if card is monster:
            continue

        for static in card.face.statics:
            if static.stat != stat or static.scope not in MONSTER_SCOPES:
                continue

            if static_conditions_hold(static, card, state):
                total += static_amount(static, card)

    for modifier in getattr(monster, "modifiers", ()):
        if modifier.stat == stat:
            total += modifier.amount

    if stat == DIFFICULTY:
        # COMPREHENSIVE_RULES.md §5: "A roll result and a monster's difficulty
        # are never above 6 nor below 1." The bound belongs here rather than in
        # combat, because it is a fact about the number and not about the fight
        # — everything that asks what a monster needs gets the same answer, and
        # nothing has to remember to clamp it afterwards.
        #
        # Without it a +1 on a monster printed at 6 asks for a 7, and one die
        # cannot roll a 7: the monster becomes unbeatable by attacking, which
        # is not a difficulty at all.
        return max(1, min(DICE_SIDES, total))

    return max(0, total)


def static_conditions_hold(
    static: Static, source: CardInstance, state: GameState
) -> bool:
    """
    Check a static's conditions against the card carrying it.

    This is the reading used by statics that are not about a player at all — a
    monster's own numbers, or a prohibition — where there is no seat to ask the
    condition about and the card itself is the subject.
    """
    if not static.conditions:
        return True

    return _CONDITIONS.evaluate_all(
        static.conditions,
        state,
        AbilityContext(
            source=source,
            controller=source.controller,
            owner=source.owner,
        ),
    )


def expire_card_modifiers(state: GameState) -> int:
    """
    Drop every card modifier that only lasted for the turn.

    A copy that only lasted for the turn lapses here too: "this becomes a copy
    of that item till end of turn" leaves the card wearing its own rules again.
    """
    dropped = 0

    for card in list(cards_in_play(state)):
        keep = [
            modifier
            for modifier in card.modifiers
            if not modifier.expires_at_end_of_turn()
        ]

        dropped += len(card.modifiers) - len(keep)
        card.modifiers = keep

        if getattr(card, "copy_expires", ""):
            card.copy_of = None
            card.copy_expires = ""

            dropped += 1

    return dropped


def expire_turn_modifiers(state: GameState) -> list[TemporaryModifier]:
    """
    Drop everything that only lasted for the turn, and return the modifiers.

    Unspent damage shields go too, and so do promises: a change owed to the
    next damage or the next loot this turn is worth nothing once the turn is
    over.

    A hit point bonus is the one that cannot simply be forgotten. The engine
    stores hit points remaining rather than damage taken, so a player who gained
    +2 HP and then took two damage looks unhurt; letting the bonus lapse without
    lowering their hit points would heal them. Taking the bonus back off keeps
    the damage where it was — and a player whose damage now exceeds their
    maximum dies, which is what the rules say happens.
    """
    state.shields = [
        shield for shield in state.shields if not shield.expires_at_end_of_turn()
    ]
    state.promises = [
        promise for promise in state.promises if not promise.expires_at_end_of_turn()
    ]
    state.watchers = [
        watcher for watcher in state.watchers if not watcher.expires_at_end_of_turn()
    ]

    for player in state.players:
        player.loot_limit_lifted = False

    expire_card_modifiers(state)

    expired = [modifier for modifier in state.modifiers if modifier.expires_at_end_of_turn()]

    if not expired:
        return []

    state.modifiers = [
        modifier for modifier in state.modifiers if not modifier.expires_at_end_of_turn()
    ]

    for modifier in expired:
        if modifier.stat != MAX_HP or modifier.amount <= 0:
            continue

        player = state.player(modifier.player_id)
        player.hp = max(0, player.hp - modifier.amount)

    refresh_derived(state)

    return expired


def static_value(state: GameState, stat: str, player_id: int, base: int) -> int:
    """
    Return a base value with every applicable static applied.

    Nothing goes below zero: a stack of penalties reduces a number to nothing
    rather than turning it inside out.
    """
    return max(0, base + bonus(state, stat, player_id))


def refresh_derived(state: GameState) -> bool:
    """
    Bring stored player values back in line with the board.

    Hit point maxima are stored rather than computed, because effects read and
    write them. This is what keeps that store honest, and it runs with the
    State-Based Actions for the same reason they do: after every change,
    before anybody looks.
    """
    changed = False

    for player in state.players:
        base = _base_hp(player)
        maximum = max(1, base + bonus(state, MAX_HP, player.player_id))

        if player.max_hp != maximum:
            player.max_hp = maximum
            changed = True

        if player.hp > maximum:
            player.hp = maximum
            changed = True

    return changed


def _base_hp(player: Any) -> int:
    """
    A player's printed hit points, before anything modifies them.
    """
    character = player.character

    if isinstance(character, CardInstance) and character.definition.health:
        return int(character.definition.health)

    return int(player.max_hp)
