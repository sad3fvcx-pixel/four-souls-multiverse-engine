# src/fsme/api/view.py

"""
A game, written down as plain data for something outside to look at.

This is what a client sees, and it is deliberately the only thing a client
sees. The engine's objects are live: a card in a hand is the same object as the
card in the discard pile it becomes, and holding on to one is holding on to the
game. A view is a copy, flat, JSON-shaped and finished — nothing here can be
played, only shown.

Nothing in this module decides anything. It reads the state the rules produced
and names the parts, so that a page can lay them out without knowing a rule.
"""

from __future__ import annotations

from typing import Any

from fsme.game import Game
from fsme.state import GameState


def snapshot(game: Game) -> dict[str, Any]:
    """
    Everything a client needs to draw the game, as it stands right now.
    """
    state = game.state

    return {
        "seed": state.seed,
        "started": state.started,
        "over": bool(state.game_over),
        "winner": state.winner,
        "souls_to_win": state.souls_to_win,
        "turn": _turn(state),
        "players": [_player(state, player) for player in state.players],
        "board": _board(state),
        "stack": [_stack_item(item) for item in state.stack],
        "waiting": _waiting(game),
    }


def _turn(state: GameState) -> dict[str, Any]:
    turn = state.turn

    return {
        "number": turn.turn_number,
        "phase": str(turn.phase),
        "active_player": turn.active_player,
        "loot_played": turn.loot_played,
        "attacks_declared": turn.attacks_declared,
    }


def _player(state: GameState, player: Any) -> dict[str, Any]:
    return {
        "id": player.player_id,
        "name": player.name,
        "hp": player.hp,
        "max_hp": player.max_hp,
        "alive": bool(player.alive),
        "pennies": player.pennies,
        "souls": player.soul_count,
        "attacks_left": player.attacks_left,
        "purchases_left": player.purchases_left,
        "counters": dict(player.counters),
        "active": player.player_id == state.turn.active_player,
        "has_priority": state.priority.holder == player.player_id,
        "character": _card(player.character),
        "hand": [_card(card) for card in player.hand.cards],
        "treasures": [_card(card) for card in player.treasures.cards],
        "curses": [_card(card) for card in player.curses.cards],
    }


def _board(state: GameState) -> dict[str, Any]:
    return {
        "shop": [_card(card) for card in state.treasure_shop.cards],
        "monster_slots": [
            {
                "index": index,
                "active": _card(slot.active),
                "buried": [_card(card) for card in slot.cards[:-1]],
            }
            for index, slot in enumerate(state.monster_area)
        ],
        "room": [_card(card) for card in state.room_area.cards],
        "bonus_souls": [_card(card) for card in state.bonus_souls.cards],
        "decks": {
            "loot": len(state.loot_deck),
            "loot_discard": len(state.loot_discard),
            "treasure": len(state.treasure_deck),
            "treasure_discard": len(state.treasure_discard),
            "monster": len(state.monster_deck),
            "monster_discard": len(state.monster_discard),
        },
        "combat": {
            "active": bool(state.combat.active),
            "attacker": state.combat.attacker,
            "monster": _card(state.combat.monster),
            "round": state.combat.round_number,
        },
    }


def _card(card: Any) -> dict[str, Any] | None:
    """
    One card, as much of it as anybody outside the engine may know.

    The face rather than the printed card, because a card copying another plays
    by the rules it is wearing — and the printed name is kept beside it, since
    what a card *is* and what it *does* are two different questions.
    """
    if card is None:
        return None

    definition = getattr(card, "definition", None)

    if definition is None:
        # A soul token: no card, no text, and it still has to be shown.
        return {
            "id": str(getattr(card, "token_id", "soul")),
            "name": "Soul",
            "type": "soul",
        }

    face = getattr(card, "face", definition)

    written: dict[str, Any] = {
        "id": definition.id,
        "instance": getattr(card, "instance_id", ""),
        "name": definition.name,
        "type": str(definition.type),
        "text": str(definition.metadata.get("text", "")),
        "tapped": bool(getattr(card, "tapped", False)),
        "eternal": bool(getattr(card, "is_eternal", False)),
        "counters": dict(getattr(card, "counters", {})),
    }

    if face is not definition:
        written["copying"] = face.name

    hp = getattr(card, "hp", None)

    if hp is not None and definition.health:
        written["hp"] = hp
        written["max_hp"] = definition.health
        written["alive"] = bool(getattr(card, "alive", True))

    if definition.attack is not None:
        written["attack"] = definition.attack

    if definition.roll is not None:
        written["roll"] = definition.roll

    if definition.souls:
        written["souls"] = definition.souls

    return written


def _stack_item(item: Any) -> dict[str, Any]:
    ability = getattr(item, "ability", None)

    return {
        "kind": str(item.kind),
        "label": item.label,
        "controller": item.controller,
        "source": getattr(item.source, "name", None),
        "description": getattr(ability, "description", "") if ability else "",
    }


def _waiting(game: Game) -> dict[str, Any]:
    """
    What the engine is waiting for, if it is waiting for anything.

    Three answers are possible and they are not alike: a question put to one
    player, a window in which anybody may respond, or nothing at all — in which
    case it is the active player's move.
    """
    decision = game.runtime.awaiting_decision

    if decision is not None:
        return {
            "kind": "decision",
            "player": decision.player,
            "prompt": decision.prompt or str(decision.kind),
            "minimum": decision.minimum,
            "maximum": decision.maximum,
            "options": [_option(option) for option in decision.options],
        }

    if game.runtime.awaiting_priority:
        return {
            "kind": "priority",
            "player": game.state.priority.holder,
        }

    return {"kind": "action", "player": game.state.turn.active_player}


def _option(option: Any) -> str:
    """
    One thing a player may choose, in as many words as it takes to tell it apart.
    """
    name = getattr(option, "name", None)

    if name is not None:
        return str(name)

    described = getattr(option, "description", None)

    if described:
        return str(described)

    return str(option)


def events(game: Game, since: int = 0) -> list[dict[str, Any]]:
    """
    The game's history from a point onwards, as a log a client can print.

    ``since`` is how much of it the client already has: the history only grows,
    so a client that remembers a number never asks for the same line twice.
    """
    written: list[dict[str, Any]] = []

    for index, event in enumerate(game.history[since:], start=since):
        written.append(
            {
                "index": index,
                "type": str(event.type),
                "source": getattr(event.source, "name", None),
                "controller": event.controller,
                "targets": [
                    getattr(target, "name", getattr(target, "player_id", None))
                    for target in event.targets
                ],
                "payload": {
                    key: _plain(value)
                    for key, value in event.payload.items()
                    if key not in ("stack_id",)
                },
            }
        )

    return written


def _plain(value: Any) -> Any:
    """
    Reduce whatever an event is carrying to something JSON can hold.
    """
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    name = getattr(value, "name", None)

    if name is not None:
        return str(name)

    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]

    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}

    return str(value)
