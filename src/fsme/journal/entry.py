# src/fsme/journal/entry.py

"""
What a game did, written down so that it can be explained.

A replay already answers "what was played": a seed and a list of commands, from
which the engine reproduces the game exactly. That is enough to *reproduce* a
game and not nearly enough to *understand* one — it says a player attacked, and
says nothing about what else they could have done, what the queue looked like
when they did it, or what came of it.

A journal is the same game with those things kept. One entry per accepted
command: the position it was made from, what the engine would have accepted
instead, the command itself, and every event it caused. Nothing here is
computed by this module — all of it is what the engine already produced, kept
instead of discarded.

Two things follow from that, and both are the point. A journal is a replay,
because it holds the commands: anything recorded can be played back through the
ordinary engine. And a journal is data, because it holds the events: counting
what happened across ten thousand of them is reading, not instrumenting.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fsme.commands import CommandType
from fsme.rng.rng import KEYED_MODEL, LEGACY_MODEL

JOURNAL_FORMAT_VERSION = "3"
"""
The format this build writes.

Two, because a journal carries the scenario the game was set up from, and a
build that did not know about scenarios would read one, ignore the field, deal
an ordinary game and report a divergence it could not explain. Bumping turns
that silent wrong answer into a refusal by name.

Three, because some entries carry a full digest as well
(``Entry.full_digest``), and a build that ignored it would call a game faithful
that its own record says came out differently.
"""

KEYED_JOURNAL_FORMAT = "4"
"""
The format of a journal of a game played on RNG model 2.

Format 3 with one more key, ``rng_model``. A game on model 1 is still written
in format 3, exactly as before; a build that knows only model 1 would deal a
model 2 game on the wrong generator, so it is made to refuse one by name.
"""

READABLE_FORMATS = frozenset({"1", "2", "3", KEYED_JOURNAL_FORMAT})
"""
The formats this build can read.

A version-1 journal is a journal from before scenarios existed, which means it
has no scenario — a true statement about it, not a missing field. So it reads,
replays and says so, and nothing anybody has already recorded is orphaned by
the bump. Versions 1 and 2 hold no full digests, and are checked the way they
always were: by the cheap one, after every command.
"""


class JournalFormatError(ValueError):
    """
    A journal file could not be read.
    """


@dataclass(frozen=True, slots=True)
class Position:
    """
    The state of the game at one moment, in the few numbers a reader needs.

    Not a save: a save is for continuing a game and holds every card in every
    zone. This is for reading, and holds what a person looking at a turn wants
    to see without scrolling.
    """

    turn: int = 0
    phase: str = ""
    active_player: int = 0

    waiting_kind: str = ""
    waiting_player: int | None = None

    stack: tuple[str, ...] = ()

    players: tuple[Mapping[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn": self.turn,
            "phase": self.phase,
            "active_player": self.active_player,
            "waiting_kind": self.waiting_kind,
            "waiting_player": self.waiting_player,
            "stack": list(self.stack),
            "players": [dict(player) for player in self.players],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Position:
        return cls(
            turn=int(data.get("turn", 0)),
            phase=str(data.get("phase", "")),
            active_player=int(data.get("active_player", 0)),
            waiting_kind=str(data.get("waiting_kind", "")),
            waiting_player=(
                None
                if data.get("waiting_player") is None
                else int(data["waiting_player"])
            ),
            stack=tuple(str(item) for item in data.get("stack", ())),
            players=tuple(dict(player) for player in data.get("players", ())),
        )


@dataclass(frozen=True, slots=True)
class Happening:
    """
    One event, flattened to the words it would be read in.
    """

    type: str
    source: str | None = None

    source_id: str | None = None
    """
    The identifier of the card this came from, when a card did.

    The name is for reading and this is for counting. Two sets print cards with
    the same name and different rules — the alternate Larry Jr. is not the
    printed one — and a tally that added them together would be measuring a
    word rather than a card.
    """

    controller: int | None = None
    targets: tuple[str, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        written: dict[str, Any] = {
            "type": self.type,
            "source": self.source,
            "controller": self.controller,
            "targets": list(self.targets),
            "payload": dict(self.payload),
        }

        if self.source_id:
            written["source_id"] = self.source_id

        return written

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Happening:
        return cls(
            type=str(data.get("type", "")),
            source=data.get("source"),
            source_id=data.get("source_id"),
            controller=(
                None if data.get("controller") is None else int(data["controller"])
            ),
            targets=tuple(str(target) for target in data.get("targets", ())),
            payload=dict(data.get("payload", {})),
        )


@dataclass(frozen=True, slots=True)
class Entry:
    """
    One accepted command, with everything that made it and everything it made.
    """

    index: int

    command: str = ""
    player: int = 0
    payload: Mapping[str, Any] = field(default_factory=dict)

    label: str = ""
    """
    The move in words, when the client that submitted it had words for it.

    A client offers "Attack Monstro" and submits ``attack index=0``; keeping the
    first makes the journal readable, and keeping the second makes it playable.
    """

    before: Position = field(default_factory=Position)
    """Where the game stood when this was chosen."""

    offered: tuple[str, ...] = ()
    """
    What else the engine would have accepted at that moment.

    Empty when the journal was kept without them. Recording the alternatives
    costs asking the engine about every conceivable move before every real one,
    which is worth it for a game somebody will read and not for the ten
    thousandth game of a simulation.
    """

    events: tuple[Happening, ...] = ()

    decision: Mapping[str, Any] | None = None
    """
    The working a bot showed for this move, when a bot made it.

    Kept as it was handed over rather than reshaped: it is the bot's own
    arithmetic, and a journal that tidied it would no longer be evidence about
    the bot. Empty for a move made by a person or by a player that does not
    reason.
    """

    digest: str = ""
    """
    Fingerprint of the game once the command had been carried out.

    The same fingerprint a replay compares against, so a journal can be
    replayed and diverge loudly at the command that diverged.
    """

    full_digest: str = ""
    """
    The full fingerprint of the game once the command had been carried out.

    ``state_digest_v2``, which sees what ``digest`` does not — how long an
    attack has gone without a hit, what a stack object carries, the counters on
    a card. It is taken after every eighth command and after the last, and is
    empty everywhere else: an entry without one is not a gap.
    """

    def to_dict(self) -> dict[str, Any]:
        written: dict[str, Any] = {
            "index": self.index,
            "command": self.command,
            "player": self.player,
            "payload": dict(self.payload),
            "before": self.before.to_dict(),
            "events": [event.to_dict() for event in self.events],
            "digest": self.digest,
        }

        if self.full_digest:
            written["full_digest"] = self.full_digest

        if self.label:
            written["label"] = self.label

        if self.offered:
            written["offered"] = list(self.offered)

        if self.decision is not None:
            written["decision"] = dict(self.decision)

        return written

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Entry:
        try:
            return cls(
                index=int(data["index"]),
                command=str(data["command"]),
                player=int(data.get("player", 0)),
                payload=dict(data.get("payload", {})),
                label=str(data.get("label", "")),
                before=Position.from_dict(data.get("before", {})),
                offered=tuple(str(move) for move in data.get("offered", ())),
                events=tuple(
                    Happening.from_dict(event) for event in data.get("events", ())
                ),
                decision=(
                    dict(data["decision"]) if data.get("decision") is not None else None
                ),
                digest=str(data.get("digest", "")),
                full_digest=str(data.get("full_digest", "")),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise JournalFormatError(f"unreadable journal entry: {error}") from error


@dataclass(slots=True)
class Journal:
    """
    A whole game, written down.

    Mutable while a game is being played and plain data afterwards. It is the
    one artefact three different jobs share: reading a game, replaying it, and
    counting things across thousands of them.
    """

    seed: int = 0

    players: tuple[str, ...] = ()
    characters: tuple[str, ...] = ()

    engine_version: str = ""
    """
    The release of FSME that played this game, as the keeper stamped it.

    Empty in a journal written before anything filled it in. Read back as a
    string whatever the file held, so it is data rather than a version until
    something checks: a replay that diverges names it, and does not treat two
    equal release numbers as proof that the engines were the same.
    """

    content_version: str = ""
    """
    What content this game was dealt from: every set and its manifest version.

    Empty in a journal kept before anything filled it in, and in one kept
    without a library to ask. Its job is to let a replay that diverges say
    *why* — the digest already proves the game came out differently, and this
    is the first thing anybody would want to check.
    """

    scenario: Mapping[str, Any] | None = None
    """
    The scenario this game was set up from, written out in full.

    In full, and not by reference: a record that needs a file which may since
    have been edited is not a record. A journal is the source of truth for the
    game it describes, so the experiment travels inside it and the original
    `scenario.json` can be deleted without anything breaking.

    ``None`` means no scenario — an ordinary game, or a journal from format 1.
    """

    scenario_digest: str = ""
    """
    A fingerprint of the scenario above, for telling experiments apart.

    Over what the scenario asks the engine for, so renaming or reseeding an
    experiment does not make it a different one, and changing what it sets up
    always does.
    """

    scenario_id: str = ""
    """
    What the experiment was called, if it was called anything.

    Written down so a report can say which experiment it came from, and for no
    other reason: nothing reads it to rebuild a game. A journal must not depend
    on a library still holding the scenario — the whole snapshot is here, and
    deleting the library breaks nothing.
    """

    rng_model: str = "1"
    """
    The generator the game was dealt and played on. Model 1 unless the journal
    is in format 4, which is how a model 2 game is written down.
    """

    interactive_priority: bool | None = None
    """
    Whether the table was offered priority after every push.

    It changes the game — a seed names one game per path — and until this field
    existed replay had to work it out from what the journal contained. ``None``
    means the journal does not say, which is every journal of format 1, and
    replay falls back to the inference it always used.
    """

    entries: list[Entry] = field(default_factory=list)

    outcome: Mapping[str, Any] = field(default_factory=dict)
    """
    How the game ended, when it did.

    A journal of an unfinished game has an empty outcome, which is a true
    statement about it rather than a missing field.
    """

    def __len__(self) -> int:
        return len(self.entries)

    def add(self, entry: Entry) -> Entry:
        self.entries.append(entry)

        return entry

    def to_dict(self) -> dict[str, Any]:
        keyed = self.rng_model == KEYED_MODEL

        written: dict[str, Any] = {
            "format": KEYED_JOURNAL_FORMAT if keyed else JOURNAL_FORMAT_VERSION,
            "engine": self.engine_version,
            "content": self.content_version,
            "seed": self.seed,
            "players": list(self.players),
            "characters": list(self.characters),
            "outcome": dict(self.outcome),
            "entries": [entry.to_dict() for entry in self.entries],
        }

        # Left out when there is nothing to say, so an ordinary game's journal
        # does not grow three keys that all mean "no".
        if self.scenario is not None:
            written["scenario"] = dict(self.scenario)

        if self.scenario_digest:
            written["scenario_digest"] = self.scenario_digest

        if self.scenario_id:
            written["scenario_id"] = self.scenario_id

        if self.interactive_priority is not None:
            written["interactive_priority"] = self.interactive_priority

        if keyed:
            written["rng_model"] = KEYED_MODEL

        return written

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Journal:
        written = str(data.get("format", ""))

        if written not in READABLE_FORMATS:
            readable = ", ".join(sorted(READABLE_FORMATS))

            raise JournalFormatError(
                f"this journal is written in format {written or '?'}, "
                f"and this engine reads {readable}"
            )

        scenario = data.get("scenario")

        return cls(
            seed=int(data.get("seed", 0)),
            rng_model=_rng_model(data, written),
            players=tuple(str(name) for name in data.get("players", ())),
            characters=tuple(str(name) for name in data.get("characters", ())),
            engine_version=str(data.get("engine", "")),
            content_version=str(data.get("content", "")),
            scenario=None if scenario is None else dict(scenario),
            scenario_digest=str(data.get("scenario_digest", "")),
            scenario_id=str(data.get("scenario_id", "")),
            interactive_priority=(
                None
                if data.get("interactive_priority") is None
                else bool(data["interactive_priority"])
            ),
            entries=[Entry.from_dict(entry) for entry in data.get("entries", ())],
            outcome=dict(data.get("outcome", {})),
        )

    def save(self, path: Path | str) -> Path:
        """
        Write the journal to a file.
        """
        where = Path(path)

        where.parent.mkdir(parents=True, exist_ok=True)
        where.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

        return where

    @classmethod
    def load(cls, path: Path | str) -> Journal:
        """
        Read a journal back.
        """
        where = Path(path)

        try:
            data = json.loads(where.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise JournalFormatError(f"{where} is not JSON: {error}") from None

        if not isinstance(data, Mapping):
            raise JournalFormatError(f"{where} does not hold a journal")

        return cls.from_dict(data)

    def commands(self) -> Sequence[tuple[CommandType, int, dict[str, Any]]]:
        """
        The commands, in order, ready to be submitted again.
        """
        replayable: list[tuple[CommandType, int, dict[str, Any]]] = []

        for entry in self.entries:
            try:
                kind = CommandType(entry.command)
            except ValueError as error:
                raise JournalFormatError(
                    f"entry {entry.index} names a command this engine does not "
                    f"have: {entry.command}"
                ) from error

            replayable.append((kind, entry.player, dict(entry.payload)))

        return replayable


def _rng_model(data: Mapping[str, Any], written: str) -> str:
    """
    Which generator a journal's game was played on.

    Format 4 is a model 2 journal and has to say so; every older format is
    model 1, and a key claiming otherwise is refused rather than believed.
    """
    said = data.get("rng_model")

    if written == KEYED_JOURNAL_FORMAT:
        if said != KEYED_MODEL:
            raise JournalFormatError(
                f"this journal is written in format {KEYED_JOURNAL_FORMAT}, which is "
                f"a game played on RNG model {KEYED_MODEL}, and it does not say so"
            )

        return KEYED_MODEL

    if said is not None:
        raise JournalFormatError(
            f"this journal is written in format {written}, which has no rng_model; "
            f"a game on another RNG model is written in format {KEYED_JOURNAL_FORMAT}"
        )

    return LEGACY_MODEL
