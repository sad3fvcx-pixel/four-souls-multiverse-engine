# src/fsme/analysis/tally.py

"""
Counting what happened, across as many games as you like.

A tally reads journals and adds up. It measures nothing the engine did not
already say: every number here is a count of events that were recorded, and
where a number could be read as a claim about the game rather than about the
record, it is named so that it cannot be.

That naming is most of the care in this file. "Winrate" of a card is not the
card's contribution to winning — it is how often the player who played it went
on to win, which is a different sentence and a much weaker one. A card played
mostly by whoever is already ahead will look strong here and be worth nothing.
The tally reports the correlation and refuses to call it an effect; separating
the two is what a card test does, by running the same games with and without
the card, and that is a different tool built on this one.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from fsme.journal import Journal

PLAYED = "on_play"
ACTIVATED = "on_activate"
BOUGHT = "treasure_bought"
MONSTER_KILLED = "monster_killed"
MONSTER_ENTERED = "on_enter"
PLAYER_DIED = "player_died"
ATTACK_ROLL = "after_attack_roll"


@dataclass(slots=True)
class Seen:
    """
    What was counted about one card, character or monster.
    """

    name: str = ""

    games: int = 0
    """Games in which it turned up at all."""

    times: int = 0
    """Times it did the thing being counted, across all games."""

    wins: int = 0
    """
    Games it turned up in that the player it belonged to went on to win.

    A correlation and not a contribution. See the note at the top of this file.
    """

    turns: int = 0
    """Turns totalled, for whatever "turns" means to this kind of thing."""

    measured: int = 0
    """
    How many times the turns above were actually measured.

    Not the same as ``games``, and the difference is the point. A monster that
    was already on the table when the game was dealt never entered play, so
    nobody saw it arrive and its life cannot be measured — counting that as a
    life of zero turns would drag every average towards nothing and look like
    a finding.
    """

    def rate(self) -> float | None:
        return self.wins / self.games if self.games else None

    def average_turns(self) -> float | None:
        return self.turns / self.measured if self.measured else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "games": self.games,
            "times": self.times,
            "wins": self.wins,
            "winrate": self.rate(),
            "measured": self.measured,
            "average_turns": self.average_turns(),
        }


@dataclass(slots=True)
class Tally:
    """
    Everything counted so far, over any number of games.

    Fed one journal at a time and kept small: a run of ten thousand games is a
    gigabyte of journals and a few kilobytes of this.
    """

    games: int = 0
    finished: int = 0

    turns: int = 0
    commands: int = 0

    wins_by_seat: Counter[int] = field(default_factory=Counter)
    deaths: int = 0

    attack_rolls: int = 0
    attack_hits: int = 0

    characters: dict[str, Seen] = field(default_factory=dict)
    cards: dict[str, Seen] = field(default_factory=dict)
    monsters: dict[str, Seen] = field(default_factory=dict)

    events: Counter[str] = field(default_factory=Counter)

    def add(self, journal: Journal) -> None:
        """
        Count one game.
        """
        self.games += 1

        told = journal.outcome.get("winner")
        winner = None if told is None else int(told)

        if winner is not None:
            self.finished += 1
            self.wins_by_seat[winner] += 1

        turns = int(journal.outcome.get("turns") or _last_turn(journal))

        self.turns += turns
        self.commands += len(journal)

        self._count_characters(journal, winner, turns)
        self._count_the_play(journal, winner)

    def _count_characters(
        self, journal: Journal, winner: int | None, turns: int
    ) -> None:
        for seat, character in enumerate(journal.characters):
            if not character:
                continue

            seen = self.characters.setdefault(character, Seen(name=character))

            seen.games += 1
            seen.turns += turns
            seen.measured += 1

            if winner == seat:
                seen.wins += 1

    def _count_the_play(self, journal: Journal, winner: int | None) -> None:
        """
        Walk the events once, counting cards, monsters and everything else.
        """
        card_names: dict[str, str] = {}
        card_owners: dict[str, set[int]] = defaultdict(set)
        card_times: Counter[str] = Counter()

        monster_names: dict[str, str] = {}
        monster_seen: Counter[str] = Counter()
        monster_killed: Counter[str] = Counter()
        monster_life: dict[str, list[int]] = defaultdict(list)
        monster_born: dict[str, int] = {}

        for entry in journal.entries:
            turn = entry.before.turn

            for event in entry.events:
                self.events[event.type] += 1

                if event.type == PLAYER_DIED:
                    self.deaths += 1

                if event.type == ATTACK_ROLL:
                    self.attack_rolls += 1

                    if event.payload.get("hit"):
                        self.attack_hits += 1

                card = event.source_id

                if card is None:
                    continue

                if event.type in (PLAYED, ACTIVATED, BOUGHT):
                    card_names[card] = event.source or card
                    card_times[card] += 1

                    who = event.controller if event.controller is not None else entry.player

                    card_owners[card].add(int(who))

                if event.type == MONSTER_ENTERED and _looks_like_a_monster(event):
                    monster_names[card] = event.source or card
                    monster_seen[card] += 1
                    monster_born.setdefault(card, turn)

                if event.type == MONSTER_KILLED:
                    monster_names[card] = event.source or card
                    monster_killed[card] += 1
                    monster_seen.setdefault(card, 0)

                    born = monster_born.pop(card, None)

                    if born is not None:
                        monster_life[card].append(max(0, turn - born))

        for card, times in card_times.items():
            seen = self.cards.setdefault(card, Seen(name=card_names.get(card, card)))

            seen.games += 1
            seen.times += times

            if winner is not None and winner in card_owners[card]:
                seen.wins += 1

        for monster, times in monster_seen.items():
            seen = self.monsters.setdefault(
                monster, Seen(name=monster_names.get(monster, monster))
            )

            seen.games += 1
            seen.times += max(times, monster_killed[monster])

            # "Wins" means something else for a monster: it is how often it was
            # beaten, since a monster has nobody to win for.
            seen.wins += monster_killed[monster]

            lives = monster_life.get(monster, ())

            seen.turns += sum(lives)
            seen.measured += len(lives)

    def merge(self, other: Tally) -> None:
        """
        Fold another tally into this one.

        Counting is addition, so it does not matter who counted what or in
        which order — which is what lets a run be split across processes and
        added back up into the same numbers.
        """
        self.games += other.games
        self.finished += other.finished
        self.turns += other.turns
        self.commands += other.commands
        self.deaths += other.deaths
        self.attack_rolls += other.attack_rolls
        self.attack_hits += other.attack_hits

        self.wins_by_seat.update(other.wins_by_seat)
        self.events.update(other.events)

        for mine, theirs in (
            (self.characters, other.characters),
            (self.cards, other.cards),
            (self.monsters, other.monsters),
        ):
            for key, seen in theirs.items():
                here = mine.setdefault(key, Seen(name=seen.name))

                here.games += seen.games
                here.times += seen.times
                here.wins += seen.wins
                here.turns += seen.turns
                here.measured += seen.measured

    def average_turns(self) -> float | None:
        return self.turns / self.games if self.games else None

    def average_commands(self) -> float | None:
        return self.commands / self.games if self.games else None

    def hit_rate(self) -> float | None:
        return self.attack_hits / self.attack_rolls if self.attack_rolls else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "games": self.games,
            "finished": self.finished,
            "average_turns": self.average_turns(),
            "average_commands": self.average_commands(),
            "deaths": self.deaths,
            "attack_rolls": self.attack_rolls,
            "hit_rate": self.hit_rate(),
            # Seats are written as text: JSON has no integer keys, and a tally
            # that changed shape on its way through a file would be a poor
            # thing to count with.
            "wins_by_seat": {
                str(seat): count for seat, count in sorted(self.wins_by_seat.items())
            },
            "characters": {
                key: seen.to_dict()
                for key, seen in by_games(self.characters)
            },
            "cards": {key: seen.to_dict() for key, seen in by_times(self.cards)},
            "monsters": {
                key: seen.to_dict() for key, seen in by_games(self.monsters)
            },
            "events": {
                kind: count
                for kind, count in sorted(
                    self.events.items(), key=lambda item: (-item[1], item[0])
                )
            },
        }


def by_games(seen: dict[str, Seen]) -> list[tuple[str, Seen]]:
    """
    Most-seen first, and ties broken by name.

    The tiebreak is not tidiness. Two runs of the same games must print the
    same table, and a sort that leaves ties where it found them prints them in
    whatever order the games happened to be counted in.
    """
    return sorted(seen.items(), key=lambda item: (-item[1].games, item[0]))


def by_times(seen: dict[str, Seen]) -> list[tuple[str, Seen]]:
    """
    Most-used first, and ties broken by name.
    """
    return sorted(seen.items(), key=lambda item: (-item[1].times, item[0]))


def _last_turn(journal: Journal) -> int:
    """
    How far a game got, for one that did not finish.
    """
    return journal.entries[-1].before.turn if journal.entries else 0


def _looks_like_a_monster(event: Any) -> bool:
    """
    Whether a card entering play was a monster.

    Everything enters play through the same event, so the card has to be told
    apart by its identifier: the import puts every monster in the monster deck
    and says so in the name it gives the card.
    """
    return str(event.source_id or "").startswith("monster_deck")
