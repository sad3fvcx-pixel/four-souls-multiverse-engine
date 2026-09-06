# src/fsme/replay/recorder.py

"""
Recording a game as it is played.
"""

from __future__ import annotations

from types import MappingProxyType

from fsme.commands import Command, CommandResult
from fsme.runtime import Runtime

from .digest import state_digest
from .recording import RecordedCommand, Recording


class Recorder:
    """
    Submits commands to a game and writes down the ones that were accepted.

    Rejected commands are not recorded. They changed nothing, so replaying
    them would only be replaying the client's mistakes; the recording is of
    the game, not of the session.
    """

    def __init__(self, runtime: Runtime, *, content_version: str = "") -> None:
        self._runtime = runtime
        self._content_version = content_version
        self._commands: list[RecordedCommand] = []

    @property
    def runtime(self) -> Runtime:
        return self._runtime

    def __len__(self) -> int:
        return len(self._commands)

    def submit(self, command: Command) -> CommandResult:
        """
        Send a command to the game and record it if it was accepted.
        """
        result = self._runtime.submit(command)

        if result.accepted:
            self._commands.append(
                RecordedCommand(
                    type=command.type,
                    player=command.player,
                    payload=MappingProxyType(dict(command.payload)),
                    digest=state_digest(self._runtime.state),
                )
            )

        return result

    def recording(self) -> Recording:
        """
        Return the sealed recording of everything accepted so far.
        """
        return Recording(
            seed=self._runtime.state.seed,
            commands=tuple(self._commands),
            content_version=self._content_version,
        ).sealed()
