# src/fsme/replay/player.py

"""
Playing a recording back.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from enum import StrEnum

from fsme import __version__
from fsme.cards import CardRegistry
from fsme.rng.rng import RNG
from fsme.runtime import Runtime
from fsme.state import GameState

from .digest import state_digest
from .errors import ReplayDivergence, ReplayRejectedCommand
from .recording import Recording

StateFactory = Callable[[], GameState]

_RELEASE = re.compile(r"\d+(?:\.\d+)+(?:[-+.]?[0-9A-Za-z]+)*")
"""
What a release number looks like: two or more dotted numbers, and whatever
pre-release or local suffix may follow them.

Anything else in the field is not a version, whatever it says. A journal
written with ``"engine": null`` reads back as the four letters ``None`` —
the reader turns every value into a string — and a check that only asked
whether the field was empty would take that for a release it could compare.
"""


def which_engines(recorded: object, running: object) -> str:
    """
    What can honestly be said about the two engines behind a replay.

    ``recorded`` is what the record says it was played by, which is data from a
    file and may be anything at all; ``running`` is the engine doing the
    replaying. The answer names what each side says and claims no more than
    that.

    It never says the engine changed. Two different release numbers prove the
    game was played and replayed by two different releases, which is worth
    knowing, and prove nothing about why it came out differently. Two equal
    ones prove still less: a release number is written once per release, and
    the rules can change between two commits that both carry it. So equal
    numbers are named as equal and nothing is concluded from them.

    Every value is quoted with ``repr``, which escapes line breaks and other
    control characters: a field that is supposed to hold ``0.10.0`` can hold
    a paragraph, and printing it as it stands would let a file rewrite the
    report it appears in.

    An empty string means neither side said anything this could repeat.
    """
    theirs = _release(recorded)
    ours = _release(running)

    if theirs is None and ours is None:
        return ""

    if theirs is not None and ours is not None:
        if theirs == ours:
            return (
                f"the journal and this engine both say {theirs!r}, which does "
                f"not show that the two are the same"
            )

        return f"the journal was played by engine {theirs!r}, and this is {ours!r}"

    if theirs is None:
        return (
            f"{_unread(recorded, 'the journal', 'which engine played it')}; "
            f"this is engine {ours!r}"
        )

    return (
        f"the journal was played by engine {theirs!r}; "
        f"{_unread(running, 'this engine', 'which release it is')}"
    )


def _release(value: object) -> str | None:
    """
    The value as a release number, or ``None`` if it is not one.
    """
    if isinstance(value, str) and _RELEASE.fullmatch(value):
        return value

    return None


def _unread(value: object, who: str, unsaid: str) -> str:
    """
    Say that one side named no release, without turning that into a difference.
    """
    if value is None or value == "":
        return f"{who} does not say {unsaid}"

    return f"{who} names its engine as {str(value)!r}, which is not a release number"


class ReplayStatus(StrEnum):
    """
    Where a playback has got to.
    """

    READY = "ready"
    PLAYING = "playing"
    PAUSED = "paused"
    FINISHED = "finished"
    STOPPED = "stopped"


class ReplayPlayer:
    """
    Reruns a recording through the ordinary engine.

    There is no separate replay path: the commands go through the same
    validation, the same rules and the same stack they went through when the
    game was played. That is the only way a replay can be evidence of anything
    — a shortcut would prove the shortcut works, not the engine.

    The starting position comes from a factory rather than from the file. The
    recording holds the seed and the commands; how the table was laid out is
    the caller's business, because the same recording should replay against
    content loaded the same way.
    """

    def __init__(
        self,
        recording: Recording,
        state_factory: StateFactory,
        *,
        cards: CardRegistry | None = None,
        verify: bool = True,
    ) -> None:
        recording.check_compatibility()
        recording.verify()

        self._recording = recording
        self._factory = state_factory
        self._cards = cards
        self._verify = verify

        self._runtime: Runtime = self._build()
        self._position = 0
        self._status = ReplayStatus.READY

    def _build(self) -> Runtime:
        state = self._factory()
        state.seed = self._recording.seed

        return Runtime(state, cards=self._cards, rng=RNG(state.seed))

    @property
    def runtime(self) -> Runtime:
        return self._runtime

    @property
    def state(self) -> GameState:
        return self._runtime.state

    @property
    def recording(self) -> Recording:
        return self._recording

    @property
    def position(self) -> int:
        """
        How many commands have been replayed.
        """
        return self._position

    @property
    def status(self) -> ReplayStatus:
        return self._status

    @property
    def finished(self) -> bool:
        return self._position >= len(self._recording.commands)

    def reset(self) -> None:
        """
        Return to the starting position.
        """
        self._runtime = self._build()
        self._position = 0
        self._status = ReplayStatus.READY

    def step(self) -> bool:
        """
        Replay one command. Returns False when there are none left.
        """
        if self._status is ReplayStatus.STOPPED or self.finished:
            self._status = (
                ReplayStatus.STOPPED
                if self._status is ReplayStatus.STOPPED
                else ReplayStatus.FINISHED
            )

            return False

        entry = self._recording.commands[self._position]
        result = self._runtime.submit(entry.to_command())

        if result.rejected:
            raise ReplayRejectedCommand(
                f"command {self._position} ({entry.type}) was refused during "
                f"playback: {result.reason}"
            )

        if self._verify and entry.digest:
            reproduced = state_digest(self._runtime.state)

            if reproduced != entry.digest:
                said = (
                    f"command {self._position} ({entry.type}) produced a "
                    f"different game: recorded {entry.digest}, "
                    f"reproduced {reproduced}"
                )
                engines = which_engines(self._recording.engine_version, __version__)

                raise ReplayDivergence(f"{said}; {engines}" if engines else said)

        self._position += 1
        self._status = (
            ReplayStatus.FINISHED if self.finished else ReplayStatus.PAUSED
        )

        return True

    def play(self) -> None:
        """
        Replay every remaining command.
        """
        self._status = ReplayStatus.PLAYING

        while self.step():
            pass

    def pause(self) -> None:
        """
        Stop advancing, keeping the position.
        """
        if self._status is ReplayStatus.PLAYING:
            self._status = ReplayStatus.PAUSED

    def stop(self) -> None:
        """
        End playback where it stands.
        """
        self._status = ReplayStatus.STOPPED


def replay(
    recording: Recording,
    state_factory: StateFactory,
    *,
    cards: CardRegistry | None = None,
    verify: bool = True,
) -> ReplayPlayer:
    """
    Replay a recording to the end and return the finished player.
    """
    player = ReplayPlayer(
        recording, state_factory, cards=cards, verify=verify
    )
    player.play()

    return player
