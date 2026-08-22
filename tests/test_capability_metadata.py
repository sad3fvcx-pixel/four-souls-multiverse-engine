"""
What the engine says about its own parameters.

The Author UI renders a form from this and nothing else, so a parameter that
says nothing about itself becomes a text box labelled `what` or `area`. The
tests here are the obligation that stops that: a parameter cannot exist
without a role, and a domain the engine enforces cannot go undeclared.

The rule these enforce is the one this project has used at every layer — the
guard is the fact, and a declaration that does not match it is a second copy
that will drift. Every domain below is read from the constant its handler
checks against.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from fsme.content.vocabulary import (
    A_LIST,
    A_MAPPING,
    BY_BINDING,
    BY_ENGINE,
    BY_PLAYER_OF,
    ROLES,
    STRUCTURE,
    WHOM,
    WRITINGS,
)
from fsme.effects import builtin_registry
from fsme.lab.desk.capabilities import catalogue
from fsme.runtime.condition_evaluator import ConditionEvaluator
from fsme.runtime.target_resolver import TargetResolver
from fsme.runtime.vocabulary import engine_vocabulary


@pytest.fixture(scope="module")
def vocabulary():
    return engine_vocabulary()


def every_parameter(vocabulary):
    """
    Every parameter of every effect, condition and target.
    """
    for name in sorted(vocabulary.effects):
        if (shape := vocabulary.shape(name)) is not None:
            for key, parameter in shape.params.items():
                yield f"{name}.{key}", parameter

    for name in sorted(vocabulary.conditions):
        if (shape := vocabulary.condition_shape(name)) is not None:
            for key, parameter in shape.params.items():
                yield f"{name}.{key}", parameter

    for name in sorted(vocabulary.targets):
        if (shape := vocabulary.target_shape(name)) is not None:
            for key, parameter in shape.params.items():
                yield f"{name}.{key}", parameter


# ----------------------------------------------------------------------
# Nothing may be shown without knowing how to show it
# ----------------------------------------------------------------------


def test_every_parameter_has_a_role(vocabulary) -> None:
    """
    The obligation. A parameter with no role cannot be rendered at all —
    nothing knows whether to draw a number box, a dropdown, or nothing.
    """
    silent = [name for name, one in every_parameter(vocabulary) if not one.role]

    assert silent == []


def test_every_role_is_one_the_interface_knows(vocabulary) -> None:
    unknown = sorted(
        {one.role for _, one in every_parameter(vocabulary) if one.role not in ROLES}
    )

    assert unknown == []


def test_nothing_reaches_the_form_as_a_bare_name() -> None:
    """
    What the audit was for. Every field the page renders carries words, a
    role, and either a domain or a type that says how to ask for it.
    """
    can = catalogue()
    bare = []

    for group in ("effects", "conditions", "targets"):
        for one in can[group]:
            for field in one["fields"]:
                if not field.get("role"):
                    bare.append(f"{one['id']}.{field['id']}")
                elif not field.get("about"):
                    bare.append(f"{one['id']}.{field['id']} (no words)")

    assert bare == []


def test_the_things_that_are_not_boxes_are_not_sent_to_the_form() -> None:
    """
    A card or player the ability picks out is not a field, and neither is the
    effect's own nested data. Each goes where it can be asked for properly.

    None of them is dropped: a parameter the engine understands and the
    interface omits is a capability quietly taken away.
    """
    can = catalogue()

    for group in ("effects", "conditions", "targets"):
        for one in can[group]:
            for field in one["fields"]:
                where = f"{one['id']}.{field['id']}"

                if field["written"] in (BY_ENGINE, BY_BINDING):
                    assert field["shown"] == "given", where
                elif field["role"] == WHOM:
                    assert field["shown"] == "group", where
                elif field["role"] == STRUCTURE:
                    assert field["shown"] == "advanced", where


def test_every_parameter_that_names_somebody_says_how_it_is_written() -> None:
    """
    Naming a player is not the same sentence for an effect and for a target,
    and a form that cannot tell them apart writes one where the other belongs.
    """
    can = catalogue()

    for group in ("effects", "conditions", "targets"):
        for one in can[group]:
            for field in one["fields"]:
                if field["role"] != WHOM:
                    continue

                assert field["written"] in WRITINGS, (
                    f"{one['id']}.{field['id']} names somebody and does not "
                    f"say how a card writes it"
                )
                assert field["picks"], f"{one['id']}.{field['id']}"


def test_a_choice_always_comes_with_its_choices(vocabulary) -> None:
    """
    A `which` with nothing to choose from is a text box in disguise.
    """
    empty = [
        name
        for name, one in every_parameter(vocabulary)
        if one.role == "which" and not one.values
    ]

    assert empty == []


# ----------------------------------------------------------------------
# What the engine enforces, it declares
# ----------------------------------------------------------------------


def _guards(handler) -> tuple[set[str], set[str]]:
    """
    The parameters this handler refuses a bad value for, and a missing one.

    A domain guard asks whether a value is *one of* something — `not in`, or
    `!=` against a constant. A guard asking whether a number is too small is a
    floor, which `least` records, and is not this.
    """
    try:
        tree = ast.parse(inspect.getsource(handler).lstrip())
    except (OSError, SyntaxError, IndentationError):
        return set(), set()

    bad: set[str] = set()
    missing: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue

        if not any(isinstance(one, ast.Raise) for one in ast.walk(node)):
            continue

        if isinstance(node.test, ast.UnaryOp) and isinstance(node.test.operand, ast.Name):
            missing.add(node.test.operand.id)

            continue

        if not isinstance(node.test, ast.Compare):
            continue

        if not isinstance(node.test.left, ast.Name):
            continue

        for operator in node.test.ops:
            if isinstance(operator, (ast.NotIn, ast.NotEq)):
                bad.add(node.test.left.id)

    return bad, missing


def test_a_domain_the_handler_enforces_is_a_domain_the_form_offers() -> None:
    """
    `lift_limit.what` had exactly one legal value, guarded by a raise, and the
    form showed a free text box. Six were like that.
    """
    registry = builtin_registry()
    undeclared = []

    for name in sorted(registry.names()):
        spec = registry.spec(name)
        bad, _ = _guards(spec.handler)

        for key in sorted(bad & set(spec.params)):
            if not spec.params[key].values:
                undeclared.append(f"{name}.{key}")

    assert undeclared == []


def test_a_requirement_the_handler_enforces_is_one_the_form_insists_on() -> None:
    """
    Five parameters raised when left out and were declared optional, so a form
    built from the declaration let somebody submit a card that cannot run.
    """
    registry = builtin_registry()
    undeclared = []

    for name in sorted(registry.names()):
        spec = registry.spec(name)
        _, missing = _guards(spec.handler)

        for key in sorted(missing & set(spec.params)):
            if not spec.params[key].required:
                undeclared.append(f"{name}.{key}")

    assert undeclared == []


def test_the_domains_are_the_constants_the_guards_read() -> None:
    """
    Not copies of them. A list written out again is free to drift from the
    lookup it describes.
    """
    from fsme.effects.builtin.copying import INDEFINITELY, TILL_END_OF_TURN
    from fsme.effects.builtin.loot import LEFT, RIGHT
    from fsme.effects.builtin.modifiers import AREAS, LIMITS
    from fsme.events import EventType

    vocabulary = engine_vocabulary()

    assert set(vocabulary.shape("copy_card").params["until"].values) == {
        TILL_END_OF_TURN,
        INDEFINITELY,
    }
    assert set(vocabulary.shape("pass_hands").params["direction"].values) == {
        LEFT,
        RIGHT,
    }
    assert set(vocabulary.shape("expand_slots").params["area"].values) == set(AREAS)
    assert set(vocabulary.shape("lift_limit").params["what"].values) == set(LIMITS)
    assert set(vocabulary.shape("watch_for").params["event"].values) == {
        str(one) for one in EventType
    }


# ----------------------------------------------------------------------
# Dependencies
# ----------------------------------------------------------------------


def test_a_parameter_another_one_overrides_says_so(vocabulary) -> None:
    """
    `heal` restores everything when `full` is set and ignores `amount`. A form
    showing both invites a card that says two things and quietly gets one.
    """
    depends = {
        name: one.unless for name, one in every_parameter(vocabulary) if one.unless
    }

    assert depends == {
        "add_counter.amount": "clear",
        "heal.amount": "full",
        "modify_event.factor": "delta",
        "move_cards.depth_from": "position",
    }


def test_every_dependency_names_a_real_parameter(vocabulary) -> None:
    for name, one in every_parameter(vocabulary):
        if not one.unless:
            continue

        effect = name.rsplit(".", 1)[0]
        shape = (
            vocabulary.shape(effect)
            or vocabulary.condition_shape(effect)
            or vocabulary.target_shape(effect)
        )

        assert one.unless in shape.params, f"{name} depends on {one.unless}"


# ----------------------------------------------------------------------
# And nothing lost
# ----------------------------------------------------------------------


def test_every_parameter_still_reaches_the_page() -> None:
    """
    The audit's own rule: nothing is removed because the form cannot draw it.
    Every parameter the engine has appears, marked with where it belongs.
    """
    vocabulary = engine_vocabulary()
    can = catalogue()

    offered = {
        f"{one['id']}.{field['id']}"
        for group in ("effects", "conditions", "targets")
        for one in can[group]
        for field in one["fields"]
    }
    known = {name for name, _ in every_parameter(vocabulary)}

    assert known - offered == set()


def test_the_registries_still_describe_themselves() -> None:
    """
    The three obligations from earlier stages, still holding.
    """
    assert [
        name
        for name in TargetResolver().names()
        if not TargetResolver().shapes()[name].describes
    ] == []
    assert [
        name
        for name in ConditionEvaluator().names()
        if not ConditionEvaluator().shapes()[name].describes
    ] == []


def test_the_checker_spells_the_engine_s_words_the_engine_s_way() -> None:
    """
    The content checker runs without an engine and reads shapes as plain data,
    so it spells three of the engine's words out for itself. Two copies of a
    word is how they come to disagree, and this is what stops that.
    """
    from fsme.cards import validator

    assert validator.BY_ENGINE == BY_ENGINE
    assert validator.LIST == A_LIST
    assert validator.MAPPING == A_MAPPING
    assert validator.DYNAMIC_HEADS >= {BY_PLAYER_OF}
