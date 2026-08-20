# src/fsme/scenario/scenario.py

"""
A scenario: the configuration a game starts from.

This is not a save and must never become one. A save is a position — every
card in every zone, whose turn it is, what is on the stack — and it exists so
that a game can be continued. A scenario is a handful of choices made *before*
a game exists: which sets are in the decks, who sits where, what the table is
worth winning. The game that follows is the game FSME already plays.

The distinction is worth holding on to, because every request to add "one more
thing the game starts with" is a request to reinvent the save format in here.

Plain data, and only plain data. Nothing in this package imports `fsme.rules`
or `fsme.game`, so the setup can read a scenario without a cycle; nothing in it
has behaviour, and nothing in it touches a GameState. What a scenario *means*
is decided by the rules, which is where meaning belongs.

Every field is optional. A scenario that says nothing is the game FSME deals
today, which is the property the whole engine's regression suite depends on.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

FORMAT = "fsme-scenario"
"""
What the file says it is.

Named rather than inferred, for the same reason the journal envelope names
itself: a file that is not one of ours should be refused as such rather than
half-read.
"""

VERSION = 1
"""
The version of the scenario format this build writes and reads.

A build that meets a newer one refuses it by number. A scenario is small and
hand-written; guessing at a field this engine has never heard of would be
guessing at somebody's experiment.
"""


@dataclass(frozen=True, slots=True)
class Seat:
    """
    One player, as a scenario asks for them.

    Every field is optional and an empty seat is dealt exactly the way a seat
    is dealt today — shuffled character, its printed starting item, the ordinary
    opening hand and cents. That matters more than it sounds: an experiment
    usually wants to pin one thing and leave the rest alone.
    """

    name: str = ""

    character: str = ""
    """
    The identifier of the character to deal to this seat.

    An identifier and not a name, because two sets print characters with the
    same name and different rules — there are six cards called Eden in the
    loaded content.
    """

    starting_item: str = ""
    """
    The item this seat begins with, instead of the one its character prints.

    Empty means the printed one, which is what a table does.
    """

    coins: int | None = None
    loot: int | None = None
    """
    What this seat is dealt when the game starts.

    ``None`` means whatever the game deals everybody. These are per seat rather
    than per game because "what if one player starts rich" is a question
    somebody will want to ask, and a single number cannot express it.
    """

    def to_dict(self) -> dict[str, Any]:
        written: dict[str, Any] = {}

        if self.name:
            written["name"] = self.name

        if self.character:
            written["character"] = self.character

        if self.starting_item:
            written["starting_item"] = self.starting_item

        if self.coins is not None:
            written["coins"] = self.coins

        if self.loot is not None:
            written["loot"] = self.loot

        return written


@dataclass(frozen=True, slots=True)
class Content:
    """
    Which cards are in the game.

    There is no ``root`` here and there must not be. Where the content lives is
    where the tool was pointed; a filesystem path inside a file that people
    share is broken on somebody else's machine at best.
    """

    expansions: tuple[str, ...] = ()
    """
    The sets to deal from. Empty means every set the content root holds, which
    is what FSME has always done.
    """

    exclude_cards: tuple[str, ...] = ()
    """
    Cards to leave out, by identifier. The same question `fsme test-card` asks:
    the game as it would be if this had never been printed.
    """

    def to_dict(self) -> dict[str, Any]:
        written: dict[str, Any] = {}

        if self.expansions:
            written["expansions"] = list(self.expansions)

        if self.exclude_cards:
            written["exclude_cards"] = list(self.exclude_cards)

        return written


@dataclass(frozen=True, slots=True)
class Table:
    """
    The numbers the rules already treat as belonging to a game.

    All three are parameters of ``rules.setup.new_game`` and fields of
    GameState, which is why they can be set at all: a constant cannot be
    changed for one game, and these were never constants.
    """

    souls_to_win: int | None = None
    monster_slots: int | None = None
    shop_slots: int | None = None

    def to_dict(self) -> dict[str, Any]:
        written: dict[str, Any] = {}

        for name in ("souls_to_win", "monster_slots", "shop_slots"):
            value = getattr(self, name)

            if value is not None:
                written[name] = value

        return written


@dataclass(frozen=True, slots=True)
class Scenario:
    """
    One experiment's starting configuration.
    """

    name: str = ""
    description: str = ""

    seed: int | None = None
    """
    The seed to deal with, when nothing else says otherwise.

    A default rather than part of the scenario's identity: a study runs one
    scenario over a thousand seeds, and a seed folded into the scenario would
    make that run meaningless. What names one game is the pair — this
    scenario, that seed.
    """

    interactive_priority: bool | None = None
    """
    Whether the table is offered priority after every push.

    Part of the scenario because it is part of the game: a seed names one game
    *per path*, and a game watched is not the game simulated from the same
    seed. ``None`` leaves it to whoever is running.
    """

    content: Content = field(default_factory=Content)
    table: Table = field(default_factory=Table)

    players: tuple[Seat, ...] = ()
    """
    The seats, in order. Empty means "deal as usual" — the number of players is
    then whoever is running the game, exactly as today.
    """

    @property
    def is_empty(self) -> bool:
        """
        Whether this scenario asks for anything at all.

        An empty scenario and no scenario must be the same game. This is what
        lets the engine take the argument everywhere without any existing
        measurement moving.
        """
        return self == Scenario(name=self.name, description=self.description)

    def with_seed(self, seed: int) -> Scenario:
        """
        The same scenario dealt from a different seed.
        """
        return replace(self, seed=int(seed))

    def to_dict(self) -> dict[str, Any]:
        """
        Write the scenario back out, leaving out everything it did not ask for.

        A scenario that said nothing round-trips to two keys, not to a page of
        nulls: the file is meant to be read and edited by a person.
        """
        written: dict[str, Any] = {"format": FORMAT, "version": VERSION}

        if self.name:
            written["name"] = self.name

        if self.description:
            written["description"] = self.description

        if self.seed is not None:
            written["seed"] = self.seed

        if self.interactive_priority is not None:
            written["interactive_priority"] = self.interactive_priority

        content = self.content.to_dict()

        if content:
            written["content"] = content

        table = self.table.to_dict()

        if table:
            written["table"] = table

        if self.players:
            written["players"] = [seat.to_dict() for seat in self.players]

        return written


def digest_of(scenario: Scenario | None) -> str:
    """
    A short fingerprint of what a scenario asks for.

    Over the written form rather than the object, and with the keys sorted, so
    two scenarios that ask for the same thing fingerprint the same however they
    were built or spelled. ``""`` for no scenario, which is the same answer as
    for a scenario that asks for nothing — because they are the same game.

    What it is for: telling two experiments apart at a glance, and noticing
    that a journal's inlined scenario has been edited since. It is not a
    security measure and is not meant as one.
    """
    if scenario is None or scenario.is_empty:
        return ""

    written = json.dumps(scenario.to_dict(), sort_keys=True, separators=(",", ":"))

    return hashlib.sha256(written.encode("utf-8")).hexdigest()[:16]


def _seat(data: Mapping[str, Any]) -> Seat:
    return Seat(
        name=str(data.get("name", "")),
        character=str(data.get("character", "")),
        starting_item=str(data.get("starting_item", "")),
        coins=None if data.get("coins") is None else int(data["coins"]),
        loot=None if data.get("loot") is None else int(data["loot"]),
    )


def from_dict(data: Mapping[str, Any]) -> Scenario:
    """
    Build a scenario from data already known to be valid.

    Validation is `scenario.file.validate`, and it runs first. This reads;
    it does not check, and it does not repair.
    """
    content = data.get("content") or {}
    table = data.get("table") or {}
    players: Sequence[Any] = data.get("players") or ()

    return Scenario(
        name=str(data.get("name", "")),
        description=str(data.get("description", "")),
        seed=None if data.get("seed") is None else int(data["seed"]),
        interactive_priority=(
            None
            if data.get("interactive_priority") is None
            else bool(data["interactive_priority"])
        ),
        content=Content(
            expansions=tuple(str(name) for name in content.get("expansions", ())),
            exclude_cards=tuple(
                str(card) for card in content.get("exclude_cards", ())
            ),
        ),
        table=Table(
            souls_to_win=(
                None if table.get("souls_to_win") is None
                else int(table["souls_to_win"])
            ),
            monster_slots=(
                None if table.get("monster_slots") is None
                else int(table["monster_slots"])
            ),
            shop_slots=(
                None if table.get("shop_slots") is None
                else int(table["shop_slots"])
            ),
        ),
        players=tuple(_seat(seat) for seat in players),
    )
