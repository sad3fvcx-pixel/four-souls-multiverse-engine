# src/fsme/runtime/ability_context.py

"""
Per-ability execution context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fsme.effects import EffectResult
from fsme.events import Event


@dataclass(slots=True)
class AbilityContext:
    """
    Local scope of a single ability while it resolves.

    Each ability gets its own context and contexts never share variables, so a
    card that stores a dice result cannot be disturbed by another card
    resolving in the middle of it.
    """

    source: Any | None = None
    ability: Any | None = None

    controller: int | None = None
    owner: int | None = None
    initiator: int | None = None

    event: Event | None = None

    variables: dict[str, Any] = field(default_factory=dict)
    targets: dict[str, list[Any]] = field(default_factory=dict)
    results: list[EffectResult] = field(default_factory=list)

    stopped: bool = False

    def store(self, name: str, value: Any) -> None:
        """
        Set a local variable.
        """
        self.variables[name] = value

    def get(self, name: str, default: Any = None) -> Any:
        """
        Read a local variable.
        """
        return self.variables.get(name, default)

    def bind(self, name: str, targets: list[Any]) -> None:
        """
        Store a resolved target group under a name.
        """
        self.targets[name] = targets

    def record(self, result: EffectResult) -> EffectResult:
        """
        Append an effect result to the ability history.
        """
        self.results.append(result)

        return result

    def stop(self) -> None:
        """
        Mark the ability as finished early.
        """
        self.stopped = True

    @property
    def last_result(self) -> EffectResult | None:
        return self.results[-1] if self.results else None

    @property
    def last_value(self) -> Any:
        result = self.last_result

        return result.value if result is not None else None

    @property
    def last_targets(self) -> list[Any]:
        result = self.last_result

        return list(result.targets) if result is not None else []
