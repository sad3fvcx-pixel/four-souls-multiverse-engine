# src/fsme/analysis/summary.py

"""
One game, reduced to what a question can be asked of.

A journal is the whole truth about a game and is far too large to hold ten
thousand of. A summary is the same game in a kilobyte: what each seat did, what
each seat had, and where their souls came from — which is enough for every
question this package asks and small enough to keep for every game in a run.

The reduction is the design decision worth defending. Everything above this
module reads summaries rather than journals, so a report can be recomputed
without replaying anything, and every number in one can be traced back to the
seed it came from. What is dropped is dropped on purpose: the order of events
inside a turn, the exact stack, the text of the cards. Those are in the journal,
and a reader following a summary back to the game gets them.

Nothing here decides anything either. A seat's souls are counted from the
events that gave them; where a soul came from is the source the engine named.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from fsme.journal import Journal

SOUL_GAINED = "soul_gained"
MONSTER_KILLED = "monster_killed"
PLAYER_DIED = "player_died"
COINS_GAINED = "coins_gained"
TREASURE_BOUGHT = "treasure_bought"
PLAYED = "on_play"
ACTIVATED = "on_activate"
ATTACK_START = "attack_start"

FROM_A_MONSTER = "monster"
FROM_A_CARD = "card"
FROM_NOWHERE_NAMED = "unnamed"


@dataclass(slots=True)
class SeatFacts:
    """
    What one seat did with its game.
    """

    seat: int
    name: str = ""
    character: str = ""

    won: bool = False

    souls: int = 0
    souls_from: Counter[str] = field(default_factory=Counter)
    """
    Where the souls came from, by kind.

    A game won on monsters and a game won on bonus souls are different games,
    and the difference is invisible in a soul count.
    """

    kills: int = 0
    deaths: int = 0
    attacks: int = 0

    coins_gained: int = 0
    purchases: int = 0

    cards_used: set[str] = field(default_factory=set)
    """
    Cards this seat played, activated or bought, by identifier.

    A set rather than a count: the questions above this ask whether a seat had
    a card, and how many times it was used is the tally's business.
    """

    moves: int = 0
    forced_moves: int = 0
    """
    Moves where the engine offered exactly one thing to do.

    A choice that was not a choice tells you nothing about a player, and a run
    made mostly of them tells you nothing about a bot.
    """

    thought: int = 0
    """Moves this seat made with a bot's working attached."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "seat": self.seat,
            "name": self.name,
            "character": self.character,
            "won": self.won,
            "souls": self.souls,
            "souls_from": dict(sorted(self.souls_from.items())),
            "kills": self.kills,
            "deaths": self.deaths,
            "attacks": self.attacks,
            "coins_gained": self.coins_gained,
            "purchases": self.purchases,
            "cards_used": sorted(self.cards_used),
            "moves": self.moves,
            "forced_moves": self.forced_moves,
            "thought": self.thought,
        }


@dataclass(slots=True)
class GameSummary:
    """
    One game, in the facts the reports are built from.
    """

    seed: int
    players: int

    finished: bool = False
    winner: int | None = None
    turns: int = 0
    commands: int = 0

    seats: list[SeatFacts] = field(default_factory=list)

    def seat(self, index: int) -> SeatFacts:
        return self.seats[index]

    @property
    def winning_seat(self) -> SeatFacts | None:
        if self.winner is None or not 0 <= self.winner < len(self.seats):
            return None

        return self.seats[self.winner]

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "players": self.players,
            "finished": self.finished,
            "winner": self.winner,
            "turns": self.turns,
            "commands": self.commands,
            "seats": [seat.to_dict() for seat in self.seats],
        }


def summarise(journal: Journal) -> GameSummary:
    """
    Reduce one journal to the facts.
    """
    winner = journal.outcome.get("winner")
    winner = None if winner is None else int(winner)

    summary = GameSummary(
        seed=journal.seed,
        players=len(journal.players),
        finished=winner is not None,
        winner=winner,
        turns=int(journal.outcome.get("turns") or _last_turn(journal)),
        commands=len(journal),
        seats=[
            SeatFacts(
                seat=seat,
                name=name,
                character=(
                    journal.characters[seat]
                    if seat < len(journal.characters)
                    else ""
                ),
                won=winner == seat,
            )
            for seat, name in enumerate(journal.players)
        ],
    )

    if not summary.seats:
        return summary

    for entry in journal.entries:
        _count_the_move(summary, entry)

        for event in entry.events:
            _count_the_event(summary, entry, event)

    return summary


def _count_the_move(summary: GameSummary, entry: Any) -> None:
    """
    Count what a seat did, and whether it had any say in doing it.
    """
    if not 0 <= entry.player < len(summary.seats):
        return

    seat = summary.seats[entry.player]

    seat.moves += 1

    if len(entry.offered) == 1:
        seat.forced_moves += 1

    if entry.decision:
        seat.thought += 1


def _count_the_event(summary: GameSummary, entry: Any, event: Any) -> None:
    """
    Count one event against whichever seat it belongs to.
    """
    who = event.controller

    if who is None or not 0 <= int(who) < len(summary.seats):
        return

    seat = summary.seats[int(who)]

    if event.type == SOUL_GAINED:
        seat.souls += 1
        seat.souls_from[_where_the_soul_came_from(event)] += 1

    elif event.type == MONSTER_KILLED:
        seat.kills += 1

    elif event.type == PLAYER_DIED:
        seat.deaths += 1

    elif event.type == ATTACK_START:
        seat.attacks += 1

    elif event.type == COINS_GAINED:
        seat.coins_gained += int(event.payload.get("amount", 0) or 0)

    elif event.type == TREASURE_BOUGHT:
        seat.purchases += 1

    if event.type in (PLAYED, ACTIVATED, TREASURE_BOUGHT) and event.source_id:
        seat.cards_used.add(str(event.source_id))


def _where_the_soul_came_from(event: Any) -> str:
    """
    Name the kind of thing that gave a soul.

    A soul awarded by a defeated monster, a soul card claimed off the table and
    a soul minted by an effect are three different ways to win, and a report
    that added them together would hide the only interesting part.
    """
    source = str(event.source_id or "")

    if source.startswith("monster_deck"):
        return FROM_A_MONSTER

    if source:
        return FROM_A_CARD

    return FROM_NOWHERE_NAMED


def _last_turn(journal: Journal) -> int:
    return journal.entries[-1].before.turn if journal.entries else 0
