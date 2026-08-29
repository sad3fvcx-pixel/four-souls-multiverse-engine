"""
A card made by answering questions, and nothing else.

The first constructor proved the architecture and then handed somebody the
editor, which meant they still had to learn what a card is made of before they
could finish one. This is the walk that does not: pick a kind, pick an action,
answer the action's own questions, and the card is done.

Everything below is about that walk producing exactly what the editor produces
— the same node, in the same place, through the same builder, checked by the
same checker and run by the same runtime. The questions it puts, their order,
and the answers it will take are all read off the published shapes, so these
tests ask the metadata what should happen and then check that it did.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from fsme.api import load_content
from fsme.lab.desk import Workbench
from fsme.lab.desk.author import build_card, check_card
from fsme.lab.desk.capabilities import catalogue
from fsme.runtime.vocabulary import USED_BY

CONTENT = Path(__file__).resolve().parents[1] / "content"
PAGE = (
    Path(__file__).resolve().parents[1]
    / "src/fsme/lab/desk/static/author.html"
)


@pytest.fixture(scope="module")
def can() -> dict[str, Any]:
    return catalogue()


@pytest.fixture(scope="module")
def everything() -> Any:
    return load_content(CONTENT)


@pytest.fixture
def bench(everything: Any, tmp_path: Path) -> Workbench:
    return Workbench(everything, CONTENT, tmp_path / "work")


# ----------------------------------------------------------------------
# What the walk is, written out from the metadata rather than from the page
# ----------------------------------------------------------------------


def putable(field: Mapping[str, Any]) -> bool:
    """
    A question whose answer is one value, which is what ``shown`` says.
    """
    return field["asked"] != "never" and field["shown"] == "form"


def finishable(effect: Mapping[str, Any]) -> bool:
    """
    An action every one of whose required answers is a question that can be
    put. Anything else needs the editor and should not be offered here.
    """
    return all(not f["required"] or putable(f) for f in effect["fields"])


def offered(can: dict[str, Any]) -> list[dict[str, Any]]:
    """
    The actions a walk may offer, on the terms the page uses.
    """
    return [
        one
        for one in can["effects"]
        if not one.get("a_step") and not one["replacing"] and finishable(one)
    ]


def asked_about(effect: Mapping[str, Any]) -> list[dict[str, Any]]:
    """
    The value questions a walk puts for one action.
    """
    return [f for f in effect["fields"] if f["asked"] == "first" and putable(f)]


def fits(target: Mapping[str, Any], hits: str) -> bool:
    """
    The compatibility rule the validator and the runtime already share.
    """
    return (
        not hits
        or target["gives"] in ("mixed", "passthrough", "")
        or target["gives"] == hits
    )


def aims_at(can: dict[str, Any], effect: Mapping[str, Any]) -> str:
    """
    What somebody would pick when the walk asks who it happens to.
    """
    if not effect["needs_target"]:
        return ""

    allowed = [
        t
        for t in can["targets"]
        if t["aimable"] and not t.get("after") and fits(t, effect["hits"])
    ]
    common = [t for t in allowed if t.get("common")] or allowed

    return common[0]["id"] if common else ""


def answer(field: Mapping[str, Any]) -> Any:
    """
    One answer of the kind the control for this question allows.
    """
    if field["choices"]:
        return field["choices"][0]

    if field["role"] == "amount":
        return 1 if field["otherwise"] is None else field["otherwise"]

    if field["role"] == "switch":
        return True

    return "something"


def a_step(can: dict[str, Any], effect: Mapping[str, Any]) -> dict[str, Any]:
    """
    The effect node a finished walk has built.
    """
    step: dict[str, Any] = {
        "id": effect["id"],
        "fields": {f["id"]: answer(f) for f in asked_about(effect)},
    }
    aim = aims_at(can, effect)

    if aim:
        step |= {"aim": aim, "aim_fields": {}, "aim_groups": {}}

    return step


def as_the_walk(can: dict[str, Any], effect: Mapping[str, Any]) -> Any:
    """
    A card the way the walk sends it: the trigger is the engine's own answer
    for this kind of card, never typed by anybody.
    """
    trigger = next(
        one["used_by"] for one in can["kinds"] if one["id"] == "loot"
    )

    return build_card(
        {
            "set": "demo",
            "card": {
                "fields": {
                    "name": "Walked",
                    "type": "loot",
                    "abilities": [
                        {
                            "fields": {
                                "trigger": trigger,
                                "effects": [a_step(can, effect)],
                            }
                        }
                    ],
                },
                "groups": {},
            },
        }
    )


def as_the_editor(can: dict[str, Any], effect: Mapping[str, Any]) -> Any:
    """
    The same card, filled in by hand with the trigger spelled out.
    """
    return build_card(
        {
            "set": "demo",
            "card": {
                "fields": {
                    "name": "Walked",
                    "type": "loot",
                    "abilities": [
                        {
                            "fields": {
                                "trigger": USED_BY["loot"],
                                "effects": [a_step(can, effect)],
                            },
                            "groups": {},
                        }
                    ],
                },
                "groups": {},
            },
        }
    )


# ----------------------------------------------------------------------
# 1. The invariant, still
# ----------------------------------------------------------------------


def test_the_walk_and_the_editor_make_the_same_card(can: dict[str, Any]) -> None:
    """
    Every action a walk offers, both ways in, byte for byte.
    """
    differ = [
        one["id"]
        for one in offered(can)
        if json.dumps(as_the_walk(can, one), sort_keys=True)
        != json.dumps(as_the_editor(can, one), sort_keys=True)
    ]

    assert differ == [], differ


# ----------------------------------------------------------------------
# 2. A finished walk is a finished card
# ----------------------------------------------------------------------


def test_every_action_a_walk_offers_passes_the_checker(can: dict[str, Any]) -> None:
    """
    Not "most of them". A walk that offers an action nobody can finish has
    lied about what it is for, and the person finds out after typing a name.
    """
    refused = {
        one["id"]: check_card(as_the_walk(can, one))[0]
        for one in offered(can)
        if check_card(as_the_walk(can, one))
    }

    assert refused == {}, refused


def test_a_walked_card_loads_and_plays(bench: Workbench, can: dict[str, Any]) -> None:
    """
    Through the runtime, in a real game, reaching the journal.
    """
    damage = next(one for one in can["effects"] if one["id"] == "deal_damage")
    moments = [one["what"] for one in bench.show_card(as_the_walk(can, damage))]

    assert moments


# The three the engine still refuses when the card is played, and why.
#
# `EffectSpec.hits` is deliberately coarse — its own docstring says so — and
# says `cards` for effects that in fact take only stack objects or only
# monsters. Nothing published distinguishes those, so a walk cannot avoid
# offering a target these three will not accept. Named here so that the number
# cannot quietly grow, and so that a finer vocabulary, if one is ever added,
# has a list of what it was for.
COARSER_THAN_THEY_ARE = ("cancel_stack", "copy_effect", "require_attack")


def test_the_actions_a_walk_cannot_finish_are_the_known_ones(
    bench: Workbench, can: dict[str, Any]
) -> None:
    """
    Every offered action plays, except the ones the coarse target vocabulary
    cannot describe. That set is checked, not assumed.
    """
    broke = []

    for one in offered(can):
        try:
            bench.show_card(as_the_walk(can, one))
        except Exception:  # noqa: BLE001 - the reason is the effect's, not ours
            broke.append(one["id"])

    assert sorted(broke) == sorted(COARSER_THAN_THEY_ARE), broke


# ----------------------------------------------------------------------
# 3. The questions are the metadata's, not the page's
# ----------------------------------------------------------------------


def test_a_walk_asks_few_enough_questions_to_be_a_walk(can: dict[str, Any]) -> None:
    """
    The point of asking one at a time is that there are not many. If an action
    ever needs a form's worth of questions, the walk is the wrong shape for it
    and this says so rather than quietly growing a page.
    """
    too_many = {
        one["id"]: len(asked_about(one))
        for one in offered(can)
        if len(asked_about(one)) > 3
    }

    assert too_many == {}, too_many


def test_every_question_a_walk_puts_has_words_to_put_it_in(
    can: dict[str, Any],
) -> None:
    """
    A walk shows one question at a time, so a question that reads as a dangling
    noun phrase has nothing beside it to make sense of it.
    """
    wordless = [
        f"{one['id']}.{f['id']}"
        for one in offered(can)
        for f in asked_about(one)
        if not f["asks"].endswith("?")
    ]

    assert wordless == [], wordless


def test_every_action_that_needs_a_target_has_one_to_offer(
    can: dict[str, Any],
) -> None:
    """
    A target question with an empty list is a walk that cannot be finished.

    That every pair the list *does* offer survives the checker is walked
    exhaustively, and cheaply, by the boundary tests
    (``test_the_page_offers_exactly_what_the_checker_accepts``); and the whole
    card, aim and answers together, is checked for every offered action by
    ``test_every_action_a_walk_offers_passes_the_checker`` above. What is left
    for here is that the list is never empty.
    """
    empty = [
        one["id"]
        for one in offered(can)
        if one["needs_target"] and not aims_at(can, one)
    ]

    assert empty == [], empty


# ----------------------------------------------------------------------
# 4. The fact this walk needed, and where it comes from
# ----------------------------------------------------------------------


def test_an_effect_that_edits_an_event_says_so(can: dict[str, Any]) -> None:
    """
    Declared where it is enforced, and read from there.

    Exactly the effects whose handler reaches for the event being replaced.
    """
    from fsme.effects import builtin_registry

    registry = builtin_registry()
    declared = {name for name in registry.names() if registry.spec(name).replacing}
    published = {one["id"] for one in can["effects"] if one["replacing"]}

    assert declared == published
    assert declared == {"cancel_event", "modify_event", "prevent_damage"}


def test_that_effect_is_refused_when_the_card_is_written(can: dict[str, Any]) -> None:
    """
    The whole point of declaring it: the refusal arrives while somebody is
    still writing, instead of when the game throws.
    """

    def card(replacement: bool) -> Any:
        fields: dict[str, Any] = {
            "trigger": "before_damage",
            "effects": [{"id": "prevent_damage", "fields": {"amount": 1}}],
        }

        if replacement:
            fields["replacement"] = True

        return build_card(
            {
                "set": "demo",
                "card": {
                    "fields": {
                        "name": "Shield",
                        "type": "treasure",
                        "abilities": [{"fields": fields}],
                    },
                    "groups": {},
                },
            }
        )

    assert check_card(card(True)) == []

    said = check_card(card(False))

    assert said, "an event-editing effect was accepted outside a replacement"
    assert "replacement" in said[0]


def test_every_shipped_card_already_obeys_it(everything: Any) -> None:
    """
    A new refusal that refuses existing content is a bug in the refusal.
    """
    from fsme.effects import builtin_registry

    registry = builtin_registry()
    replacing = {
        name for name in registry.names() if registry.spec(name).replacing
    }
    wrong = []

    for card in everything.definitions():
        for index, ability in enumerate(card.abilities or []):
            used = _effect_names(ability.effects)

            if used & replacing and ability.replacement is not True:
                wrong.append(f"{card.card_id} ability {index}")

    assert wrong == [], wrong


def _effect_names(node: Any) -> set[str]:
    found: set[str] = set()

    if isinstance(node, Mapping):
        for key, value in node.items():
            if key == "effect" and isinstance(value, str):
                found.add(value)

            found |= _effect_names(value)
    elif isinstance(node, Sequence) and not isinstance(node, str):
        for one in node:
            found |= _effect_names(one)

    return found


def test_a_walk_offers_nothing_it_cannot_finish(can: dict[str, Any]) -> None:
    """
    What is held back, and for a reason the metadata states.
    """
    held = [
        one["id"]
        for one in can["effects"]
        if not one.get("a_step") and one not in offered(can)
    ]

    for name in held:
        one = next(x for x in can["effects"] if x["id"] == name)

        assert one["replacing"] or not finishable(one), (
            f"{name} is held back for no reason the metadata gives"
        )

    assert "prevent_damage" in held
    assert "watch_for" in held
    assert "deal_damage" not in held


# ----------------------------------------------------------------------
# 5. The page draws it, and names none of it
# ----------------------------------------------------------------------


def test_the_page_walks_without_naming_an_effect(can: dict[str, Any]) -> None:
    """
    The walk is one screen per question, drawn by the same controls the editor
    draws. If it ever names an effect, it has stopped being generic and the
    next effect the engine gains will not be offered.
    """
    script = PAGE.read_text("utf-8").split("<script>")[1]
    named = [one["id"] for one in can["effects"] if f'"{one["id"]}"' in script]

    assert named == [], named


def test_the_page_asks_one_question_at_a_time(can: dict[str, Any]) -> None:
    """
    The shape of the walk, checked where it is written.
    """
    script = PAGE.read_text("utf-8").split("<script>")[1]

    assert "function questions()" in script
    assert "function ask(" in script
    # Which questions and in what order come from the shapes, not from here.
    assert 'f.asked === "first"' in script
    assert "picksFirst" in script
