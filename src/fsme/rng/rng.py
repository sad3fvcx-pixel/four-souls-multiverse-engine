"""
Deterministic random number generator used by the engine.
"""

from __future__ import annotations

import random
from collections.abc import MutableSequence, Sequence
from typing import Any


class RNG:
    """Deterministic random number generator."""

    def __init__(self, seed: int) -> None:
        self._seed = seed
        self._random = random.Random(seed)

    @property
    def seed(self) -> int:
        """Return the initial seed."""
        return self._seed

    def randint(self, a: int, b: int) -> int:
        """Return a random integer N such that a <= N <= b."""
        return self._random.randint(a, b)

    def random(self) -> float:
        """Return the next random float in the range [0.0, 1.0)."""
        return self._random.random()

    def choice[T](self, sequence: Sequence[T]) -> T:
        """Return a random element from a non-empty sequence."""
        return self._random.choice(sequence)

    def shuffle(self, sequence: MutableSequence[Any]) -> None:
        """Shuffle a mutable sequence in place."""
        self._random.shuffle(sequence)

    def get_state(self) -> tuple[Any, ...]:
        """Return the internal RNG state."""
        return self._random.getstate()

    def set_state(self, state: tuple[Any, ...]) -> None:
        """Restore the internal RNG state."""
        self._random.setstate(state)
