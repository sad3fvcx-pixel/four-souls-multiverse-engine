# src/fsme/effects/effect.py

"""
Effect operations for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

_EMPTY: Mapping[str, Any] = MappingProxyType({})


@dataclass(frozen=True, slots=True)
class EffectOp:
    """
    One atomic operation produced by the interpreter.

    An EffectOp is the executable unit of the Effect DSL. It is immutable:
    the interpreter builds it once from a card definition and the executor
    only reads it.
    """

    name: str

    params: Mapping[str, Any] = field(default_factory=lambda: _EMPTY)

    target: Any | None = None
    """
    What this operation applies to.

    Usually a name — of a group the ability bound, or of a target in the engine
    vocabulary. It may also be a whole target specification, which is how a card
    asks its question at the moment the effect runs rather than before the
    ability starts: "destroy an item, and if you do, steal one" must not ask
    which item to steal until the first item is destroyed.
    """

    def param(self, key: str, default: Any = None) -> Any:
        """
        Read a parameter value.
        """
        return self.params.get(key, default)

    def __str__(self) -> str:
        if self.target is None:
            return self.name

        return f"{self.name}->{self.target}"
