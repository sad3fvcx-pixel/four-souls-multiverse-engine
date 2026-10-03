# src/fsme/journal/replay.py

"""
Playing a journal back.

A journal holds the commands, so it can be replayed; it holds a fingerprint of
the position after each of them, so a replay can say *where* it went wrong
rather than only that it did. Both matter, and the second is the one that makes
a journal worth keeping: a game that no longer replays is a game whose engine
changed under it, and the entry that first disagrees is the change.

The commands go through the ordinary engine. There is no replay path, and there
must not be one — a shortcut would prove the shortcut works.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fsme import __version__
from fsme.commands import Command, CommandType
from fsme.content import ContentLibrary
from fsme.game import Game
from fsme.replay import state_digest
from fsme.replay.player import which_engines
from fsme.scenario import Scenario, parse

from .entry import Journal

_ANOTHER_GAME = (
    "left the game in a different state than it did when the journal was kept"
)
"""
What a digest divergence is, in words. Said on its own when there is nothing
to add, and first when there is, so the fact is never replaced by its context.
"""


@dataclass(frozen=True, slots=True)
class Divergence:
    """
    The first command whose outcome no longer matches what was written down.
    """

    index: int
    command: str
    player: int

    expected: str
    found: str

    reason: str = ""

    def __str__(self) -> str:
        if self.reason:
            return f"entry {self.index} ({self.command}): {self.reason}"

        return f"entry {self.index} ({self.command}) {_ANOTHER_GAME}"


@dataclass(frozen=True, slots=True)
class Playback:
    """
    What came of replaying a journal.
    """

    game: Game
    replayed: int
    divergence: Divergence | None = None

    @property
    def faithful(self) -> bool:
        return self.divergence is None


def replay_journal(
    journal: Journal,
    library: ContentLibrary,
    *,
    interactive_priority: bool | None = None,
    stop_at: int | None = None,
) -> Playback:
    """
    Deal the same game and play the journal's commands into it.

    ``stop_at`` replays only the first N commands, which is what a reader
    stepping through a game wants: the position as it stood at any point, built
    by the engine rather than stored.

    A divergence stops the playback where it happened. Going on would be
    replaying a different game, and reporting the end of a different game as
    the end of this one is worse than reporting nothing.

    Journals come in two shapes and both are replayed. A game played through a
    Session — which is what Watch does, and what Save journal writes — records
    the deal as its first command, because the keeper is watching before the
    cards are dealt. A simulation's keeper starts after the deal, so its
    journal begins at the first move. Dealing here *and* replaying a recorded
    deal would be dealing twice, so the deal is done here only when the journal
    does not carry one.

    That asymmetry is on the list to remove. Until it is, this reads both,
    which is what makes a game saved from Watch openable by ``fsme replay`` —
    it was not, and the two shipped features could not be used together.

    ``interactive_priority`` has to match how the game was played or the
    positions differ from the first command: an interactive game opens a window
    after every push and records the passes that close it, and replaying those
    into a game that never opens one is replaying a different game. A journal
    of format 2 says which it was and is believed. An older one does not, and
    is read the way it always was — from whether it records a deal or holds a
    pass — which is inference and is marked as inference where it is made.

    **The scenario comes out of the journal, never from a file.** A journal is
    the record of one game, and a record that needed an external file which may
    since have been edited would not be one: an experiment saved today has to
    replay next year with nothing beside it. A journal written before scenarios
    existed has none, which is a true statement about it rather than a missing
    field, and it replays as the ordinary game it was.
    """
    if interactive_priority is None:
        interactive_priority = how_it_was_played(journal)

    content = why_the_content_differs(journal, library)
    engine = why_the_engine_differs(journal)

    game = Game.from_content(
        library,
        list(journal.players),
        seed=journal.seed,
        interactive_priority=interactive_priority,
        scenario=scenario_of(journal),
    )

    if not deals_itself(journal):
        game.start()

    played = 0

    for entry, (kind, player, payload) in zip(
        journal.entries, journal.commands(), strict=True
    ):
        if stop_at is not None and played >= stop_at:
            break

        result = game.submit(Command(type=kind, player=player, payload=dict(payload)))

        if not result.accepted:
            return Playback(
                game=game,
                replayed=played,
                divergence=Divergence(
                    index=entry.index,
                    command=entry.command,
                    player=entry.player,
                    expected="accepted",
                    found="rejected",
                    reason=_because(
                        f"the engine now refuses it: {result.reason}", content, engine
                    ),
                ),
            )

        played += 1

        found = state_digest(game.state)

        if entry.digest and found != entry.digest:
            return Playback(
                game=game,
                replayed=played,
                divergence=Divergence(
                    index=entry.index,
                    command=entry.command,
                    player=entry.player,
                    expected=entry.digest,
                    found=found,
                    reason=(
                        _because(f"it {_ANOTHER_GAME}", content, engine)
                        if content or engine
                        else ""
                    ),
                ),
            )

    return Playback(game=game, replayed=played)


def why_the_content_differs(journal: Journal, library: ContentLibrary) -> str:
    """
    What to say about the content if this replay comes out differently.

    A journal records what it was played against — every set and the version
    its manifest claimed. Until now nothing read it back, so a game replayed
    against changed content reported a state digest that did not match and
    stopped there, which tells the reader that something is different and
    nothing about what.

    The comparison is of manifest versions and not of a fingerprint over the
    cards, which is the decision ``ContentLibrary.identity`` was written for
    and this does not revisit. Two libraries with the same identity are not
    proven identical, so this cannot see a card edited without its manifest
    version changing; two with different ones are proven different, which is
    the half somebody looking for the reason can act on.

    An empty string means there is nothing to say — either the journal records
    no content, or the two identities agree. It does not mean the content is
    the same, and nothing here claims that it is.
    """
    written = journal.content_version

    if not written:
        return ""

    here = library.identity()

    if written == here:
        return ""

    return (
        f"the content is not what this was played against — "
        f"the journal says {written}, this library is {here}"
    )


def why_the_engine_differs(journal: Journal) -> str:
    """
    What to say about the engine if this replay comes out differently.

    The same question as the content one above and answered in the same
    spirit, with one difference that follows from what a release number is.
    Content has an identity per set, so two that agree say nothing; a release
    number is written once per release, and a replay that diverges between two
    builds carrying the same one is exactly the case somebody is looking at
    when they read this. So equal numbers are named rather than left out, and
    named as proving nothing — see ``which_engines``, which both replay paths
    share so that they cannot come to say different things.

    The number is the journal's own ``engine`` field, read as it was written.
    """
    return which_engines(journal.engine_version, __version__)


def _because(*said: str) -> str:
    """
    One reason out of several, leaving out the ones with nothing to say.

    ``Divergence.reason`` is a single string, and a refusal, a content note and
    an engine note can all be true of the same entry. They go in that order —
    what happened first, then what might explain it — and none replaces another.
    """
    return "; ".join(part for part in said if part)


def deals_itself(journal: Journal) -> bool:
    """
    Whether this journal records the deal as its own first command.

    Read off the journal rather than configured, because it is a fact about the
    file in hand and not a choice the caller should have to make correctly.
    """
    return bool(journal.entries) and (
        journal.entries[0].command == str(CommandType.START_GAME)
    )


def scenario_of(journal: Journal) -> Scenario | None:
    """
    The scenario this journal was played under, read back out of it.

    Parsed rather than trusted. The snapshot in a journal is data somebody may
    have edited, and a scenario that no longer validates should be refused by
    name here rather than dealt as something nobody wrote.
    """
    if journal.scenario is None:
        return None

    return parse(journal.scenario, where="the scenario recorded in this journal")


def how_it_was_played(journal: Journal) -> bool:
    """
    Whether the game offered priority to the table.

    Believed when the journal says so, inferred when it does not. A journal of
    format 1 predates the field; everything written since carries it.
    """
    if journal.interactive_priority is not None:
        return journal.interactive_priority

    return _was_interactive(journal)


def _was_interactive(journal: Journal) -> bool:
    """
    Whether this journal came from a game that offered priority to the table.

    Two signs, either of which settles it. Passing priority is a command that
    only exists when somebody was given the chance — a headless game opens no
    window, so its journal holds no passes. And recording the deal means the
    journal was kept by a Session, which is the interactive path.

    Neither is a field saying so, because there is no such field. This is
    inference, and it is written down as inference so that the day it is wrong
    somebody knows where to look.
    """
    if deals_itself(journal):
        return True

    passing = str(CommandType.PASS_PRIORITY)

    return any(entry.command == passing for entry in journal.entries)


def summarise(playback: Playback, journal: Journal) -> dict[str, Any]:
    """
    Say how a playback went, in the few facts worth printing.
    """
    return {
        "commands": len(journal),
        "replayed": playback.replayed,
        "faithful": playback.faithful,
        "divergence": None if playback.faithful else str(playback.divergence),
        "over": bool(playback.game.state.game_over),
        "winner": playback.game.state.winner,
    }
