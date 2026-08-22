# src/fsme/runtime/vocabulary.py

"""
What this engine actually implements.

The content pipeline validates card meaning against a list of names. That list
has to come from the engine rather than from a document, or the two drift and
content passes validation for effects nobody wrote.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields
from types import MappingProxyType

from fsme.cards.definition import Ability, Static
from fsme.content import Vocabulary
from fsme.content.vocabulary import (
    STRUCTURE,
    UNCHECKED,
    EffectShape,
    NodeShape,
    ParamShape,
)
from fsme.effects import EffectRegistry, builtin_registry
from fsme.effects.registry import EffectSpec, ParamKind
from fsme.events import EventType
from fsme.rules.statics import STATIC_SCOPES

from .condition_evaluator import ConditionEvaluator
from .interpreter import _MODIFIER_KEYS, CONTROL_KEYS, CONTROL_NAMES
from .runtime import ABILITY_SCOPES
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
    conditions = ConditionEvaluator()
    targets = TargetResolver()

    return Vocabulary(
        effects=frozenset(registry.names()) | CONTROL_NAMES,
        triggers=frozenset(str(event_type) for event_type in EventType),
        conditions=frozenset(conditions.names()) | BOOLEAN_CONDITIONS,
        targets=frozenset(targets.names()),
        shapes=MappingProxyType(
            {name: _shape_of(registry.spec(name)) for name in registry.names()}
        ),
        condition_shapes=conditions.shapes(),
        target_shapes=targets.shapes(),
        node_shapes=_node_shapes(),
    )


TEXT = "text"


def _node_shapes() -> Mapping[str, NodeShape]:
    """
    What an ability, a static and each control node may be written with.

    The two card structures are read off their own dataclasses: ``from_data``
    reads exactly the fields, so the fields are what a card may write, and
    adding one to the language widens this the moment it exists. The control
    nodes are read off the table beside the expanders that consume them.

    Only two keys carry a domain, and both are places a misspelling used to
    change what a card did rather than stop it: a scope the engine does not
    know falls through to the branch that means something else.
    """
    return MappingProxyType(
        {
            "ability": NodeShape(
                name="ability",
                params=MappingProxyType(
                    {
                        field.name: ParamShape(
                            field.name,
                            TEXT,
                            values=ABILITY_SCOPES if field.name == "scope" else (),
                        )
                        for field in fields(Ability)
                    }
                ),
            ),
            "static": NodeShape(
                name="static",
                params=MappingProxyType(
                    {
                        field.name: ParamShape(
                            field.name,
                            TEXT,
                            values=STATIC_SCOPES if field.name == "scope" else (),
                        )
                        for field in fields(Static)
                    }
                ),
            ),
            **{
                name: NodeShape(
                    name=name,
                    params=MappingProxyType(
                        {
                            key: ParamShape(key, TEXT)
                            for key in tuple(keys) + tuple(sorted(_MODIFIER_KEYS))
                        }
                    ),
                )
                for name, keys in CONTROL_KEYS.items()
            },
        }
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
                    describes=param.asks,
                    role=param.role or (STRUCTURE if name in spec.literal else ""),
                    unless=param.unless,
                )
                for name, param in spec.params.items()
            }
        ),
        primary=spec.primary,
        open_ended=spec.open_ended,
        literal=spec.literal,
    )
