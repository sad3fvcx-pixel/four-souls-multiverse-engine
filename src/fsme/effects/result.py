# src/fsme/effects/result.py

"""
Effect execution result for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EffectResult:
    """
    Result of executing a single effect operation.

    ``value`` carries whatever the effect produced (a dice roll, a drawn card,
    an amount actually applied) so that later effects in the same ability can
    reference it through the ``previous_result`` target.
    """

    effect: str = ""

    success: bool = True
    resolved: bool = True
    cancelled: bool = False

    value: Any = None
    targets: list[Any] = field(default_factory=list)

    message: str = ""

    @classmethod
    def ok(
        cls,
        effect: str = "",
        value: Any = None,
        targets: list[Any] | None = None,
        message: str = "",
    ) -> EffectResult:
        return cls(
            effect=effect,
            success=True,
            resolved=True,
            cancelled=False,
            value=value,
            targets=list(targets or ()),
            message=message,
        )

    @classmethod
    def cancelled_result(cls, effect: str = "", message: str = "") -> EffectResult:
        return cls(
            effect=effect,
            success=True,
            resolved=False,
            cancelled=True,
            message=message,
        )

    @classmethod
    def failed(cls, effect: str = "", message: str = "") -> EffectResult:
        return cls(
            effect=effect,
            success=False,
            resolved=False,
            cancelled=False,
            message=message,
        )
