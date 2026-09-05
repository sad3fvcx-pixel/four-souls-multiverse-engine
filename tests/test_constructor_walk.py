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


ANSWERED_ELSEWHERE = ("given", "spelling", "group")
"""
The three ways of showing a field that are not a question this walk puts.

``given`` is answered by the engine or by whatever writes the card; ``spelling``
is the same question under a second name and is asked under the first; ``group``
is what aiming an action asks, which the walk puts as its own step. Everything
else the page has a control for is a question.
"""


def asks(field: Mapping[str, Any]) -> bool:
    """
    Whether the walk puts this question.

    Read off the same routing the editor draws by, so a control the language
    gains is asked without this being told. ``asked`` decides how prominent a
    question is in a *form*; a walk has no "advanced", so a required answer is
    asked wherever it sits and an optional one waits for the editor.
    """
    if field["asked"] == "never" or field["shown"] in ANSWERED_ELSEWHERE:
        return False

    return field["asked"] == "first" or field["required"]


def finishable(effect: Mapping[str, Any]) -> bool:
    """
    An action every one of whose required answers is one the walk will ask.

    The same predicate ``questions`` filters by, so the two cannot come apart:
    an action is offered exactly when answering everything it puts finishes it.
    """
    return all(not f["required"] or asks(f) for f in effect["fields"])


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
    return [f for f in effect["fields"] if asks(f)]


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


def answer(can: dict[str, Any], field: Mapping[str, Any]) -> Any:
    """
    One answer of the kind the control for this question allows.

    A control that holds more of the language is answered with one of what it
    holds — the "add" button on it, pressed once. Which kind that is comes from
    the shape, so nothing here names an effect or a node.
    """
    if field["a_list_of"]:
        return [one_of(can, field["a_list_of"])]

    if field["each_shaped_like"]:
        return {"something": one_of(can, field["each_shaped_like"])}

    if field["choices"]:
        return field["choices"][0]

    if field["role"] == "amount":
        return 1 if field["otherwise"] is None else field["otherwise"]

    if field["role"] == "switch":
        return True

    return "something"


def one_of(can: dict[str, Any], kind: str) -> dict[str, Any]:
    """
    The smallest node of a kind, as the control's own "add" button makes one.

    A step is chosen from the actions on offer, which is what the page offers
    inside a body; anything else is a shape of its own and is simply filled in.
    """
    if kind == "step":
        # A step inside a body is walked exactly as a step at the top is: the
        # action is chosen and then its own questions are answered. What it is
        # *not* is aimed — the walk aims the step it is walking, and a step
        # inside a body takes the usual target for the card. See the test
        # below for why aiming one is a separate question.
        chosen = offered(can)[0]

        return {"id": chosen["id"],
                "fields": {f["id"]: answer(can, f) for f in asked_about(chosen)}}

    shape = next(
        one
        for group in ("structures", "abilities", "statics")
        for one in can[group]
        if one["id"] == kind
    )
    filled = {f["id"]: answer(can, f) for f in shape["fields"] if f["required"]}

    return {"id": kind, "fields": filled or _one_answer(can, shape), "groups": {}}


def _one_answer(can: dict[str, Any], shape: Mapping[str, Any]) -> dict[str, Any]:
    """
    A node none of whose fields is required still has to say something.

    A change carries one of six operations and insists on none of them, and a
    change carrying nothing is a promise that changes nothing.
    """
    first = next((f for f in shape["fields"] if f["shown"] == "form"), None)

    return {first["id"]: answer(can, first)} if first else {}


def a_step(can: dict[str, Any], effect: Mapping[str, Any]) -> dict[str, Any]:
    """
    The effect node a finished walk has built.
    """
    step: dict[str, Any] = {
        "id": effect["id"],
        "fields": {f["id"]: answer(can, f) for f in asked_about(effect)},
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

    # What is left is the three that edit the event their ability is handed,
    # which is a fact about them and not about the page: the walk makes an
    # ordinary ability, and an ability that is not a replacement is not handed
    # one. `watch_for` and `promise` used to be here for a reason that was
    # about the page instead, and are not any more.
    assert sorted(held) == ["cancel_event", "modify_event", "prevent_damage"]
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


# ----------------------------------------------------------------------
# 6. Every question the walk must put, it puts
# ----------------------------------------------------------------------


def every_field(can: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (one["id"], field)
        for group in ("effects", "conditions", "targets", "cards",
                      "abilities", "statics", "structures")
        for one in can[group]
        for field in one["fields"]
    ]


def test_the_walk_asks_by_the_same_routing_the_editor_draws_by(
    can: dict[str, Any],
) -> None:
    """
    Not a list of the ways a field may be shown: three of them are questions
    somebody else puts, and the rest are questions.

    `given` is answered by the engine, `spelling` is asked under the other
    name, and `group` is what aiming an action asks — so a walk that put any
    of them would be asking twice or asking nobody. Everything else the page
    has a control for is a question, which is why a control the language gains
    is asked without this being told about it.
    """
    script = PAGE.read_text("utf-8").split("<script>")[1]

    assert "const ANSWERED_ELSEWHERE" in script
    assert 'f.shown === "form"' not in script.split("function asks(")[1][:400]


def test_a_required_answer_is_never_out_of_reach(can: dict[str, Any]) -> None:
    """
    The invariant the two gates exist for.

    `asked` says how prominent a question is in a form — straight away, behind
    "more options", behind "advanced". A walk has no "advanced": it asks one
    question after another until the action is finished. So a required answer
    is asked wherever it sits, or the action is not offered at all. There is no
    third state, and this is the test that says so.
    """
    for owner, field in every_field(can):
        if field["required"] and field["asked"] not in ("never",):
            assert asks(field), f"{owner}.{field['id']} is required and unreachable"


def test_nothing_optional_is_asked_that_was_not_asked_before(
    can: dict[str, Any],
) -> None:
    """
    The walk stays a walk. Widening it to reach a required answer must not
    drag every "more options" field onto the screen with it.
    """
    for owner, field in every_field(can):
        if not field["required"] and field["asked"] != "first":
            assert not asks(field), f"{owner}.{field['id']} became a walk question"


def test_the_two_gates_cannot_disagree(can: dict[str, Any]) -> None:
    """
    `finishable` says an action can be finished; `questions` decides what is
    put. If one widens and the other does not, the walk offers an action and
    never asks what it needs — which is a card the checker refuses, made by
    somebody who answered everything they were shown.
    """
    for one in can["effects"]:
        if not finishable(one):
            continue

        for field in one["fields"]:
            if field["required"] and field["asked"] != "never":
                assert asks(field), f"{one['id']}.{field['id']}"


def test_the_walk_now_offers_everything_that_is_not_a_replacement(
    can: dict[str, Any],
) -> None:
    """
    Two effects used to be held back for a reason that was about the page
    rather than about them: a promise owes a set of named changes and
    `watch_for` holds a list of steps, and the page could draw both long
    before the walk would ask for either.
    """
    held = [
        one["id"]
        for one in can["effects"]
        if not one.get("a_step") and not one["replacing"] and not finishable(one)
    ]

    assert held == [], held


def test_the_shipped_cards_that_needed_the_editor(can: dict[str, Any]) -> None:
    """
    The six the analysis found, by what they use rather than by name.
    """
    for name in ("promise", "watch_for"):
        one = next(x for x in can["effects"] if x["id"] == name)

        assert finishable(one), name
        assert [f["id"] for f in one["fields"] if f["required"] and asks(f)] == [
            f["id"] for f in one["fields"] if f["required"]
        ], name


def test_a_step_inside_a_body_may_be_aimed() -> None:
    """
    The walk can reach `watch_for`, so a step inside one can be aimed, and the
    card that comes out of it is a card.

    This used to record the opposite. `watch_for` keeps its steps for an event
    that has not happened yet and the runtime builds a fresh context when it
    arrives, so the ability's own list is gone by then — and the writer put the
    choice there anyway, which the checker refused and was right to. The writer
    now knows where it is, and puts the choice on the step whose body it is in.
    """
    said = {
        "set": "demo",
        "card": {
            "fields": {
                "name": "W",
                "type": "loot",
                "abilities": [
                    {
                        "fields": {
                            "trigger": "on_play",
                            "effects": [
                                {
                                    "id": "watch_for",
                                    "fields": {
                                        "event": "on_play",
                                        "effects": [
                                            {
                                                "id": "deal_damage",
                                                "fields": {"amount": 1},
                                                "aim": "target_player",
                                                "aim_fields": {},
                                                "aim_groups": {},
                                            }
                                        ],
                                    },
                                }
                            ],
                        }
                    }
                ],
            },
            "groups": {},
        },
    }

    card = build_card(said)
    ability = card["abilities"][0]

    assert check_card(card) == [], check_card(card)
    assert "targets" not in ability, "the choice went where nothing can see it"
    assert ability["effects"][0]["effects"][0]["targets"], "the step kept nothing"

    inner = said["card"]["fields"]["abilities"][0]["fields"]["effects"][0]
    inner["fields"]["effects"][0].pop("aim")

    assert check_card(build_card(said)) == [], "and unaimed it is a fine card too"


# ----------------------------------------------------------------------
# An event is walked like anything else the engine settles
# ----------------------------------------------------------------------
#
# The walk skips "when does this happen" for a kind the engine has one answer
# for, and hands the whole card to the editor for a kind it has not. An event
# looked like the second and is the first: nobody plays one — it is turned
# over out of the monster deck — but once it is turned over `_resolve_event`
# does what a played loot card does and emits the same moment.
#
# So these are the loot tests asked about an event, and they pass for the same
# reason: nothing in the walk knows what kind of card it is walking.


def the_walk_asks(can: dict[str, Any], kind: str) -> str:
    """
    What the page would fill in for this kind, or nothing if it must ask.

    Read the way `pickKind` reads it, because that is the thing being checked:
    a kind with an answer goes to the questions, one without goes to the
    editor with the kind already set.
    """
    return next(one["used_by"] for one in can["kinds"] if one["id"] == kind)


def test_choosing_an_event_reaches_the_questions(can: dict[str, Any]) -> None:
    """
    The entry point, which is the whole of what changed.
    """
    assert the_walk_asks(can, "event") == "on_play"


def test_the_kinds_that_must_still_ask_still_do(can: dict[str, Any]) -> None:
    """
    And the ones that were not touched. Each reacts to several moments, so
    the page hands over the editor rather than choosing one of them.
    """
    for kind in ("monster", "character", "curse", "room"):
        assert the_walk_asks(can, kind) == "", kind


def test_an_event_walked_through_is_a_card_the_engine_takes(
    can: dict[str, Any],
) -> None:
    """
    The path a person walks: pick the kind, pick one action, answer it, keep
    it. Nothing here says `on_play` — the kind said it.
    """
    effect = next(one for one in offered(can) if one["id"] == "gain_coins")
    card = build_card(
        {
            "set": "demo",
            "card": {
                "fields": {
                    "name": "Walked Event",
                    "type": "event",
                    "abilities": [
                        {
                            "fields": {
                                "trigger": the_walk_asks(can, "event"),
                                "effects": [a_step(can, effect)],
                            }
                        }
                    ],
                },
                "groups": {},
            },
        }
    )

    assert card["type"] == "event"
    assert card["abilities"][0]["trigger"] == "on_play"
    assert check_card(card) == [], check_card(card)


def test_a_walked_event_opens_again_saying_the_same_thing(
    can: dict[str, Any],
) -> None:
    """
    Kept and opened again. A card whose meaning survives the round trip is the
    contract every other kind is already held to, and an event is not exempt
    from it for being reached a different way.
    """
    from fsme.lab.desk.author import read_card

    effect = next(one for one in offered(can) if one["id"] == "gain_coins")
    made = build_card(
        {
            "set": "demo",
            "card": {
                "fields": {
                    "name": "Walked Event",
                    "type": "event",
                    "abilities": [
                        {
                            "fields": {
                                "trigger": the_walk_asks(can, "event"),
                                "effects": [a_step(can, effect)],
                            }
                        }
                    ],
                },
                "groups": {},
            },
        }
    )
    again = build_card(read_card(made))

    assert again == made, "opening it again said something else"
    assert check_card(again) == []


# ----------------------------------------------------------------------
# When the engine settles no moment, the walk asks for one
# ----------------------------------------------------------------------
#
# Four kinds have one right answer and the walk fills it in: a loot card is
# played, an item is used, an event is turned over and resolved. The rest react
# to several moments and no one of them is *the* moment — which was why they
# were handed the whole card instead.
#
# So the walk asks. Nothing about the question is about a kind: the moments are
# the ones the ability's own trigger field offers, shown by the sentence the
# engine carries about each, and a moment the engine gains is offered without
# this being told. What is limited is how far it has been taken, not what it
# can do.


def script() -> str:
    return PAGE.read_text("utf-8").split("<script>")[1]


def test_the_walk_puts_the_question_when_nothing_settles_it() -> None:
    """
    The screen exists, and `pickKind` reaches it instead of the editor.
    """
    said = script()

    assert "function chooseMoment()" in said
    assert "return chooseMoment()" in said


def test_the_moments_offered_are_the_engines_own(can: dict[str, Any]) -> None:
    """
    Read from the catalogue, not written down here.

    A list in the page would go on offering the same handful after the engine
    gained a moment, which is the failure this whole screen is built to avoid.
    """
    said = script()
    named = [one["id"] for one in can["triggers"] if f'"{one["id"]}"' in said]

    assert named == [], named
    assert "can.triggers" in said, "the moments come from somewhere else"


def test_the_question_splits_the_moments_the_way_everything_else_is_split(
    can: dict[str, Any],
) -> None:
    """
    The handful somebody usually wants, and the rest a click away — the same
    grammar the actions use, not a second one.
    """
    said = script().split("function chooseMoment()")[1].split("\n}")[0]

    assert "t.common" in said, "the split is not the published one"
    assert "!t.common" in said
    assert "t.about" in said, "a moment is shown by something other than itself"
    assert any(one["common"] for one in can["triggers"])


def test_the_kinds_the_engine_settles_are_never_asked(can: dict[str, Any]) -> None:
    """
    Four kinds have an answer, so the question would be a second one put about
    something already decided.
    """
    said = script()
    where = said.index("function pickKind(")
    body = said[where:said.index("\n}", where)]

    # The question is reached only where there is no answer to read.
    assert body.index("if (of.used_by) return chooseAction(of.used_by)") < body.index(
        "chooseMoment()"
    ), "a kind the engine settles could reach the question"

    for kind in ("loot", "treasure", "starting_item", "event"):
        assert next(
            one["used_by"] for one in can["kinds"] if one["id"] == kind
        ), kind


def test_how_far_this_has_been_taken_is_published_not_written_down(
    can: dict[str, Any],
) -> None:
    """
    The kinds walked so far, said once and where the kinds themselves are said.

    Not a claim about the language — `chooseMoment` knows nothing about kinds —
    so it is checked as a stage and not as a rule. It is beside `used_by`
    because it answers the half of that question `used_by` leaves open: no
    moment is settled, and this says whether the walk is the one to ask.
    """
    asked = {one["id"] for one in can["kinds"] if one["moment_is_asked"]}

    assert asked == {"curse", "character", "monster"}
    # Every one of them is a kind the engine settles no moment for, or the
    # question would be a second one put about something already decided.
    for one in can["kinds"]:
        assert not (one["moment_is_asked"] and one["used_by"]), one["id"]


def test_the_page_names_no_kind_of_card_at_all() -> None:
    """
    Neither the question nor the routing to it may carry its own list.

    A list of kinds in the page is the same mistake as a list of moments: it
    goes on saying the same thing after the engine has changed. It also reads
    as a rule about a kind when it is nothing of the sort — the collision that
    found this is that `character` is a target as well, and the page's standing
    rule is that it names none of those either.
    """
    runs = "\n".join(
        one.split("//")[0] for one in script().splitlines()
    )
    named = [
        one for one in catalogue()["kinds"] if f'"{one["id"]}"' in runs
    ]

    assert named == [], [one["id"] for one in named]


def a_walked_card(can: dict[str, Any], kind: str, moment: str) -> Any:
    """
    A card the way the walk sends one whose moment was answered rather than
    filled in: the kind, the moment that was picked, one action.
    """
    effect = next(one for one in offered(can) if one["id"] == "gain_coins")

    return build_card(
        {
            "set": "demo",
            "card": {
                "fields": {
                    "name": "Walked",
                    "type": kind,
                    "abilities": [
                        {"fields": {"trigger": moment, "effects": [a_step(can, effect)]}}
                    ],
                },
                "groups": {},
            },
        }
    )


@pytest.mark.parametrize(
    ("kind", "moment"),
    [("curse", "turn_end"), ("character", "on_activate")],
)
def test_a_card_whose_moment_was_asked_for_is_a_card_the_engine_takes(
    can: dict[str, Any], kind: str, moment: str
) -> None:
    """
    Both kinds this has been taken to, each at a moment its own shipped cards
    use. The moment is the only thing that came from the question; everything
    after it is the walk that was already there.
    """
    card = a_walked_card(can, kind, moment)

    assert card["type"] == kind
    assert card["abilities"][0]["trigger"] == moment
    assert check_card(card) == [], check_card(card)


@pytest.mark.parametrize(
    ("kind", "moment"),
    [("curse", "turn_end"), ("character", "on_activate")],
)
def test_a_card_whose_moment_was_asked_for_opens_again_the_same(
    can: dict[str, Any], kind: str, moment: str
) -> None:
    """
    Kept and opened again, which is the contract every other kind is held to.
    """
    from fsme.lab.desk.author import read_card

    made = a_walked_card(can, kind, moment)
    again = build_card(read_card(made))

    assert again == made, "opening it again said something else"
    assert check_card(again) == []


def test_every_moment_the_question_offers_has_somewhere_to_go(
    can: dict[str, Any]
) -> None:
    """
    The question offers the engine's moments; the walk has to be able to put
    each of them on a card. Both come from the shapes, so this checks they
    still meet rather than assuming it.
    """
    for one in can["triggers"]:
        card = a_walked_card(can, "curse", one["id"])

        assert card["abilities"][0]["trigger"] == one["id"], one["id"]
        assert check_card(card) == [], (one["id"], check_card(card))


# ----------------------------------------------------------------------
# What is printed on a card, as opposed to what it does
# ----------------------------------------------------------------------
#
# Everything the walk asked until now was something the card *does*. A monster
# also carries numbers because of what it *is* — hit points, what it hits for,
# the roll needed to hit it — and no question about an effect will ever reach
# them, because they are not on an effect.
#
# Which numbers a kind carries is a fact the engine already held and only half
# published. Each number says which kinds do *not* have it, which is the right
# answer for a form: a kind nobody has described is in no such list, so the
# form shows the box rather than hiding an answer it cannot rule out. It is the
# wrong answer for a walk, which would then ask a soul card for hit points. So
# the other half is published beside it, and the screen is built from that.


def test_what_each_kind_prints_is_published(can: dict[str, Any]) -> None:
    """
    Read from the engine's own table, for every kind, not only the ones a walk
    happens to reach.
    """
    printed = {one["id"]: tuple(one["printed"]) for one in can["kinds"]}

    assert printed["monster"] == ("health", "attack", "roll")
    assert printed["character"] == ("health", "attack")
    assert printed["treasure"] == ("cost",)
    # A kind that carries none, and a kind nobody has described, both say so by
    # being empty — and the walk has nothing to put for either.
    assert printed["loot"] == ()
    assert printed["soul"] == ()


def test_the_two_halves_of_the_printed_numbers_agree(can: dict[str, Any]) -> None:
    """
    The half a field publishes and the half a kind publishes come from one
    table, and this is what stops them becoming two.

    A number's `unless_when` lists the kinds that do not carry it. Where a kind
    is described at all, that list and this one are the same fact said twice —
    so every number a kind is said to print must be one no number excludes it
    from, and the other way about.
    """
    fields = {
        one["id"]: one
        for one in next(n for n in can["cards"] if n["id"] == "card")["fields"]
        if one["unless"] == "type"
    }
    described = {
        one["id"] for one in can["kinds"]
        if any(one["id"] in fields[f]["unless_when"] for f in fields)
        or one["printed"]
    }

    assert described, "no kind is described at all"

    for kind in can["kinds"]:
        if kind["id"] not in described:
            continue

        expected = {
            name for name, f in fields.items()
            if kind["id"] not in f["unless_when"]
        }

        assert set(kind["printed"]) == expected, kind["id"]


def test_the_screen_is_built_from_that_and_names_no_number() -> None:
    """
    The page picks the card's own fields by what the kind says it prints. A
    list of names here would be the third copy of the same table, and the one
    that could not be checked against the engine.
    """
    said = script()

    assert "function printedFields()" in said
    assert "of.printed" in said, "the numbers come from somewhere else"

    where = said.index("function printedFields()")
    body = said[where:said.index("\n}", where)]

    for name in ("health", "attack", "roll", "cost", "souls"):
        assert f'"{name}"' not in body, name


def test_a_kind_that_prints_nothing_is_never_asked() -> None:
    """
    The screen is skipped rather than shown empty, which is the difference
    between "there is nothing to say" and "you have said nothing".
    """
    said = script()
    where = said.index("function finish(")
    body = said[where:said.index("\n}", where)]

    assert "printedFields().length" in body
    assert "done(" in body, "a kind with no numbers never reaches the end"


def a_printed_card(can: dict[str, Any], kind: str, moment: str, **numbers: int) -> Any:
    """
    A card the way the walk sends one whose numbers were answered: the kind,
    the moment, one action, and what the kind prints.
    """
    effect = next(one for one in offered(can) if one["id"] == "gain_coins")

    return build_card(
        {
            "set": "demo",
            "card": {
                "fields": {
                    "name": "Printed",
                    "type": kind,
                    **numbers,
                    "abilities": [
                        {"fields": {"trigger": moment, "effects": [a_step(can, effect)]}}
                    ],
                },
                "groups": {},
            },
        }
    )


def test_a_monster_walked_through_keeps_what_is_printed_on_it(
    can: dict[str, Any],
) -> None:
    """
    The whole point of the screen: the numbers reach the card, survive being
    written, and come back saying the same thing.
    """
    from fsme.lab.desk.author import read_card

    card = a_printed_card(can, "monster", "monster_killed", health=3, attack=1, roll=4)

    assert card["type"] == "monster"
    assert card["abilities"][0]["trigger"] == "monster_killed"
    assert (card["health"], card["attack"], card["roll"]) == (3, 1, 4)
    assert check_card(card) == [], check_card(card)
    assert build_card(read_card(card)) == card, "opening it again said something else"


def test_every_kind_the_walk_reaches_keeps_every_number_it_prints(
    can: dict[str, Any],
) -> None:
    """
    Over the kinds rather than over monsters: whatever a kind is said to print
    is a number the walk can put on it and the writer keeps.
    """
    from fsme.lab.desk.author import read_card

    reached = [
        one for one in can["kinds"]
        if (one["used_by"] or one["moment_is_asked"]) and one["printed"]
    ]

    assert {one["id"] for one in reached} == {"treasure", "character", "monster"}

    for one in reached:
        numbers = {name: 2 for name in one["printed"]}
        moment = one["used_by"] or "turn_end"
        card = a_printed_card(can, one["id"], moment, **numbers)

        for name in one["printed"]:
            assert card.get(name) == 2, (one["id"], name)

        assert check_card(card) == [], (one["id"], check_card(card))
        assert build_card(read_card(card)) == card, one["id"]


def test_the_kinds_that_print_nothing_gain_no_numbers(can: dict[str, Any]) -> None:
    """
    A loot card walked through is the card it was before this screen existed.
    """
    fields = {
        one["id"]
        for one in next(n for n in can["cards"] if n["id"] == "card")["fields"]
        if one["unless"] == "type"
    }

    for kind in ("loot", "event", "starting_item", "curse"):
        one = next(k for k in can["kinds"] if k["id"] == kind)

        assert one["printed"] == [], kind

        card = a_printed_card(can, kind, one["used_by"] or "turn_end")

        assert not (fields & set(card)), (kind, fields & set(card))
        assert check_card(card) == [], (kind, check_card(card))


def test_a_monster_is_a_kind_the_walk_asks_the_moment_of(can: dict[str, Any]) -> None:
    """
    The engine settles no moment for a monster and it is not in `USED_BY`; the
    walk asks, the same way it asks a curse.
    """
    monster = next(one for one in can["kinds"] if one["id"] == "monster")

    assert monster["used_by"] == "", "a monster was given one settled moment"
    assert monster["moment_is_asked"] is True
    assert "monster" not in USED_BY


def test_every_moment_a_real_monster_uses_can_be_put_on_one(
    can: dict[str, Any],
) -> None:
    """
    The thirteen moments the shipped monsters actually react to, built the way
    the walk builds one. Read off the content rather than listed here, so a
    moment the sets gain is checked without this being told.
    """
    library = load_content(CONTENT)
    moments = sorted(
        {
            str(ability.trigger)
            for card in library.definitions()
            if str(card.type) == "monster"
            for ability in card.abilities
        }
    )

    assert moments, "no shipped monster reacts to anything"

    for moment in moments:
        card = a_printed_card(can, "monster", moment, health=2, attack=1, roll=4)

        assert card["abilities"][0]["trigger"] == moment, moment
        assert check_card(card) == [], (moment, check_card(card))


def test_a_number_left_off_stays_off(can: dict[str, Any]) -> None:
    """
    The screen asks; it does not answer.

    A monster that prints no attack is a real card — `death` is one, and the
    engine has a documented answer for the blow it deals when the card names
    none. Turning an unanswered question into a number would put a fact on the
    card that its author never said, and the round trip would then swear the
    card had always said it.
    """
    from fsme.lab.desk.author import read_card

    card = a_printed_card(can, "monster", "monster_killed", health=3, roll=4)

    assert card["health"] == 3
    assert card["roll"] == 4
    assert "attack" not in card, card.get("attack")
    assert check_card(card) == [], check_card(card)
    assert build_card(read_card(card)) == card


# ----------------------------------------------------------------------
# A rule that waits for nothing
# ----------------------------------------------------------------------
#
# Everything the walk could make until now was a reaction: a moment, and the
# things that happen at it. A card may also change a number for as long as it
# is in play, and such a rule has no moment and nothing that happens in it —
# so no question about an action was ever going to reach one, and picking an
# effect was the only way a part of a card came into being at all.
#
# The two sides of that are already told apart, and were before this: a part
# that holds a list of steps is the reacting sort, which is the test `doesIn`
# makes to decide whether to show a card's parts as the things they do. This
# is the other side of the same test, and nothing about it is about any one
# shape — a part the language gains lands on whichever side it belongs to.


def parts_of(can: dict[str, Any]) -> list[dict[str, Any]]:
    """
    The card's own fields that are lists of a part the catalogue describes.
    """
    shapes = {
        one["id"]: one
        for group in ("abilities", "statics", "structures", "cards")
        for one in can[group]
    }
    card = next(n for n in can["cards"] if n["id"] == "card")

    return [
        {"list": f, "part": shapes[f["a_list_of"]]}
        for f in card["fields"]
        if f["a_list_of"] in shapes
    ]


def test_a_card_holds_both_sorts_of_rule(can: dict[str, Any]) -> None:
    """
    What the route is built on: some parts are made of things that happen and
    some are not, and the card says which of its lists hold which.
    """
    holds = {
        one["part"]["id"]: any(
            f["a_list_of"] == "step" for f in one["part"]["fields"]
        )
        for one in parts_of(can)
    }

    assert True in holds.values(), "no part of a card is made of steps"
    assert False in holds.values(), "every part of a card is made of steps"


def test_the_walk_can_make_a_rule_that_is_not_made_of_steps() -> None:
    """
    The route exists, and is reached from both screens that ask somebody what
    their card does — the one that asks a moment first and the one that does
    not. A card whose moment the engine settles never sees the first, so an
    option offered only there would be unreachable for most of the kinds that
    have such rules.
    """
    said = script()

    assert "function standingShapes()" in said
    assert "function pickShape(" in said

    for screen in ("chooseAction", "chooseMoment"):
        where = said.index(f"function {screen}(")
        body = said[where:said.index("\n}", where)]

        assert "standingHtml()" in body, screen


def test_which_rules_those_are_is_read_and_not_listed(can: dict[str, Any]) -> None:
    """
    The route finds them by asking whether the part is made of steps, which is
    the test the walk already made to decide what to show. A list of shapes
    here would be a second answer to a question already answered.
    """
    said = script()
    where = said.index("function standingShapes()")
    body = said[where:said.index("\n}", where)]

    assert 'a_list_of === "step"' in body, "the two sorts are told apart some other way"

    for one in parts_of(can):
        assert f'"{one["part"]["id"]}"' not in body, one["part"]["id"]
        assert f'"{one["list"]["id"]}"' not in body, one["list"]["id"]


def test_the_page_names_no_part_of_a_card(can: dict[str, Any]) -> None:
    """
    Neither the shapes nor the lists they live in, anywhere the page runs.

    The same standing rule that keeps effects, targets and kinds of card out of
    the page. A name here reads as a rule about one shape, and the next shape
    the language gains would quietly not get it.
    """
    runs = "\n".join(one.split("//")[0] for one in script().splitlines())

    for one in parts_of(can):
        assert f'"{one["part"]["id"]}"' not in runs, one["part"]["id"]
        assert f'"{one["list"]["id"]}"' not in runs, one["list"]["id"]


def test_the_option_is_worded_by_the_shape_itself(can: dict[str, Any]) -> None:
    """
    What the button says comes from what the shape says about itself, so a
    shape the language gains introduces itself.
    """
    said = script()
    where = said.index("function standingHtml()")
    body = said[where:said.index("\n}", where)]

    assert "one.part.about" in body, "the wording is written here instead"

    for one in parts_of(can):
        assert one["part"]["about"], one["part"]["id"]


def a_standing_card(can: dict[str, Any], kind: str, **numbers: int) -> Any:
    """
    A card the way the new route sends one: the kind, one rule that waits for
    nothing, and whatever the kind prints.
    """
    return build_card(
        {
            "set": "demo",
            "card": {
                "fields": {
                    "name": "Standing",
                    "type": kind,
                    **numbers,
                    "statics": [
                        {
                            "id": "static",
                            "fields": {
                                "scope": "self",
                                "stat": "attack",
                                "amount": 1,
                            },
                            "groups": {},
                        }
                    ],
                },
                "groups": {},
            },
        }
    )


@pytest.mark.parametrize(
    ("kind", "numbers"),
    [
        ("monster", {"health": 3, "attack": 1, "roll": 4}),
        ("treasure", {"cost": 5}),
        ("curse", {}),
    ],
)
def test_a_card_whose_only_rule_waits_for_nothing(
    can: dict[str, Any], kind: str, numbers: dict[str, int]
) -> None:
    """
    The three kinds the shipped sets actually write such cards for, each built
    the way the walk builds one, kept and opened again.
    """
    from fsme.lab.desk.author import read_card

    card = a_standing_card(can, kind, **numbers)

    assert card["type"] == kind
    assert card["statics"] == [{"stat": "attack", "amount": 1, "scope": "self"}]
    assert not card.get("abilities"), "a rule that waits for nothing made one"
    assert check_card(card) == [], check_card(card)
    assert build_card(read_card(card)) == card, "opening it again said something else"


def test_the_kinds_that_write_such_cards_are_the_kinds_this_reaches(
    can: dict[str, Any],
) -> None:
    """
    Read off the content rather than listed: every kind that ships a card whose
    only rules are of the standing sort is a kind the walk now takes.
    """
    library = load_content(CONTENT)
    kinds = {
        str(card.type)
        for card in library.definitions()
        if card.statics and not card.abilities
    }

    assert kinds, "no shipped card has only standing rules"

    walked = {
        one["id"] for one in can["kinds"]
        if one["used_by"] or one["moment_is_asked"]
    }

    assert kinds <= walked, kinds - walked


def test_a_standing_rule_does_not_take_the_place_of_an_ability(
    can: dict[str, Any],
) -> None:
    """
    Both sorts on one card, which is how fourteen shipped cards are written.
    The walk shows them through the screen that already shows a card's parts,
    rather than a second way of choosing between them.
    """
    from fsme.lab.desk.author import read_card

    effect = next(one for one in offered(can) if one["id"] == "gain_coins")
    card = build_card(
        {
            "set": "demo",
            "card": {
                "fields": {
                    "name": "Both",
                    "type": "monster",
                    "health": 3,
                    "abilities": [
                        {
                            "fields": {
                                "trigger": "monster_killed",
                                "effects": [a_step(can, effect)],
                            }
                        }
                    ],
                    "statics": [
                        {
                            "id": "static",
                            "fields": {"scope": "self", "stat": "difficulty",
                                       "amount": 1},
                            "groups": {},
                        }
                    ],
                },
                "groups": {},
            },
        }
    )

    assert card["abilities"][0]["trigger"] == "monster_killed"
    assert card["statics"] == [
        {"stat": "difficulty", "amount": 1, "scope": "self"}
    ]
    assert check_card(card) == [], check_card(card)
    assert build_card(read_card(card)) == card


def test_every_shipped_card_of_the_standing_sort_still_round_trips() -> None:
    """
    Over the cards themselves. The route makes what these already are, so if
    the writer stopped keeping one of them the route would be making something
    the engine had never been given.
    """
    from fsme.lab.desk.author import read_card

    standing = [
        card
        for card in every_shipped_card()
        if card.get("statics") and not card.get("abilities")
    ]

    assert len(standing) >= 18, len(standing)

    for card in standing:
        once = build_card(read_card(card, set_id=str(card["expansion"])))

        assert once["statics"] == card["statics"], card["id"]
        assert check_card(once) == [], (card["id"], check_card(once))
        assert build_card(read_card(once, set_id=str(card["expansion"]))) == once, (
            card["id"]
        )


def every_shipped_card() -> list[dict[str, Any]]:
    """
    Every shipped card as it is written on disk, rather than as the engine
    holds it — this is about what the writer puts back, so it is the file that
    has to be compared against.
    """
    found = []

    for path in sorted(CONTENT.rglob("*.json")):
        if path.name == "manifest.json" or path.name.startswith("_"):
            continue

        data = json.loads(path.read_text("utf-8"))
        cards = data["cards"] if isinstance(data, dict) and "cards" in data else (
            data if isinstance(data, list) else [data]
        )
        found.extend(one for one in cards if isinstance(one, dict))

    return found
