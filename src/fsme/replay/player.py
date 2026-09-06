# src/fsme/replay/player.py

"""
Playing a recording back.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from fsme.cards import CardRegistry
from fsme.rng.rng import RNG
from fsme.runtime import Runtime
from fsme.state import GameState

from .digest import state_digest
from .errors import ReplayDivergence, ReplayRejectedCommand
from .recording import Recording

StateFactory = Callable[[], GameState]


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
                raise ReplayDivergence(
                    f"command {self._position} ({entry.type}) produced a "
                    f"different game: recorded {entry.digest}, "
                    f"reproduced {reproduced}"
                )

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
