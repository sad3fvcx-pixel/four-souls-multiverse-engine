# src/fsme/runtime/vocabulary.py

"""
What this engine actually implements.

The content pipeline validates card meaning against a list of names. That list
has to come from the engine rather than from a document, or the two drift and
content passes validation for effects nobody wrote.
"""

from __future__ import annotations

from types import MappingProxyType

from fsme.content import Vocabulary
from fsme.content.vocabulary import UNCHECKED, EffectShape, ParamShape
from fsme.effects import EffectRegistry, builtin_registry
from fsme.effects.registry import EffectSpec, ParamKind
from fsme.events import EventType

from .condition_evaluator import ConditionEvaluator
from .interpreter import CONTROL_NAMES
from .target_resolver import TargetResolver

BOOLEAN_CONDITIONS = frozenset({"and", "or", "not"})


def engine_vocabulary(effects: EffectRegistry | None = None) -> Vocabulary:
    """
    Read the vocabulary out of the live engine.

    This is the one function that knows both sides. What goes in is a registry
    full of callables; what comes out is names and plain descriptions, and the
    pipeline that receives it never learns there was an engine to ask.
    """
    registry = effects if effects is not None else builtin_registry()

    return Vocabulary(
        effects=frozenset(registry.names()) | CONTROL_NAMES,
        triggers=frozenset(str(event_type) for event_type in EventType),
        conditions=frozenset(ConditionEvaluator().names()) | BOOLEAN_CONDITIONS,
        targets=frozenset(TargetResolver().names()),
        shapes=MappingProxyType(
            {name: _shape_of(registry.spec(name)) for name in registry.names()}
        ),
    )


def _shape_of(spec: EffectSpec) -> EffectShape:
    """
    An effect, flattened to what a card file may say about it.

    The handler is left behind here deliberately. A description that carried it
    would put a live function into the content pipeline, and the pipeline's
    whole value is that it can check a card without one.
    """
    return EffectShape(
        name=spec.name,
        params=MappingProxyType(
            {
                name: ParamShape(
                    name=param.name,
                    kind=(
                        UNCHECKED
                        if param.kind is ParamKind.OPEN
                        else str(param.kind)
                    ),
                    required=param.required,
                    nullable=param.nullable,
                    values=param.values,
                    least=param.least,
                )
                for name, param in spec.params.items()
            }
        ),
        primary=spec.primary,
        open_ended=spec.open_ended,
        literal=spec.literal,
    )
