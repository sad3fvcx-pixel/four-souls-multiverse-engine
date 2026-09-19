# src/fsme/commands/result.py

"""
Command results for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fsme.events import Event

from .command import Command


@dataclass(frozen=True, slots=True)
class CommandResult:
    """
    The outcome of submitting a command.

    Every API operation returns either success or a structured error, and a
    rejected command leaves GameState untouched, so a caller can retry or
    report without first having to repair anything.
    """

    command: Command

    accepted: bool

    reason: str = ""

    events: tuple[Event, ...] = field(default_factory=tuple)

    @classmethod
    def accept(
        cls,
        command: Command,
        events: tuple[Event, ...] = (),
    ) -> CommandResult:
        return cls(command=command, accepted=True, events=events)

    @classmethod
    def reject(cls, command: Command, reason: str) -> CommandResult:
        return cls(command=command, accepted=False, reason=reason)

    @property
    def rejected(self) -> bool:
        return not self.accepted

    def __bool__(self) -> bool:
        return self.accepted

    def __str__(self) -> str:
        if self.accepted:
            return f"{self.command} accepted"

        return f"{self.command} rejected: {self.reason}"
