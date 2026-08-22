# src/fsme/cards/validator.py

"""
Card content validation for Four Souls Multiverse Engine.

Validation happens before gameplay: ENGINE_INVARIANTS.md requires that invalid
content never reaches GameState, so the loader rejects a whole file rather than
letting a half-valid card into a game.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

from .references import validate_references
from .suggest import did_you_mean
from .types import CardType

REQUIRED_FIELDS = ("id", "name", "type", "expansion", "abilities")

_OPTIONAL_INT_FIELDS = ("health", "attack", "roll", "cost", "souls")


def validate_card(
    data: Any,
    *,
    known_effects: Collection[str] | None = None,
    known_triggers: Collection[str] | None = None,
    known_conditions: Collection[str] | None = None,
    known_targets: Collection[str] | None = None,
    shapes: Mapping[str, Any] | None = None,
    condition_shapes: Mapping[str, Any] | None = None,
    target_shapes: Mapping[str, Any] | None = None,
    node_shapes: Mapping[str, Any] | None = None,
) -> list[str]:
    """
    Return every problem found in one raw card.

    An empty list means the card is loadable. Effect and trigger vocabularies
    are passed in as plain names so that content validation stays independent
    of the effect implementations themselves.

    ``shapes`` says what each effect *takes*, in the same spirit and under the
    same rule: plain data, handed over by whoever owns a live engine, never
    imported from one. Without it the names are checked and the arguments are
    not — which is what a caller with no engine gets, and is exactly what
    happened to every card until this existed.
    """
    errors: list[str] = []

    if not isinstance(data, Mapping):
        return [f"card must be an object, got {type(data).__name__}"]

    card_id = data.get("id", "<no id>")

    for field_name in REQUIRED_FIELDS:
        if field_name not in data:
            errors.append(f"{card_id}: missing required field '{field_name}'")

    if "type" in data:
        try:
            CardType(data["type"])
        except ValueError:
            errors.append(f"{card_id}: unknown card type '{data['type']}'")

    for field_name in _OPTIONAL_INT_FIELDS:
        value = data.get(field_name)

        if value is not None and not isinstance(value, int):
            errors.append(
                f"{card_id}: field '{field_name}' must be an integer"
            )

    rewards = data.get("rewards")

    if rewards is not None:
        if not isinstance(rewards, Mapping):
            errors.append(f"{card_id}: 'rewards' must be an object")
        else:
            for key, value in rewards.items():
                if not isinstance(value, int):
                    errors.append(
                        f"{card_id}: reward '{key}' must be an integer"
                    )

    abilities = data.get("abilities", ())

    if not isinstance(abilities, (list, tuple)):
        errors.append(f"{card_id}: 'abilities' must be a list")
        return errors

    errors.extend(
        _validate_conditions(
            data,
            known=known_conditions,
            shapes=condition_shapes,
            card_id=str(card_id),
        )
    )

    errors.extend(
        _validate_targets(
            data,
            known=known_targets,
            shapes=target_shapes,
            card_id=str(card_id),
        )
    )

    errors.extend(
        validate_references(
            data,
            shapes=target_shapes,
            known_targets=known_targets,
            card_id=str(card_id),
        )
    )

    errors.extend(
        _validate_nodes(data, nodes=node_shapes, card_id=str(card_id))
    )

    for index, ability in enumerate(abilities):
        errors.extend(
            _validate_ability(
                ability,
                card_id=str(card_id),
                index=index,
                known_effects=known_effects,
                known_triggers=known_triggers,
                known_targets=known_targets,
                shapes=shapes,
            )
        )

    return errors


def _validate_ability(
    ability: Any,
    *,
    card_id: str,
    index: int,
    known_effects: Collection[str] | None,
    known_triggers: Collection[str] | None,
    known_targets: Collection[str] | None = None,
    shapes: Mapping[str, Any] | None = None,
) -> list[str]:
    location = f"{card_id}: ability {index}"

    if not isinstance(ability, Mapping):
        return [f"{location}: must be an object"]

    errors: list[str] = []

    trigger = ability.get("trigger")

    if not trigger:
        errors.append(f"{location}: missing 'trigger'")
    elif known_triggers is not None and trigger not in known_triggers:
        errors.append(
            f"{location}: unknown trigger '{trigger}'"
            f"{did_you_mean(str(trigger), known_triggers)}"
        )

    for key in ("targets", "effects"):
        value = ability.get(key, ())

        if not isinstance(value, (list, tuple)):
            errors.append(f"{location}: '{key}' must be a list")

    effects = ability.get("effects", ())

    if isinstance(effects, (list, tuple)):
        if not effects:
            errors.append(f"{location}: needs at least one effect")

        if known_effects is not None:
            for name in _effect_names(effects):
                if name not in known_effects and name not in _CONTROL_NAMES:
                    errors.append(
                        f"{location}: unknown effect '{name}'"
                        f"{did_you_mean(name, known_effects)}"
                    )

    if shapes and isinstance(effects, (list, tuple)):
        errors.extend(
            _validate_arguments(effects, shapes=shapes, location=location)
        )

    if known_targets is not None:
        declared = _declared_target_names(ability) | _effect_aliases(
            ability.get("effects", ())
        )

        for name in _target_names(ability):
            if name not in known_targets and name not in declared:
                errors.append(
                    f"{location}: unknown target '{name}'"
                    f"{did_you_mean(name, known_targets)}"
                )

    return errors


DYNAMIC_HEADS = frozenset(
    {"from", "count", "from_event", "last_result", "player_of"}
)
"""
The five ways a card names a number it cannot know when it is written.

``{"amount": {"from": "dice"}}`` is a card saying "as much as the roll". The
executor knows these five and hands anything else straight to the effect, so a
misspelled one — ``{"frmo": "dice"}`` — is not a rejected typo but a dictionary
arriving where a number was expected. That is the mistake this set exists to
catch.
"""

WRITTEN_BY_THE_ENGINE = frozenset({"effect", "target", "targets", "store"})
"""
Keys the interpreter takes out of a node before the effect ever sees it.

Exactly these four, and the list has to match `runtime.interpreter.normalise`
and `_operation`: anything else written beside an effect is handed to it as a
parameter, so anything else is the card's to get right.
"""

WHOLE = "a whole number"
TEXT = "text"
FLAG = "true or false"


def _validate_arguments(
    nodes: Any,
    *,
    shapes: Mapping[str, Any],
    location: str,
    path: str = "effects",
) -> list[str]:
    """
    Check what a card gives each effect against what that effect takes.

    Walks the same shape `_effect_names` does, and for the same reason keeps a
    path while it goes: an author with a mistake three branches deep needs to
    be told where it is, not merely that it exists.
    """
    errors: list[str] = []

    for position, node in enumerate(nodes):
        here = f"{path}[{position}]"

        if not isinstance(node, Mapping):
            continue

        name, params = _effect_call(node, shapes)

        if name is not None:
            errors.extend(
                _validate_call(name, params, shapes[name], location, here)
            )

        for branch in _BRANCH_KEYS:
            inside = node.get(branch)

            if isinstance(inside, (list, tuple)):
                errors.extend(
                    _validate_arguments(
                        inside, shapes=shapes, location=location,
                        path=f"{here}.{branch}",
                    )
                )

        for number, mode in enumerate(_modes(node)):
            inside = mode.get("effects", ())

            if isinstance(inside, (list, tuple)):
                errors.extend(
                    _validate_arguments(
                        inside, shapes=shapes, location=location,
                        path=f"{here}.modes[{number}].effects",
                    )
                )

    return errors


def _effect_call(
    node: Mapping[str, Any],
    shapes: Mapping[str, Any],
) -> tuple[str | None, dict[str, Any]]:
    """
    The effect this node calls and the parameters it passes, or nothing.

    Two written forms, both of which the interpreter accepts, so both of which
    have to be read the same way here::

        {"effect": "gain_coins", "amount": 3}
        {"gain_coins": 3}
        {"draw_loot": {"count": 2}}

    A node naming a control word, or an effect this vocabulary has never heard
    of, is somebody else's complaint — the name check has already made it.
    """
    if "effect" in node:
        name = str(node["effect"])

        if name not in shapes:
            return None, {}

        return name, {
            key: value
            for key, value in node.items()
            if key not in WRITTEN_BY_THE_ENGINE
        }

    named = [
        key
        for key in node
        if key not in _MODIFIER_KEYS and key not in _BRANCH_KEYS
    ]

    if len(named) != 1 or named[0] not in shapes:
        return None, {}

    name = named[0]
    value = node[name]

    if isinstance(value, Mapping):
        return name, {
            key: item
            for key, item in value.items()
            if key not in WRITTEN_BY_THE_ENGINE
        }

    primary = shapes[name].primary

    return (name, {primary: value}) if primary else (None, {})


def _validate_call(
    name: str,
    params: Mapping[str, Any],
    shape: Any,
    location: str,
    path: str,
) -> list[str]:
    """
    One effect call, against what that effect takes.
    """
    errors: list[str] = []

    for key, value in params.items():
        if key in shape.literal:
            # The effect's own structured data. What is *inside* it needs a
            # game and nothing here may judge that — but whether it is a
            # structure at all is a different question, and the effect answers
            # it at registration because its handler raises on anything else.
            errors.extend(
                _outer_shape(name, shape.params.get(key), value, location, path)
            )
            continue

        parameter = shape.params.get(key)

        if parameter is None:
            if not shape.open_ended:
                errors.append(
                    f"{location}: {path}.{key}: '{name}' takes no parameter "
                    f"called '{key}'"
                    f"{did_you_mean(key, list(shape.params))}"
                )

            continue

        errors.extend(_validate_value(name, parameter, value, location, path))

    for key, parameter in shape.params.items():
        if parameter.required and key not in params:
            errors.append(
                f"{location}: {path}: '{name}' needs '{key}' "
                f"({parameter.wants()}), and the card does not give it"
            )

    return errors


def _validate_value(
    name: str,
    parameter: Any,
    value: Any,
    location: str,
    path: str,
) -> list[str]:
    """
    One value, against the one parameter it was written for.
    """
    where = f"{location}: {path}.{parameter.name}"

    named = _naming(parameter, value, where, name)

    if named is not None:
        return named

    if value is None:
        if parameter.nullable:
            return []

        return [
            f"{where}: '{name}' takes {parameter.wants()} here, and the card "
            f"writes nothing; leave the key out instead"
        ]

    if isinstance(value, Mapping):
        head = DYNAMIC_HEADS & set(value)

        if not head:
            return [
                f"{where}: this asks for a value the ability works out while "
                f"it runs, and names it "
                f"{', '.join(repr(key) for key in sorted(value))}; the ways to "
                f"do that are {', '.join(sorted(DYNAMIC_HEADS))}"
            ]

        if not parameter.checkable or parameter.kind == WHOLE:
            return []

        return [
            f"{where}: '{name}' takes {parameter.wants()} here, and a value "
            f"worked out while the ability runs is always a whole number"
        ]

    if not parameter.checkable:
        return []

    written = _kind_written(value)

    if written != parameter.kind:
        return [
            f"{where}: '{name}' takes {parameter.wants()} here, "
            f"and the card gives {written} ({value!r})"
        ]

    if parameter.values and value not in parameter.values:
        return [
            f"{where}: '{name}' takes {parameter.wants()} here, "
            f"and the card gives {value!r}"
            f"{did_you_mean(str(value), [str(one) for one in parameter.values])}"
        ]

    if (
        parameter.least is not None
        and isinstance(value, int)
        and value < parameter.least
    ):
        return [
            f"{where}: '{name}' takes {parameter.wants()} here, "
            f"and the card gives {value!r}"
        ]

    return []


def _kind_written(value: Any) -> str:
    """
    What a card actually wrote, in the same words the parameters use.
    """
    if isinstance(value, bool):
        # Before int: in Python True is 1, and a card that writes true where a
        # count belongs has made a mistake worth naming rather than rounding.
        return FLAG

    if isinstance(value, int):
        return WHOLE

    if isinstance(value, str):
        return TEXT

    if isinstance(value, (list, tuple)):
        return "a list"

    return type(value).__name__


_BOOLEAN_NAMES = frozenset({"and", "or", "not"})


STATIC_STAT_BY_SCOPE = "the stats a static may change depend on what it reaches"


def _validate_nodes(
    card: Mapping[str, Any],
    *,
    nodes: Mapping[str, Any] | None,
    card_id: str,
) -> list[str]:
    """
    Check the parts of the DSL that have no name inside them to look up.

    An ability, a static and a control node *are* the structure, so what they
    accept is a closed set of keys — unlike the top of a card, where an
    unknown field is kept because a set may carry something this engine has
    not learned yet. Inside the DSL there is nothing to be forward compatible
    with: the interpreter reads these keys and hands nothing else on, so
    ``{"if": [...], "thne": [...]}`` is a branch that never runs, silently.
    """
    if not nodes:
        return []

    errors: list[str] = []
    monster = str(card.get("type", "")) == "monster"

    for index, ability in enumerate(card.get("abilities", ()) or ()):
        if isinstance(ability, Mapping):
            errors.extend(
                _one_node(ability, nodes.get("ability"), card_id, f"abilities[{index}]")
            )
            errors.extend(
                _control_nodes(
                    ability.get("effects", ()),
                    nodes,
                    card_id,
                    f"abilities[{index}].effects",
                )
            )

    for index, static in enumerate(card.get("statics", ()) or ()):
        if not isinstance(static, Mapping):
            continue

        where = f"statics[{index}]"

        errors.extend(_one_node(static, nodes.get("static"), card_id, where))
        errors.extend(_static_stat(static, monster, card_id, where))

    return errors


def _one_node(
    node: Mapping[str, Any],
    shape: Any,
    card_id: str,
    path: str,
) -> list[str]:
    """
    Check one node's keys, and the values of the ones with a domain.
    """
    if shape is None:
        return []

    errors: list[str] = []

    for key, value in node.items():
        parameter = shape.params.get(key)

        if parameter is None:
            article = "an" if shape.name[0] in "aeiou" else "a"

            errors.append(
                f"{card_id}: {path}: '{key}' is not part of "
                f"{article} {shape.name}{did_you_mean(str(key), shape.params)}"
            )

            continue

        if parameter.values and isinstance(value, str) and value not in parameter.values:
            errors.append(
                f"{card_id}: {path}.{key}: '{value}' is not one of "
                + " or ".join(f"'{one}'" for one in parameter.values)
                + did_you_mean(value, parameter.values)
            )

    return errors


def _control_nodes(
    effects: Any,
    nodes: Mapping[str, Any],
    card_id: str,
    path: str,
) -> list[str]:
    """
    Walk an ability's effects, checking every control node on the way down.
    """
    if not isinstance(effects, (list, tuple)):
        return []

    errors: list[str] = []

    for index, node in enumerate(effects):
        if not isinstance(node, Mapping):
            continue

        here = f"{path}[{index}]"
        head = next((key for key in node if key in nodes and key != "static"), "")

        if head and head != "ability":
            wrong = _one_node(node, nodes[head], card_id, here)

            errors.extend(wrong)

            # Only when the node is otherwise written correctly. `thne` is a
            # branch with nothing under `then`, and saying so as well as naming
            # the typo is two complaints about one mistake — which is how a
            # list of problems stops being read.
            if not wrong:
                errors.extend(_does_something(node, nodes[head], card_id, here))

        for key, value in node.items():
            if isinstance(value, (list, tuple)):
                errors.extend(_control_nodes(value, nodes, card_id, f"{here}.{key}"))
            elif isinstance(value, Mapping):
                errors.extend(
                    _control_nodes(
                        value.get("effects", ()), nodes, card_id, f"{here}.{key}"
                    )
                )

    return errors


def _does_something(
    node: Mapping[str, Any],
    shape: Any,
    card_id: str,
    path: str,
) -> list[str]:
    """
    Whether a control node has anything to do.

    ``{"if": ["player_alive"], "then": []}`` is a branch that runs and does
    nothing. It loads, it resolves, it changes nothing, and it reads exactly
    like a branch that works — which is the worst kind of mistake to leave for
    somebody to find during a game.

    Where a node keeps what it does is the interpreter's own statement, carried
    on the shape. A node that keeps nothing anywhere — ``stop`` — is not asked.
    """
    bodies = getattr(shape, "bodies", ())

    if not bodies:
        return []

    if any(node.get(key) for key in bodies):
        return []

    return [
        f"{card_id}: {path}: this '{shape.name}' has nothing to do — "
        f"say what happens under "
        + " or ".join(f"'{key}'" for key in bodies)
    ]


def _static_stat(
    static: Mapping[str, Any],
    monster: bool,
    card_id: str,
    path: str,
) -> list[str]:
    """
    Check a static's stat against the stats of whatever it reaches.

    Unlike ``add_modifier``, a static's landing place is known before a game.
    Two functions read statics and they never overlap: one walks player
    statics and skips any whose source has no controller, the other walks a
    monster's. A monster has no controller, so the split is automatic — and a
    player statistic written on a monster's static is read by nobody.
    """
    from fsme.rules.statics import MONSTER_SCOPES
    from fsme.state.modifiers import MONSTER_STATS, STATS

    stat = static.get("stat")

    if not isinstance(stat, str) or not stat:
        return []

    scope = str(static.get("scope", "controller"))
    reaches_monsters = scope in MONSTER_SCOPES or (monster and scope == "self")
    allowed = MONSTER_STATS if reaches_monsters else STATS

    if stat in allowed:
        return []

    whose = "a monster" if reaches_monsters else "a player"

    return [
        f"{card_id}: {path}.stat: '{stat}' is not something {whose} has"
        f"{did_you_mean(stat, allowed)}"
        f" — this static reaches {whose}, whose stats are "
        + ", ".join(f"'{one}'" for one in sorted(allowed))
    ]


LIST = "a list"

TARGET_KEYS = ("targets", "target")
"""
The two keys that hold a target specification.

An ability declares ``targets`` and binds them by name; a single effect may
point at one with ``target``. Both are targets wherever they appear.
"""


def _validate_targets(
    card: Mapping[str, Any],
    *,
    known: Collection[str] | None,
    shapes: Mapping[str, Any] | None,
    card_id: str,
) -> list[str]:
    """
    Check what a card wrote inside its targets.

    Names are checked elsewhere and are not checked again here. What this adds
    is the inside of a specification: a misspelt deck, a count written as a
    word, a flag where a family name belongs. All of those load cleanly today
    and are found — if they are found at all — somewhere in the middle of a
    game, naming no card and no file.

    A specification naming a group the ability bound with ``as`` is passed
    over. That name belongs to one card, so there is nothing to look it up in.
    """
    if not shapes:
        return []

    errors: list[str] = []

    for where, ability in _abilities_and_statics(card):
        bound = _declared_target_names(ability) | _effect_aliases(
            ability.get("effects", ())
        )

        for path, spec in _target_specs(ability, where):
            name, params = _target_call(spec)

            if name is None or name in bound or name.startswith("__"):
                continue

            shape = shapes.get(name)

            if shape is None or shape.open_ended:
                # Either the engine has never heard of this target — which the
                # name check has already said — or nobody described it.
                continue

            errors.extend(
                _check_target_params(name, params, shape, card_id, path)
            )

    return errors


def _abilities_and_statics(
    card: Mapping[str, Any],
) -> list[tuple[str, Mapping[str, Any]]]:
    """
    Everything on a card that may carry targets, and where it is written.
    """
    found: list[tuple[str, Mapping[str, Any]]] = []

    for key in ("abilities", "statics"):
        group = card.get(key, ())

        if not isinstance(group, (list, tuple)):
            continue

        found.extend(
            (f"{key}[{index}]", item)
            for index, item in enumerate(group)
            if isinstance(item, Mapping)
        )

    return found


def _target_specs(node: Any, path: str) -> list[tuple[str, Any]]:
    """
    Every target specification in an ability, with where it was found.
    """
    found: list[tuple[str, Any]] = []

    if isinstance(node, Mapping):
        for key, value in node.items():
            here = f"{path}.{key}"

            if key == "targets" and isinstance(value, (list, tuple)):
                found.extend(
                    (f"{here}[{index}]", spec) for index, spec in enumerate(value)
                )
            elif key == "target":
                found.append((here, value))
            else:
                found.extend(_target_specs(value, here))
    elif isinstance(node, (list, tuple)):
        for index, item in enumerate(node):
            found.extend(_target_specs(item, f"{path}[{index}]"))

    return found


def _target_call(spec: Any) -> tuple[str | None, dict[str, Any]]:
    """
    Reduce a target specification to a name and parameters.

    This is ``normalise`` in the resolver, read from the outside. The two must
    agree about what a card said, or validation would be checking a target the
    game will not resolve.
    """
    if isinstance(spec, str):
        return spec, {}

    if not isinstance(spec, Mapping):
        return None, {}

    if "target" in spec:
        return (
            str(spec["target"]),
            {key: value for key, value in spec.items() if key != "target"},
        )

    if len(spec) != 1:
        return None, {}

    name, value = next(iter(spec.items()))

    if isinstance(value, Mapping):
        return str(name), dict(value)

    return str(name), {"value": value}


MAPPING = "a set of named values"
"""
What ``kind`` says for a parameter holding named values.

Spelled here for the reason ``BY_ENGINE`` is: this module reads shapes as plain
data and runs without an engine. A test holds every one of these spellings
against the engine's own.
"""


def _outer_shape(
    name: str,
    parameter: Any,
    value: Any,
    location: str,
    path: str,
) -> list[str]:
    """
    Whether a parameter the effect keeps as written is the shape it keeps.

    Only the outside. ``{"effects": "gain_coins"}`` is a card that meant a list
    of things to do and wrote the name of one, which used to load and then fail
    the first time anybody played it.
    """
    if parameter is None or parameter.kind not in (LIST, MAPPING):
        return []

    fits = (
        isinstance(value, Mapping)
        if parameter.kind == MAPPING
        else isinstance(value, (list, tuple))
    )

    if fits or value is None:
        return []

    return [
        f"{location}: {path}.{parameter.name}: '{name}' takes "
        f"{parameter.kind} here, and the card gives {value!r}"
    ]


def _naming(
    parameter: Any,
    value: Any,
    where: str,
    name: str,
) -> list[str] | None:
    """
    A parameter that names somebody, checked against how it may be named.

    ``None`` means this is not one of those and the ordinary checks apply.

    The engine says both halves — what a parameter names and how a card writes
    it — so this asks the parameter rather than the effect. Nothing here knows
    which effect it is looking at, which is what stops it becoming a list of
    special cases. Until now these carried no checkable kind at all, so
    ``{"who": "the loser"}`` loaded and then died the moment somebody played
    it, which is the worst place to find out.
    """
    written = str(getattr(parameter, "written_as", "") or "")

    if not written:
        return None

    if written == BY_BINDING:
        # A name, and one the card is allowed to choose for itself.
        return [] if isinstance(value, str) else [
            f"{where}: '{name}' is bound under a name, and the card gives "
            f"{value!r}"
        ]

    if written == BY_ENGINE:
        return [
            f"{where}: '{name}' is handed this by the engine, and there is no "
            f"way for a card to write one; leave the key out"
        ]

    if written in DYNAMIC_HEADS:
        if isinstance(value, int) and not isinstance(value, bool):
            return []

        if isinstance(value, Mapping) and written in value:
            return []

        return [
            f"{where}: '{name}' takes somebody the ability picked out, written "
            f"as {{{written!r}: the name it was bound with}}, "
            f"and the card gives {value!r}"
        ]

    if isinstance(value, str):
        return []

    if isinstance(value, (list, tuple)) and all(
        isinstance(one, str) for one in value
    ):
        return []

    return [
        f"{where}: '{name}' takes the name something the ability chose was "
        f"bound with, and the card gives {value!r}"
    ]


BY_BINDING = "FSME writes this one for you"
"""
What ``written_as`` says for the name a target is bound under.

A card writes it; no author answers it. Checked as a name and nothing more.
"""

BY_ENGINE = "the engine supplies it"
"""
What ``written_as`` says for a parameter no card may write at all.

Both are spelled here rather than imported: this module is the one the content
pipeline runs without an engine, and it reads shapes as plain data on purpose.
The strings are the engine's, and a test holds the two together.
"""


def _check_target_params(
    name: str,
    params: Mapping[str, Any],
    shape: Any,
    location: str,
    path: str,
) -> list[str]:
    """
    Check what a card wrote inside one target.

    A parameter the target does not read is refused rather than ignored. That
    is not pedantry: ``of`` on an item target was dropped in silence for as
    long as anybody played the two cards that wrote it, and both did something
    other than what they say.
    """
    errors: list[str] = []

    for key in shape.params:
        if shape.params[key].required and key not in params:
            errors.append(f"{location}: {path}: '{name}' needs '{key}'")

    for key, value in params.items():
        parameter = shape.params.get(key)

        if parameter is None:
            errors.append(
                f"{location}: {path}: '{name}' takes no '{key}'"
                f"{did_you_mean(str(key), shape.params)}"
            )
            continue

        named = _naming(
            parameter, value, f"{location}: {path}", name
        )

        if named is not None:
            errors.extend(named)
            continue

        if not parameter.checkable:
            continue

        written = _kind_written(value)

        if written != parameter.kind:
            errors.append(
                f"{location}: {path}: '{name}' wants {parameter.wants()} "
                f"for '{key}', card says {value!r}"
            )
            continue

        if parameter.kind == LIST:
            # A list's allowed values are what each of its items may be.
            errors.extend(
                f"{location}: {path}: '{name}' has no '{key}' called {item!r}"
                for item in value
                if parameter.values and item not in parameter.values
            )
            continue

        if parameter.values and value not in parameter.values:
            errors.append(
                f"{location}: {path}: '{name}' wants {parameter.wants()} "
                f"for '{key}', card says {value!r}"
            )
            continue

        if parameter.least is not None and int(value) < parameter.least:
            errors.append(
                f"{location}: {path}: '{name}' wants {parameter.wants()} "
                f"for '{key}', card says {value!r}"
            )

    return errors


CONDITION_KEYS = ("conditions", "if")
"""
The two keys that hold a list of conditions.

An ability writes ``conditions``; an effect that only happens sometimes writes
``if``, and the interpreter reads either. Both are conditions wherever they
appear, which is what makes it safe to look for them anywhere in a card rather
than only in the places official cards happen to use.
"""

_UNCHECKED_KIND = "anything the engine can only judge during a game"


def _validate_conditions(
    card: Mapping[str, Any],
    *,
    known: Collection[str] | None,
    shapes: Mapping[str, Any] | None,
    card_id: str,
) -> list[str]:
    """
    Check every condition in a card, wherever it is written.

    Conditions are not confined to abilities. A static modifier carries them, a
    single effect inside an ability carries them, and a branch of a choice
    carries them again. Looking only where the shipped cards put them would
    leave a custom card's conditions unchecked exactly where the author was
    doing something less usual, so this looks everywhere.
    """
    errors: list[str] = []

    for path, nodes in _condition_lists(card):
        errors.extend(
            _check_condition_nodes(
                nodes, known=known, shapes=shapes, location=card_id, path=path
            )
        )

    return errors


def _condition_lists(node: Any, path: str = "") -> list[tuple[str, Any]]:
    """
    Every condition list in a card, with where it was found.
    """
    found: list[tuple[str, Any]] = []

    if isinstance(node, Mapping):
        for key, value in node.items():
            here = f"{path}.{key}" if path else str(key)

            if key in CONDITION_KEYS:
                found.append((here, value))
            else:
                found.extend(_condition_lists(value, here))
    elif isinstance(node, (list, tuple)):
        for index, item in enumerate(node):
            found.extend(_condition_lists(item, f"{path}[{index}]"))

    return found


def _check_condition_nodes(
    nodes: Any,
    *,
    known: Collection[str] | None,
    shapes: Mapping[str, Any] | None,
    location: str,
    path: str,
) -> list[str]:
    """
    Check one list of conditions, and anything nested inside it.
    """
    if isinstance(nodes, (str, Mapping)):
        # A card may write one condition where a list is expected; the
        # interpreter wraps it, so validation reads it the same way.
        nodes = [nodes]

    if not isinstance(nodes, (list, tuple)):
        return [f"{location}: {path}: conditions must be a list"]

    errors: list[str] = []

    for index, node in enumerate(nodes):
        errors.extend(
            _check_condition(
                node,
                known=known,
                shapes=shapes,
                location=location,
                path=f"{path}[{index}]",
            )
        )

    return errors


def _check_condition(
    node: Any,
    *,
    known: Collection[str] | None,
    shapes: Mapping[str, Any] | None,
    location: str,
    path: str,
) -> list[str]:
    """
    Check one condition node against the engine's description of it.
    """
    name, params = _condition_call(node)

    if name is None:
        return [f"{location}: {path}: condition must be a name or an object"]

    if name in _BOOLEAN_NAMES:
        return _check_condition_nodes(
            params.get("of", ()),
            known=known,
            shapes=shapes,
            location=location,
            path=f"{path}.{name}",
        )

    if known is not None and name not in known:
        return [
            f"{location}: {path}: unknown condition '{name}'"
            f"{did_you_mean(name, known)}"
        ]

    shape = shapes.get(name) if shapes else None

    if shape is None or shape.open_ended:
        return []

    return _check_condition_params(name, params, shape, location, path)


def _condition_call(node: Any) -> tuple[str | None, dict[str, Any]]:
    """
    Reduce a condition node to a name and parameters.

    This is ``normalise`` in the evaluator, read from the outside. The two must
    agree about what a card said, or validation would be checking a condition
    the game will not run.
    """
    if isinstance(node, str):
        return node, {}

    if not isinstance(node, Mapping):
        return None, {}

    if "condition" in node:
        return (
            str(node["condition"]),
            {key: value for key, value in node.items() if key != "condition"},
        )

    if len(node) != 1:
        return None, {}

    name, value = next(iter(node.items()))

    if name in _BOOLEAN_NAMES:
        return str(name), {
            "of": value if isinstance(value, (list, tuple)) else [value]
        }

    if isinstance(value, Mapping):
        return str(name), dict(value)

    return str(name), {"value": value}


def _check_condition_params(
    name: str,
    params: Mapping[str, Any],
    shape: Any,
    location: str,
    path: str,
) -> list[str]:
    """
    Check what a card wrote inside one condition.

    A parameter the condition does not read is refused rather than ignored.
    ``{"player_hp": {"operatr": "<", "value": 2}}`` is not a card asking about
    low health with a spare key attached — the misspelling is dropped and the
    comparison silently becomes "equal to zero", which is a card that plays
    wrongly and never complains.
    """
    errors: list[str] = []

    for key in shape.params:
        if shape.params[key].required and key not in params:
            errors.append(f"{location}: {path}: '{name}' needs '{key}'")

    for key, value in params.items():
        parameter = shape.params.get(key)

        if parameter is None:
            errors.append(
                f"{location}: {path}: '{name}' takes no '{key}'"
                f"{did_you_mean(str(key), shape.params)}"
            )
            continue

        if parameter.kind == _UNCHECKED_KIND:
            continue

        written = _kind_written(value)

        if written != parameter.kind:
            errors.append(
                f"{location}: {path}: '{name}' wants {parameter.wants()} "
                f"for '{key}', card says {value!r}"
            )
            continue

        if parameter.values and value not in parameter.values:
            errors.append(
                f"{location}: {path}: '{name}' wants {parameter.wants()} "
                f"for '{key}', card says {value!r}"
            )
            continue

        if parameter.least is not None and int(value) < parameter.least:
            errors.append(
                f"{location}: {path}: '{name}' wants {parameter.wants()} "
                f"for '{key}', card says {value!r}"
            )

    return errors


def _effect_aliases(nodes: Any) -> set[str]:
    """
    Names bound by targets written on individual effects.
    """
    names: set[str] = set()

    if not isinstance(nodes, (list, tuple)):
        return names

    for node in nodes:
        if not isinstance(node, Mapping):
            continue

        for spec in node.get("targets", ()) or ():
            if isinstance(spec, Mapping):
                names |= _declared_target_names({"targets": [spec]})

        target = node.get("target")

        if isinstance(target, Mapping):
            names |= _declared_target_names({"targets": [target]})

        for branch in _BRANCH_KEYS:
            names |= _effect_aliases(node.get(branch, ()))

        for mode in _modes(node):
            names |= _effect_aliases(mode.get("effects", ()))

    return names


def _declared_target_names(ability: Mapping[str, Any]) -> set[str]:
    """
    Collect the names an ability binds its own target groups under.

    An ability that declares ``{"target_player": {"as": "victim"}}`` may then
    point an effect at ``victim``. That name is not part of the engine's
    vocabulary and never will be — it belongs to this one card — so it has to
    be gathered from the ability rather than looked up.

    Only ``as`` introduces such a name. A bare string in ``targets`` does bind
    a group — under the target's own name, which is what
    ``{"targets": ["all_players"]}`` relies on — but binding is not declaring,
    and reading it as a declaration used to make every misspelling legal:
    ``{"targets": ["target_playr"]}`` loaded cleanly and stopped the game when
    the ability fired, while the same mistake written as an object was caught
    at once.
    """
    names: set[str] = set()

    declared = ability.get("targets", ())

    if not isinstance(declared, (list, tuple)):
        return names

    for spec in declared:
        if not isinstance(spec, Mapping):
            continue

        if "as" in spec:
            names.add(str(spec["as"]))
            continue

        for value in spec.values():
            if isinstance(value, Mapping) and "as" in value:
                names.add(str(value["as"]))

    return names


def _target_names(ability: Mapping[str, Any]) -> list[str]:
    """
    Collect every target named by an ability, declared or used inline.
    """
    names: list[str] = []

    declared = ability.get("targets", ())

    if isinstance(declared, (list, tuple)):
        for spec in declared:
            if isinstance(spec, str):
                names.append(spec)
            elif isinstance(spec, Mapping):
                if "target" in spec:
                    names.append(str(spec["target"]))
                else:
                    for key in spec:
                        if key != "as":
                            names.append(str(key))
                            break

    names.extend(_inline_targets(ability.get("effects", ())))

    return names


def _inline_targets(nodes: Any) -> list[str]:
    """
    Collect targets written on individual effects.
    """
    names: list[str] = []

    if not isinstance(nodes, (list, tuple)):
        return names

    for node in nodes:
        if not isinstance(node, Mapping):
            continue

        target = node.get("target")

        if isinstance(target, str) and not target.startswith("__"):
            names.append(target)
        elif isinstance(target, Mapping):
            names.extend(_spec_names(target))

        asks = node.get("targets")

        if isinstance(asks, (list, tuple)):
            for spec in asks:
                if isinstance(spec, Mapping):
                    names.extend(_spec_names(spec))
                elif isinstance(spec, str):
                    names.append(spec)

        for key in ("for_each", "of"):
            value = node.get(key)

            if isinstance(value, str):
                names.append(value)

        for branch in _BRANCH_KEYS:
            names.extend(_inline_targets(node.get(branch, ())))

        for mode in _modes(node):
            names.extend(_inline_targets(mode.get("effects", ())))

    return names


_CONTROL_NAMES = frozenset(
    {"sequence", "if", "repeat", "for_each", "stop", "may", "choose"}
)

_MODIFIER_KEYS = frozenset(
    {
        "effect",
        "target",
        "targets",
        "optional",
        "description",
        "params",
        "as",
        "prompt",
        "store",
    }
)

_BRANCH_KEYS = ("effects", "then", "else", "may")


def _effect_names(nodes: Any) -> list[str]:
    """
    Collect every effect name used by a DSL fragment, including nested ones.
    """
    names: list[str] = []

    for node in nodes:
        if isinstance(node, str):
            names.append(node)
            continue

        if not isinstance(node, Mapping):
            continue

        if "effect" in node:
            names.append(str(node["effect"]))
        elif not any(key in _CONTROL_NAMES for key in node):
            # A control node is named by its head, and everything else on it
            # belongs to that node rather than being an effect. Reading the
            # next key along as an effect name turned one typo into two
            # complaints: `{"may": [...], "promt": "..."}` is a `may` with a
            # misspelled key, not a `may` and an effect called `promt`.
            for key in node:
                if key not in _MODIFIER_KEYS and key not in _BRANCH_KEYS:
                    names.append(str(key))
                    break

        for branch in _BRANCH_KEYS:
            branch_value = node.get(branch)

            if isinstance(branch_value, (list, tuple)):
                names.extend(_effect_names(branch_value))

        for mode in _modes(node):
            names.extend(_effect_names(mode.get("effects", ())))

    return names


def _spec_names(spec: Mapping[str, Any]) -> list[str]:
    """
    Name the target a written-out specification asks for.
    """
    if "target" in spec:
        return [str(spec["target"])]

    for key in spec:
        if key not in ("as", "prompt"):
            return [str(key)]

    return []


_MODE_KEYS = ("modes", "choose")


def _modes(node: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """
    Return the modes of a "choose one" node.

    Each mode carries its own effects, and they are content like any other:
    a mode nobody picks in testing is still a mode that has to be valid.
    """
    for key in _MODE_KEYS:
        value = node.get(key)

        if isinstance(value, (list, tuple)):
            return [mode for mode in value if isinstance(mode, Mapping)]

    return []


def validate_cards(
    cards: Any,
    *,
    known_effects: Collection[str] | None = None,
    known_triggers: Collection[str] | None = None,
    known_conditions: Collection[str] | None = None,
    known_targets: Collection[str] | None = None,
    shapes: Mapping[str, Any] | None = None,
    condition_shapes: Mapping[str, Any] | None = None,
    target_shapes: Mapping[str, Any] | None = None,
    node_shapes: Mapping[str, Any] | None = None,
) -> list[str]:
    """
    Validate a collection of raw cards and report duplicate identifiers.
    """
    if not isinstance(cards, (list, tuple)):
        return [f"expected a list of cards, got {type(cards).__name__}"]

    errors: list[str] = []
    seen: set[str] = set()

    for card in cards:
        errors.extend(
            validate_card(
                card,
                known_effects=known_effects,
                known_triggers=known_triggers,
                known_conditions=known_conditions,
                known_targets=known_targets,
                shapes=shapes,
                condition_shapes=condition_shapes,
                target_shapes=target_shapes,
                node_shapes=node_shapes,
            )
        )

        if isinstance(card, Mapping) and "id" in card:
            card_id = str(card["id"])

            if card_id in seen:
                errors.append(f"{card_id}: duplicate card identifier")

            seen.add(card_id)

    return errors
