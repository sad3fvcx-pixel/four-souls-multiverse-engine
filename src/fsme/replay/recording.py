# src/fsme/replay/recording.py

"""
Replay files.

A replay is not a video. It is a seed and a list of commands, from which the
engine reproduces the game by running the very same pipeline it ran the first
time. Nothing about how the game looked is stored, and nothing about how it
turned out either — only what the players did.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from fsme import __version__
from fsme.commands import Command, CommandType

from .errors import ReplayFormatError, ReplayIntegrityError

REPLAY_FORMAT_VERSION = "2"
"""
The format this build writes.

Two, because a command may carry a full digest as well
(``RecordedCommand.full_digest``), and a build that ignored it would call a
playback faithful that the recording says came out differently.
"""

READABLE_REPLAY_FORMATS = (REPLAY_FORMAT_VERSION, "1")
"""
The formats this build plays back.

A recording in format 1 holds no full digests, and is checked the way it always
was: by the cheap digest, after every command.
"""

_EMPTY: Mapping[str, Any] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class RecordedCommand:
    """
    One command as it was submitted, with the position it produced.
    """

    type: CommandType
    player: int

    payload: Mapping[str, Any] = field(default_factory=lambda: _EMPTY)

    digest: str = ""
    """
    Fingerprint of the game right after this command, when it was recorded.

    Replay compares against it to catch divergence at the command that caused
    it rather than at the end of the game.
    """

    full_digest: str = ""
    """
    The full fingerprint of the game right after this command, when it is a
    full check: every eighth command and the last. Empty everywhere else.
    """

    def to_command(self) -> Command:
        """
        Rebuild a submittable command.
        """
        return Command(
            type=self.type,
            player=self.player,
            payload=dict(self.payload),
        )

    def to_dict(self) -> dict[str, Any]:
        written: dict[str, Any] = {
            "type": str(self.type),
            "player": self.player,
            "payload": dict(self.payload),
            "digest": self.digest,
        }

        # Only when there is one, so that a command without one writes and
        # checksums exactly as it did in format 1.
        if self.full_digest:
            written["full_digest"] = self.full_digest

        return written

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RecordedCommand:
        try:
            return cls(
                type=CommandType(data["type"]),
                player=int(data["player"]),
                payload=MappingProxyType(dict(data.get("payload", {}))),
                digest=str(data.get("digest", "")),
                full_digest=str(data.get("full_digest", "")),
            )
        except (KeyError, ValueError) as error:
            raise ReplayFormatError(f"invalid recorded command: {error}") from error


@dataclass(frozen=True, slots=True)
class Recording:
    """
    Everything needed to reproduce a game.
    """

    seed: int

    commands: tuple[RecordedCommand, ...] = ()

    format_version: str = REPLAY_FORMAT_VERSION
    engine_version: str = __version__
    content_version: str = ""

    checksum: str = ""

    def __len__(self) -> int:
        return len(self.commands)

    def compute_checksum(self) -> str:
        """
        Return the integrity value for this recording's contents.
        """
        payload = json.dumps(
            {
                "seed": self.seed,
                "format_version": self.format_version,
                "content_version": self.content_version,
                "commands": [command.to_dict() for command in self.commands],
            },
            sort_keys=True,
            separators=(",", ":"),
        )

        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]

    def sealed(self) -> Recording:
        """
        Return this recording with its checksum filled in.
        """
        return Recording(
            seed=self.seed,
            commands=self.commands,
            format_version=self.format_version,
            engine_version=self.engine_version,
            content_version=self.content_version,
            checksum=self.compute_checksum(),
        )

    def verify(self) -> None:
        """
        Check the recording against its own integrity value.

        Corrupted data has to be caught before playback, not discovered as a
        confusing divergence halfway through a game.
        """
        if not self.checksum:
            return

        if self.checksum != self.compute_checksum():
            raise ReplayIntegrityError(
                "replay checksum does not match its contents"
            )

    def check_compatibility(self) -> None:
        """
        Refuse a recording this engine cannot play back.
        """
        if self.format_version not in READABLE_REPLAY_FORMATS:
            readable = " and ".join(f"'{one}'" for one in READABLE_REPLAY_FORMATS)

            raise ReplayFormatError(
                f"replay format '{self.format_version}' is not supported; "
                f"this engine reads format {readable}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": self.format_version,
            "engine_version": self.engine_version,
            "content_version": self.content_version,
            "seed": self.seed,
            "checksum": self.checksum,
            "commands": [command.to_dict() for command in self.commands],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Recording:
        if not isinstance(data, Mapping):
            raise ReplayFormatError("a replay must be an object")

        try:
            return cls(
                seed=int(data["seed"]),
                commands=tuple(
                    RecordedCommand.from_dict(entry)
                    for entry in data.get("commands", ())
                ),
                format_version=str(data.get("format_version", "")),
                engine_version=str(data.get("engine_version", "")),
                content_version=str(data.get("content_version", "")),
                checksum=str(data.get("checksum", "")),
            )
        except KeyError as error:
            raise ReplayFormatError(f"replay is missing {error}") from error

    def save(self, path: Path | str) -> Path:
        """
        Write the recording to a JSON file.
        """
        file_path = Path(path)
        file_path.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

        return file_path

    @classmethod
    def load(cls, path: Path | str) -> Recording:
        """
        Read a recording, checking its integrity and version first.
        """
        file_path = Path(path)

        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ReplayFormatError(f"{file_path}: invalid JSON: {error}") from error

        recording = cls.from_dict(data)

        recording.check_compatibility()
        recording.verify()

        return recording
