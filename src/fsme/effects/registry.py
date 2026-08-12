# src/fsme/effects/registry.py

"""
Registry of built-in effects for Four Souls Multiverse Engine.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from .context import EffectContext
from .errors import EffectRegistrationError, UnknownEffectError

EffectHandler = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class EffectSpec:
    """
    Immutable description of one registered effect.
    """

    name: str
    handler: EffectHandler

    uses_stack: bool = False
    needs_target: bool = False

    primary: str | None = None
    """
    Parameter filled by the DSL shorthand form.

    ``{"gain_coins": 3}`` means ``amount=3`` while ``{"draw_loot": 2}`` means
    ``count=2``; the effect declares which, so the interpreter never guesses.
    """

    stores: str | None = None
    """
    Ability variable that receives this effect's return value.

    ``roll_dice`` stores ``dice``, which is what lets a later condition read
    ``dice_equals`` without the executor special-casing dice.
    """

    description: str = ""


class EffectRegistry:
    """
    Name to implementation mapping for every effect the engine knows.

    Registration is permanent: DEVELOPMENT_GUIDELINES.md requires definitions
    to be immutable once registered, so re-registering a name is an error
    rather than a silent override. A card that needs new behaviour extends the
    registry with a new effect; it never replaces an existing one.
    """

    def __init__(self) -> None:
        self._specs: dict[str, EffectSpec] = {}

    def __contains__(self, name: object) -> bool:
        return name in self._specs

    def __len__(self) -> int:
        return len(self._specs)

    def register(
        self,
        name: str,
        handler: EffectHandler,
        *,
        uses_stack: bool = False,
        needs_target: bool = False,
        primary: str | None = None,
        stores: str | None = None,
        description: str = "",
    ) -> EffectSpec:
        """
        Register an effect implementation.
        """
        if not name:
            raise EffectRegistrationError("effect name must not be empty")

        if name in self._specs:
            raise EffectRegistrationError(
                f"effect '{name}' is already registered"
            )

        spec = EffectSpec(
            name=name,
            handler=handler,
            uses_stack=uses_stack,
            needs_target=needs_target,
            primary=primary,
            stores=stores,
            description=description,
        )

        self._specs[name] = spec

        return spec

    def effect(
        self,
        name: str,
        *,
        uses_stack: bool = False,
        needs_target: bool = False,
        primary: str | None = None,
        stores: str | None = None,
        description: str = "",
    ) -> Callable[[EffectHandler], EffectHandler]:
        """
        Decorator form of :meth:`register`.
        """

        def decorate(handler: EffectHandler) -> EffectHandler:
            self.register(
                name,
                handler,
                uses_stack=uses_stack,
                needs_target=needs_target,
                primary=primary,
                stores=stores,
                description=description,
            )
            return handler

        return decorate

    def spec(self, name: str) -> EffectSpec:
        """
        Return the specification of a registered effect.
        """
        try:
            return self._specs[name]
        except KeyError:
            raise UnknownEffectError(f"unknown effect '{name}'") from None

    def execute(
        self,
        name: str,
        context: EffectContext,
        targets: Sequence[Any],
        **params: Any,
    ) -> Any:
        """
        Run a registered effect.
        """
        return self.spec(name).handler(context, targets, **params)

    def names(self) -> frozenset[str]:
        """
        Return every registered effect name.
        """
        return frozenset(self._specs)


def builtin_registry() -> EffectRegistry:
    """
    Build a registry populated with the engine's built-in effects.
    """
    from .builtin import register_builtin_effects

    registry = EffectRegistry()
    register_builtin_effects(registry)

    return registry
