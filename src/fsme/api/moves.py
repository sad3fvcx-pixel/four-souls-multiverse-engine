# src/fsme/api/moves.py

"""
What can be done right now, according to the engine.

A client has to offer the player something to click, and the list of things
worth offering is a rules question. This module does not answer it. It writes
down every move that could conceivably be made from the shape of the position —
this hand has four cards, so there are four cards to play — and then asks the
engine's own validators which of them are legal, one at a time.

That is the whole trick, and it is what keeps the rules in one place: a move
appears here because ``validate`` said yes, never because this module thinks it
should. When a rule changes, this list changes with it and nobody edits it.
"""

from __future__ import annotations

from typing import Any

from fsme.commands import Command, CommandType
from fsme.game import Game
from fsme.rules.activation import CHARACTER, ROOM
from fsme.rules.combat import DECK as ATTACK_DECK
from fsme.rules.shop import DECK as BUY_DECK
from fsme.state import GamePhase


def legal_moves(game: Game) -> list[dict[str, Any]]:
    """
    Every command the engine would accept right now, with a label for each.
    """
    state = game.state

    if game.runtime.awaiting_decision is not None:
        # A question is open, and answering it is the only move there is.
        return []

    offered: list[dict[str, Any]] = []

    for player in state.players:
        for command, label in _candidates(game, player.player_id):
            if _would_be_accepted(game, command):
                offered.append(
                    {
                        "player": command.player,
                        "type": str(command.type),
                        "payload": dict(command.payload),
                        "label": label,
                    }
                )

    return offered


def _candidates(game: Game, seat: int) -> list[tuple[Command, str]]:
    """
    Every move worth asking about for one player, legal or not.
    """
    state = game.state
    player = state.player(seat)

    moves: list[tuple[Command, str]] = []

    def add(kind: CommandType, label: str, **payload: Any) -> None:
        moves.append((Command(type=kind, player=seat, payload=payload), label))

    add(CommandType.START_GAME, "Start the game")
    add(CommandType.PASS_PRIORITY, "Pass")
    add(CommandType.END_PHASE, "End the phase")
    add(CommandType.END_TURN, "End the turn")

    for index, card in enumerate(player.hand.cards):
        add(CommandType.PLAY_LOOT, f"Play {card.name}", index=index)

    for index, card in enumerate(player.treasures.cards):
        for ability in _activated(card):
            add(
                CommandType.ACTIVATE_TREASURE,
                f"Use {card.name}"
                + (f" — {ability['description']}" if ability["description"] else ""),
                index=index,
                ability=ability["index"],
            )

    for ability in _activated(player.character):
        add(
            CommandType.ACTIVATE_TREASURE,
            f"Use {getattr(player.character, 'name', 'your character')}",
            zone=CHARACTER,
            ability=ability["index"],
        )

    for index, card in enumerate(state.room_area.cards):
        for ability in _activated(card):
            add(
                CommandType.ACTIVATE_TREASURE,
                f"Use {card.name}",
                zone=ROOM,
                index=index,
                ability=ability["index"],
            )

    if state.turn.phase is GamePhase.ACTION:
        for index, card in enumerate(state.treasure_shop.cards):
            add(CommandType.BUY_TREASURE, f"Buy {card.name}", index=index)

        add(CommandType.BUY_TREASURE, "Buy the top of the treasure deck", source=BUY_DECK)

        for index, monster in enumerate(state.active_monsters.cards):
            add(CommandType.ATTACK, f"Attack {monster.name}", index=index)

        add(CommandType.ATTACK, "Attack the monster deck", source=ATTACK_DECK)

    return moves


def _activated(card: Any) -> list[dict[str, Any]]:
    """
    The abilities a card taps for, numbered as the command numbers them.
    """
    face = getattr(card, "face", None)

    if face is None:
        return []

    return [
        {"index": index, "description": ability.description}
        for index, ability in enumerate(face.abilities_for("on_activate"))
    ]


def _would_be_accepted(game: Game, command: Command) -> bool:
    """
    Ask the engine whether it would take this command, without submitting it.

    The validators only read the state — that is a rule of the engine, not a
    hope of this module — so asking is free and changes nothing.
    """
    return game.runtime.refuse_reason(command) is None
