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

from fsme.commands import Command, CommandType
from fsme.content import ContentLibrary
from fsme.game import Game
from fsme.replay import state_digest

from .entry import Journal


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

        return (
            f"entry {self.index} ({self.command}) left the game in a different "
            f"state than it did when the journal was kept"
        )


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

    ``interactive_priority`` left unset is worked out from the journal. It has
    to match how the game was played or the positions differ from the first
    command: an interactive game opens a window after every push and records
    the passes that close it, and replaying those into a game that never opens
    one is replaying a different game. The journal does not say which it was —
    that is the honest gap here, and recording it belongs with the rest of the
    journal work — so it is read off what the journal contains. Pass an
    explicit value to override the reading.
    """
    if interactive_priority is None:
        interactive_priority = _was_interactive(journal)

    game = Game.from_content(
        library,
        list(journal.players),
        seed=journal.seed,
        interactive_priority=interactive_priority,
    )

    if not _deals_itself(journal):
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
                    reason=f"the engine now refuses it: {result.reason}",
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
                ),
            )

    return Playback(game=game, replayed=played)


def _deals_itself(journal: Journal) -> bool:
    """
    Whether this journal records the deal as its own first command.

    Read off the journal rather than configured, because it is a fact about the
    file in hand and not a choice the caller should have to make correctly.
    """
    return bool(journal.entries) and (
        journal.entries[0].command == str(CommandType.START_GAME)
    )


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
    if _deals_itself(journal):
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
