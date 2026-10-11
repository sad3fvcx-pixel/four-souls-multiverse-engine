# src/fsme/replay/recorder.py

"""
Recording a game as it is played.
"""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

from fsme.commands import Command, CommandResult
from fsme.rng.rng import KEYED_MODEL
from fsme.runtime import Runtime

from .digest import full_checkpoint, state_digest, state_digest_v2
from .recording import (
    KEYED_REPLAY_FORMAT,
    REPLAY_FORMAT_VERSION,
    RecordedCommand,
    Recording,
)


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
            index = len(self._commands)

            self._commands.append(
                RecordedCommand(
                    type=command.type,
                    player=command.player,
                    payload=MappingProxyType(dict(command.payload)),
                    digest=state_digest(self._runtime.state),
                    full_digest=(
                        state_digest_v2(self._runtime.state)
                        if full_checkpoint(index)
                        else ""
                    ),
                )
            )

        return result

    def recording(self) -> Recording:
        """
        Return the sealed recording of everything accepted so far.

        Its last command carries the full digest whatever its index, taken of
        the position the game is in now — which is the position after that
        command, since a refused command changes nothing. What the recorder
        keeps is left as it was, so sealing twice gives the same recording.
        """
        commands = list(self._commands)

        if commands and not commands[-1].full_digest:
            commands[-1] = replace(
                commands[-1], full_digest=state_digest_v2(self._runtime.state)
            )

        model = self._runtime.state.rng_model

        return Recording(
            seed=self._runtime.state.seed,
            commands=tuple(commands),
            format_version=(
                KEYED_REPLAY_FORMAT if model == KEYED_MODEL else REPLAY_FORMAT_VERSION
            ),
            content_version=self._content_version,
            rng_model=model,
        ).sealed()
