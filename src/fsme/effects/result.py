# src/fsme/effects/result.py

"""
Effect execution result for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class EffectResult:
    """
    Result of executing an effect.
    """

    success: bool = True

    resolved: bool = True

    cancelled: bool = False

    message: str = ""

    emitted_events: list[str] = field(default_factory=list)

    generated_effects: list[str] = field(default_factory=list)

    @classmethod
    def ok(cls, message: str = "") -> "EffectResult":
        return cls(
            success=True,
            resolved=True,
            cancelled=False,
            message=message,
        )

    @classmethod
    def cancelled_result(cls, message: str = "") -> "EffectResult":
        return cls(
            success=True,
            resolved=False,
            cancelled=True,
            message=message,
        )

    @classmethod
    def failed(cls, message: str = "") -> "EffectResult":
        return cls(
            success=False,
            resolved=False,
            cancelled=False,
            message=message,
        )