"""
The layer between what the engine can do and how a person is asked about it.

Every capability here was already described — in the engine's words, for the
engine's purposes. This is about the second description: the question a person
is put, what each allowed answer means, and when the question is worth asking
at all.

The tests are about that layer staying honest, because it is the kind of layer
that rots quietly: a new effect arrives, nobody words a question for it, and
the form falls back to an identifier that only makes sense to whoever wrote it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fsme.content.vocabulary import ASKED, DEEPER, FIRST, MORE, NEVER
from fsme.lab.desk.capabilities import catalogue
from fsme.runtime.vocabulary import engine_vocabulary

PAGE = (
    Path(__file__).resolve().parents[1]
    / "src/fsme/lab/desk/static/author.html"
)

SECTIONS = ("effects", "conditions", "targets", "cards", "abilities",
            "statics", "structures")


@pytest.fixture(scope="module")
def can() -> dict[str, Any]:
    return catalogue()


@pytest.fixture(scope="module")
def page() -> str:
    return PAGE.read_text("utf-8")


def without_comments(script: str) -> str:
    """
    The code, with the prose taken out.

    These tests are about what the renderer *does*. A comment explaining the
    sentence that used to be wrong has to be allowed to quote it.
    """
    kept = []

    for line in script.splitlines():
        stripped = line.strip()

        if stripped.startswith("//"):
            continue

        kept.append(line.split(" // ")[0] if " // " in line else line)

    return "\n".join(kept)


def every_field(can: dict[str, Any]):
    for group in SECTIONS:
        for one in can[group]:
            for field in one["fields"]:
                yield f"{one['id']}.{field['id']}", field


# ----------------------------------------------------------------------
# 1. Everything a person answers has a question worded for it
# ----------------------------------------------------------------------


def test_every_field_a_person_answers_has_been_worded(
    can: dict[str, Any],
) -> None:
    """
    The regression this file exists for.

    A parameter with no question falls back to what it *is* — a noun phrase
    written to sit inside a sentence — and reads as a dangling clause: "the
    rules it follows", "which kind of card it is". Anything somebody has to
    answer needs a question, and a new one arriving without one is a form that
    got a little worse without anybody deciding it should.
    """
    silent = [
        where
        for where, field in every_field(can)
        if field["asked"] != NEVER and not field["asks"]
    ]

    assert silent == [], f"asked for, never worded: {silent}"


def test_a_question_reads_as_a_question(can: dict[str, Any]) -> None:
    odd = [
        (where, field["asks"])
        for where, field in every_field(can)
        if field["asks"] and not field["asks"].endswith("?")
    ]

    assert odd == [], odd


def test_the_question_and_the_noun_phrase_are_different_slots(
    can: dict[str, Any],
) -> None:
    """
    Two slots because they are two jobs. `about` goes inside a sentence and
    `asks` goes above a box, and one string cannot do both — which is what
    produced "Not used while which kind of card it is says what it says".
    """
    shape = engine_vocabulary().node_shape("card")

    assert shape.params["type"].describes == "which kind of card it is"
    assert shape.params["type"].asks == "What kind of card is it?"


# ----------------------------------------------------------------------
# 2. No allowed answer reaches a person as an identifier
# ----------------------------------------------------------------------


def test_the_domains_a_card_writes_by_hand_are_all_explained(
    can: dict[str, Any],
) -> None:
    """
    Scope, stat, zone, forbidden action, kind of card: five closed lists a
    person picks from, and every one of them used to be spelled the way the
    engine spells it. `max_hp` is not an answer anybody recognises.

    Only the parts of a card a person fills in by hand are held to this. An
    effect registers its own small domains — `top` or `bottom`, `deck` or
    `discard` — in words that were already words.
    """
    bare = []

    for group in ("cards", "abilities", "statics"):
        for one in can[group]:
            for field in one["fields"]:
                if not field["choices"]:
                    continue

                missing = [
                    value
                    for value in field["choices"]
                    if value not in field["means"]
                ]

                if missing:
                    bare.append((f"{one['id']}.{field['id']}", missing[:3]))

    assert bare == [], bare


def test_a_gloss_describes_something_that_is_actually_allowed(
    can: dict[str, Any],
) -> None:
    """
    A meaning for a value the domain does not contain describes nothing, and
    is how a list of explanations comes to disagree with the list it explains.
    """
    astray = [
        (where, sorted(set(field["means"]) - set(field["choices"])))
        for where, field in every_field(can)
        if field["choices"] and set(field["means"]) - set(field["choices"])
    ]

    assert astray == [], astray


# ----------------------------------------------------------------------
# 3. When the question is asked
# ----------------------------------------------------------------------


def test_every_field_says_when_it_is_asked(can: dict[str, Any]) -> None:
    wrong = [
        (where, field["asked"])
        for where, field in every_field(can)
        if field["asked"] not in ASKED
    ]

    assert wrong == [], wrong


def test_what_a_card_does_is_asked_before_what_it_is_worth(
    can: dict[str, Any],
) -> None:
    card = next(one for one in can["cards"] if one["id"] == "card")
    asked = {field["id"]: field["asked"] for field in card["fields"]}

    assert asked["abilities"] == FIRST
    assert asked["statics"] == FIRST
    assert asked["souls"] == MORE
    assert asked["rewards"] == DEEPER


def test_an_ability_asks_when_and_what_first(can: dict[str, Any]) -> None:
    ability = next(one for one in can["abilities"] if one["id"] == "ability")
    asked = {field["id"]: field["asked"] for field in ability["fields"]}

    assert asked["trigger"] == FIRST
    assert asked["effects"] == FIRST
    # Real, and the last two anybody should meet.
    assert asked["scope"] == DEEPER
    assert asked["zone"] == DEEPER


def test_nothing_the_engine_writes_is_ever_asked(can: dict[str, Any]) -> None:
    """
    Not disabled, not explained — not there. A box for an answer that is about
    to be overwritten is worse than no box.
    """
    for where, field in every_field(can):
        if field["written"] in (
            "the engine supplies it",
            "FSME writes this one for you",
        ):
            assert field["asked"] == NEVER, where


# ----------------------------------------------------------------------
# 4. The order they are asked in
# ----------------------------------------------------------------------


def test_fields_arrive_in_the_order_they_were_declared(
    can: dict[str, Any],
) -> None:
    """
    Declared order is the order somebody would ask them in — an ability says
    trigger, then conditions, then targets, then effects. Alphabetical order
    put `attack` first on every card and asked a static "by how much" before
    "which number".
    """
    from dataclasses import fields as dataclass_fields

    from fsme.cards.definition import Ability, CardDefinition, Static

    for name, structure in (
        ("ability", Ability),
        ("static", Static),
        ("card", CardDefinition),
    ):
        published = [
            field["id"]
            for group in ("abilities", "statics", "cards")
            for one in can[group]
            if one["id"] == name
            for field in one["fields"]
        ]

        assert published == [f.name for f in dataclass_fields(structure)], name


def test_the_page_asks_in_the_order_it_is_given(page: str) -> None:
    """
    And the renderer does not sort them back.
    """
    script = page.split("<script>")[1]

    assert ".sort(" not in script.split("function fieldsHtml")[1][:900]


# ----------------------------------------------------------------------
# 5. What the page does with all of it
# ----------------------------------------------------------------------


def test_the_page_labels_with_the_question(page: str) -> None:
    script = page.split("<script>")[1]

    assert "function asksOf(f) { return f.asks || f.about; }" in script
    # And nothing labels a control with the noun phrase any more.
    assert "esc(f.about)}${needed(f)}" not in script


def test_the_page_folds_by_when_a_question_is_asked(page: str) -> None:
    script = page.split("<script>")[1]

    for when in (FIRST, MORE, DEEPER):
        assert f'"{when}"' in script, when

    assert "function folded(" in script
    assert 'f.asked === "never"' in script


def test_the_reason_a_question_is_skipped_names_the_answer(page: str) -> None:
    """
    The sentence that used to read "Not used while which kind of card it is
    says what it says" — a template given a clause where it needed a value.
    """
    script = without_comments(page.split("<script>")[1])

    assert "says what it says" not in script
    assert "function becauseOf(f, values, siblings)" in script
    # It reaches for the answer, not just the other question.
    assert "meant(other" in script


def test_the_page_never_names_an_effect_to_decide_how_to_draw_it(
    page: str, can: dict[str, Any]
) -> None:
    """
    The whole architecture in one assertion. If the renderer had to learn what
    `deal_damage` is, every effect after it would need the same.
    """
    script = without_comments(page.split("<script>")[1])
    # `shown` is the renderer's own routing vocabulary and one of its words —
    # "group" — happens to also be the name of a target. Matching on the word
    # alone would call that a violation, and it is not one.
    routing = {"form", "group", "advanced", "given", "spelling", "body", "nested"}
    named = [
        one["id"]
        for kind in ("effects", "conditions", "targets")
        for one in can[kind]
        if one["id"] not in routing
        and (f'"{one["id"]}"' in script or f"'{one['id']}'" in script)
    ]

    assert named == [], f"the renderer names: {named}"


# ----------------------------------------------------------------------
# 6. A simple card stays simple
# ----------------------------------------------------------------------


def test_a_simple_card_asks_a_handful_of_questions(can: dict[str, Any]) -> None:
    """
    The measurement the whole change was for, made where a test can keep it.

    A card that deals one damage to a player used to draw thirty-six controls
    and five hundred words. What made it so was not the engine having too many
    capabilities — it was every capability being asked about at once. So what
    is guarded here is the count of questions asked *straight away*, which is
    what a person meets, and not the count of questions that exist.

    Nothing is hidden from the engine's side: `more` and `deeper` are still
    published, still rendered, still one click away. If that stops being true
    the test above about every field reaching a control fails instead.
    """
    def asked_first(group: str, node: str) -> list[str]:
        one = next(x for x in can[group] if x["id"] == node)
        return [f["id"] for f in one["fields"] if f["asked"] == FIRST]

    # A card: what it is called, what kind it is, and what it does.
    assert len(asked_first("cards", "card")) <= 4
    # An ability: when, and what happens.
    assert len(asked_first("abilities", "ability")) <= 2
    # A static: which number, who, by how much.
    assert len(asked_first("statics", "static")) <= 3

    # And an effect asks at most one thing before "more options" — the one it
    # is mostly about, which is the one its shorthand form fills.
    for effect in can["effects"]:
        first = [f["id"] for f in effect["fields"] if f["asked"] == FIRST]

        assert len(first) <= 1, f"{effect['id']} asks {first} straight away"


def test_everything_still_reaches_a_control(can: dict[str, Any]) -> None:
    """
    The other half of the bargain: fewer questions at once, none taken away.
    """
    for where, field in every_field(can):
        assert field["asked"] in ASKED, where

    # Every parameter of every effect is still published with somewhere to go.
    for effect in can["effects"]:
        for field in effect["fields"]:
            assert field["shown"], f"{effect['id']}.{field['id']}"
