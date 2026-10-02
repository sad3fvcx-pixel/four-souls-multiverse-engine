"""
The engine's vocabulary is built once and shared.

Building it registers every effect again, and the desk asked for it about
eighteen times for every card it wrote — nearly all the time a whole-corpus
round trip took. So the vocabulary of the engine as it ships is kept after the
first time. That is only safe if nothing in it can be changed, which is what
most of this file holds to; and a registry somebody passes in is still read
afresh, because they may register more.
"""

from __future__ import annotations

import dataclasses
import enum
from types import MappingProxyType
from typing import Any

from fsme.effects import builtin_registry
from fsme.rules.restrictions import ACTION_WORDS
from fsme.rules.statics import SCOPE_WORDS
from fsme.runtime.runtime import ABILITY_SCOPE_WORDS, ZONE_WORDS
from fsme.runtime.vocabulary import engine_vocabulary
from fsme.state.modifiers import STAT_WORDS

INVENTED = "an_effect_only_this_test_registers"


def _with_one_more_effect() -> Any:
    registry = builtin_registry()

    def handler(ctx: Any, targets: Any, amount: int = 1) -> None:
        return None

    registry.register(INVENTED, handler)

    return registry


def test_the_engine_s_vocabulary_is_built_once() -> None:
    assert engine_vocabulary() is engine_vocabulary()


def test_a_registry_passed_in_is_read_as_it_is() -> None:
    """
    Not the shared one: whoever holds a registry may have registered more.
    """
    registry = _with_one_more_effect()
    theirs = engine_vocabulary(registry)

    assert INVENTED in theirs.effects
    assert INVENTED in theirs.shapes
    assert theirs is not engine_vocabulary()
    assert engine_vocabulary(registry) is not theirs


def test_reading_a_registry_leaves_the_shared_vocabulary_alone() -> None:
    before = engine_vocabulary()

    engine_vocabulary(_with_one_more_effect())

    after = engine_vocabulary()

    assert after is before
    assert INVENTED not in after.effects
    assert INVENTED not in after.shapes


def test_a_registry_like_the_engine_s_reads_the_same() -> None:
    """The two paths build the same thing; only one of them keeps it."""
    assert engine_vocabulary(builtin_registry()) == engine_vocabulary()


# ----------------------------------------------------------------------
# Nothing in it can be changed
# ----------------------------------------------------------------------


def _mutable_parts(value: Any, path: str, seen: set[int]) -> list[str]:
    """
    Every place under ``value`` that something could change.

    Read off what is actually there rather than off the annotations: a field
    typed ``Mapping`` will hold a plain ``dict`` as happily as a read-only one.
    """
    if value is None or isinstance(value, (str, int, float, bytes, enum.Enum)):
        return []

    if id(value) in seen:
        return []

    seen.add(id(value))

    if isinstance(value, (frozenset, tuple)):
        return [
            part
            for index, item in enumerate(value)
            for part in _mutable_parts(item, f"{path}[{index}]", seen)
        ]

    if isinstance(value, MappingProxyType):
        return [
            part
            for key, item in value.items()
            for part in (
                _mutable_parts(key, f"{path} key {key!r}", seen)
                + _mutable_parts(item, f"{path}[{key!r}]", seen)
            )
        ]

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        own = (
            []
            if type(value).__dataclass_params__.frozen  # type: ignore[attr-defined]
            else [f"{path}: {type(value).__name__} is not frozen"]
        )

        return own + [
            part
            for field in dataclasses.fields(value)
            for part in _mutable_parts(
                getattr(value, field.name), f"{path}.{field.name}", seen
            )
        ]

    return [f"{path}: {type(value).__name__}"]


def test_nothing_in_the_shared_vocabulary_can_be_changed() -> None:
    assert _mutable_parts(engine_vocabulary(), "vocabulary", set()) == []


def test_what_the_words_mean_is_read_only_and_reads_as_before() -> None:
    """
    The five glossaries a static's and an ability's fields are explained by
    are the engine's own tables, handed over as views rather than as the
    tables themselves: the same words, and no way to write through them.
    """
    nodes = engine_vocabulary().node_shapes
    glossaries = {
        ("ability", "scope"): ABILITY_SCOPE_WORDS,
        ("ability", "zone"): ZONE_WORDS,
        ("static", "scope"): SCOPE_WORDS,
        ("static", "forbids"): ACTION_WORDS,
        ("static", "stat"): STAT_WORDS,
    }

    for (node, field), table in glossaries.items():
        shown = nodes[node].params[field].values_mean

        assert isinstance(shown, MappingProxyType), (node, field)
        assert dict(shown) == dict(table), (node, field)
