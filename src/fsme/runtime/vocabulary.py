# src/fsme/runtime/vocabulary.py

"""
What this engine actually implements.

The content pipeline validates card meaning against a list of names. That list
has to come from the engine rather than from a document, or the two drift and
content passes validation for effects nobody wrote.
"""

from __future__ import annotations

from fsme.content import Vocabulary
from fsme.effects import EffectRegistry, builtin_registry
from fsme.events import EventType

from .condition_evaluator import ConditionEvaluator
from .interpreter import CONTROL_NAMES
from .target_resolver import TargetResolver

BOOLEAN_CONDITIONS = frozenset({"and", "or", "not"})


def engine_vocabulary(effects: EffectRegistry | None = None) -> Vocabulary:
    """
    Read the vocabulary out of the live engine.
    """
    registry = effects if effects is not None else builtin_registry()

    return Vocabulary(
        effects=frozenset(registry.names()) | CONTROL_NAMES,
        triggers=frozenset(str(event_type) for event_type in EventType),
        conditions=frozenset(ConditionEvaluator().names()) | BOOLEAN_CONDITIONS,
        targets=frozenset(TargetResolver().names()),
    )
