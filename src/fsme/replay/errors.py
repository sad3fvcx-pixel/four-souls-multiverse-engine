"""
Exceptions for the replay subsystem.
"""

from __future__ import annotations

from fsme.util.errors import ReplayError


class ReplayFormatError(ReplayError):
    """
    Raised when a replay file cannot be read or its version is unsupported.
    """


class ReplayIntegrityError(ReplayError):
    """
    Raised when a replay's contents do not match its checksum.
    """


class ReplayDivergence(ReplayError):
    """
    Raised when playback produces a different game than the one recorded.

    Determinism is a mandatory property of the engine, so a divergence is an
    engine defect rather than a problem with the replay file. The command that
    diverged is named, because that is where the defect is.
    """


class ReplayRejectedCommand(ReplayError):
    """
    Raised when a recorded command is refused during playback.

    Replay never bypasses validation, so a command that was legal when it was
    recorded and is illegal now means the two games have already diverged.
    """


__all__ = [
    "ReplayDivergence",
    "ReplayError",
    "ReplayFormatError",
    "ReplayIntegrityError",
    "ReplayRejectedCommand",
]
