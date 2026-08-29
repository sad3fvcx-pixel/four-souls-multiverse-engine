"""
What the form asks, against what the engine says it should ask.

The Author UI renders from capability metadata and from nothing else. That is
the property under test here, and it is a property of the *renderer*: there is
no list of effects in the page, so an effect the engine gains draws itself and
an effect whose metadata changes draws itself differently.

The page is JavaScript, so what is checked is the two halves the page sits
between — the metadata it reads, and the card it produces. A field that the
metadata routes to a control the page has, filled in the way that control
fills it, must come out as a card the ordinary validation accepts; and a field
routed away from the form must not be reachable as a text box.

These are the mistakes the older renderer made. Each one shipped, each one
looked like a bug in one effect, and none of them was.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fsme.content.vocabulary import (
    A_LIST,
    BY_BINDING,
    BY_ENGINE,
    BY_NAME,
    BY_PLAYER_OF,
    STRUCTURE,
    WHOM,
)
from fsme.lab.desk.author import build_card, check_card
from fsme.lab.desk.capabilities import catalogue

PAGE = (
    Path(__file__).resolve().parents[1]
    / "src/fsme/lab/desk/static/author.html"
)


@pytest.fixture(scope="module")
def can() -> dict[str, Any]:
    return catalogue()


def every_field(can: dict[str, Any]):
    for group in ("effects", "conditions", "targets"):
        for one in can[group]:
            for field in one["fields"]:
                yield group, one["id"], field


def a_card(effects: list[dict[str, Any]]) -> dict[str, Any]:
    return build_card(
        {
            "set": "demo",
            "name": "Under Test",
            "kind": "loot",
            "ability": {"trigger": "on_play", "effects": effects},
        }
    )


def one_effect(card: dict[str, Any]) -> dict[str, Any]:
    return dict(card["abilities"][0]["effects"][0])


# ----------------------------------------------------------------------
# 1. A closed set of values is a choice
# ----------------------------------------------------------------------


def test_a_scalar_domain_is_offered_as_a_choice(can: dict[str, Any]) -> None:
    """
    Every parameter with a domain reaches the form carrying that domain, so the
    page can draw a selection rather than a box somebody types a guess into.
    """
    for _, owner, field in every_field(can):
        if not field["choices"]:
            continue

        assert field["shown"] == "form", f"{owner}.{field['id']}"
        assert field["role"] in ("which", "names"), f"{owner}.{field['id']}"
        assert not field["many"] or field["kind"] == A_LIST


def test_the_page_draws_a_choice_from_the_choices() -> None:
    """
    The renderer's own branch, read off the page: a `which` with choices is a
    `<select>`, and nothing about which effect it belongs to is consulted.
    """
    page = PAGE.read_text("utf-8")

    assert 'f.role === "which" && f.choices.length' in page
    assert "<select" in page


# ----------------------------------------------------------------------
# 2. A domain of several values is several choices
# ----------------------------------------------------------------------


def test_a_list_domain_is_marked_as_taking_more_than_one(
    can: dict[str, Any],
) -> None:
    """
    `"loot"` and `["loot"]` look the same in a form and are not the same in a
    card, so the difference has to survive as far as the control.
    """
    many = [
        f"{owner}.{field['id']}"
        for _, owner, field in every_field(can)
        if field["many"]
    ]

    assert set(many) == {
        "all_stack.kinds",
        "all_stack.triggers",
        "target_stack_item.kinds",
        "target_stack_item.triggers",
    }

    for _, owner, field in every_field(can):
        if field["many"]:
            assert field["kind"] == A_LIST, f"{owner}.{field['id']}"
            assert field["choices"], f"{owner}.{field['id']}"


def test_several_values_reach_the_card_as_several() -> None:
    # `cancel_stack` because this is about a list of values arriving as a
    # list. It is the effect that really acts on a thing waiting on the
    # stack, and a card that aimed something else there would now be refused
    # for that instead — which is a different test.
    card = a_card(
        [
            {
                "id": "cancel_stack",
                "fields": {},
                "aim": "target_stack_item",
                "aim_fields": {"kinds": ["loot", "dice"]},
            }
        ]
    )
    chosen = card["abilities"][0]["targets"][0]["target_stack_item"]

    assert chosen["kinds"] == ["loot", "dice"]
    assert check_card(card) == []


def test_one_value_where_a_list_belongs_is_still_refused() -> None:
    """
    The check that would have caught the old single `<select>`.
    """
    card = a_card(
        [
            {
                "id": "gain_coins",
                "fields": {"amount": 1},
                "aim": "target_stack_item",
                "aim_fields": {"kinds": "loot"},
            }
        ]
    )

    assert check_card(card), "a scalar passed where a list was wanted"


def test_the_page_draws_several_choices_for_a_list() -> None:
    page = PAGE.read_text("utf-8")

    assert "if (f.many)" in page
    assert "select multiple" in page
    assert "selectedOptions" in page


# ----------------------------------------------------------------------
# 3. Naming somebody is not typing their name
# ----------------------------------------------------------------------


def test_nothing_that_names_somebody_is_a_text_box(can: dict[str, Any]) -> None:
    """
    `give_treasure.to`, `take_card.player`, `deal_damage.dealt_by`,
    `require_attack.who`, `claim_soul.card` — every one of them used to fall
    through to a plain input, because the renderer looked at `kind` and these
    have no kind anything can check.
    """
    for _, owner, field in every_field(can):
        if field["role"] != WHOM:
            continue

        assert field["shown"] in ("group", "given"), f"{owner}.{field['id']}"
        assert field["written"] in (BY_NAME, BY_PLAYER_OF, BY_ENGINE)
        assert field["picks"] in ("players", "cards")


def test_the_ones_that_name_a_player_are_picked_not_typed(
    can: dict[str, Any],
) -> None:
    """
    Every effect parameter that is handed a seat rather than a number.

    Listed rather than counted, so that one arriving or leaving is looked at
    rather than passing as a number that changed. `transfer_coins.source_player`
    is here because its handler resolves it with `state.player` and said so
    nowhere — a form offered a box for typing a whole number into, and reading
    a card back could not tell the naming from an amount.
    """
    named = {
        f"{owner}.{field['id']}"
        for group, owner, field in every_field(can)
        if group == "effects" and field["written"] == BY_PLAYER_OF
    }

    assert named == {
        "deal_damage.dealt_by",
        "divide_damage.dealt_by",
        "give_treasure.to",
        "require_attack.who",
        "take_card.player",
        "transfer_coins.source_player",
    }


def test_a_player_the_ability_chose_is_written_as_the_engine_reads_it() -> None:
    """
    The author picks a target; the card gets both halves — a group bound with
    `as`, and the parameter naming it the one way the executor understands.
    """
    card = a_card(
        [
            {
                "id": "give_treasure",
                "fields": {},
                "groups": {"to": {"id": "another_player", "fields": {}}},
                "aim": "target_treasure",
                "aim_fields": {},
            }
        ]
    )
    given = one_effect(card)

    assert given["to"] == {"player_of": "chosen_1"}
    assert card["abilities"][0]["targets"][0] == {
        "another_player": {"as": "chosen_1"}
    }
    assert check_card(card) == []


def test_typing_a_name_into_one_of_them_is_refused() -> None:
    card = a_card(
        [{"id": "give_treasure", "fields": {"to": "the other one"}}]
    )
    problems = check_card(card)

    assert problems, "free text passed where a player belongs"
    assert "player_of" in problems[0]


def test_a_card_the_engine_supplies_is_not_asked_for(can: dict[str, Any]) -> None:
    supplied = {
        f"{owner}.{field['id']}"
        for _, owner, field in every_field(can)
        if field["written"] == BY_ENGINE
    }

    assert supplied == {
        "attach_curse.card",
        "claim_soul.card",
        "gain_soul.card",
        "gain_soul.earned_from",
    }

    card = a_card([{"id": "claim_soul", "fields": {"card": "the soul"}}])

    assert check_card(card), "a card file named a card it cannot name"


# ----------------------------------------------------------------------
# 4. A structure is not a string
# ----------------------------------------------------------------------


def test_a_structured_parameter_is_never_offered_as_a_box(
    can: dict[str, Any],
) -> None:
    deep = {
        f"{owner}.{field['id']}"
        for _, owner, field in every_field(can)
        if field["role"] == STRUCTURE
    }

    assert deep == {
        "promise.changes",
        "promise.when",
        "watch_for.conditions",
        "watch_for.effects",
    }

    for _, owner, field in every_field(can):
        if field["role"] == STRUCTURE:
            assert field["shown"] == "advanced", f"{owner}.{field['id']}"


def test_the_page_never_stores_half_written_structure_as_text() -> None:
    """
    The page parses what is typed and keeps nothing when it does not parse.
    Storing the text instead is how a structure becomes a sentence.
    """
    page = PAGE.read_text("utf-8")

    assert "function setStructure" in page
    assert "JSON.parse(written)" in page
    assert "delete at(path)[key];" in page


def test_a_structure_survives_as_a_structure() -> None:
    card = a_card(
        [
            {
                "id": "watch_for",
                "fields": {
                    "event": "damage_dealt",
                    "effects": [{"effect": "gain_coins", "amount": 1}],
                },
            }
        ]
    )

    assert one_effect(card)["effects"] == [
        {"effect": "gain_coins", "amount": 1}
    ]
    assert check_card(card) == []


def test_the_same_structure_written_as_a_string_is_refused() -> None:
    card = a_card(
        [
            {
                "id": "watch_for",
                "fields": {
                    "event": "damage_dealt",
                    "effects": "gain_coins",
                },
            }
        ]
    )

    assert check_card(card), "a structure passed as a sentence"


# ----------------------------------------------------------------------
# 5. A question another answer settles is not asked twice
# ----------------------------------------------------------------------


def test_every_dependency_reaches_the_page_with_what_settles_it(
    can: dict[str, Any],
) -> None:
    depends = {
        f"{owner}.{field['id']}": (field["unless"], tuple(field["unless_when"]))
        for _, owner, field in every_field(can)
        if field["unless"]
    }

    assert depends == {
        "add_counter.amount": ("clear", ()),
        "heal.amount": ("full", ()),
        "modify_event.factor": ("delta", ()),
        "move_cards.depth_from": ("position", ("bottom",)),
    }


def test_what_settles_a_dependency_is_a_parameter_beside_it(
    can: dict[str, Any],
) -> None:
    """
    The renderer looks the other parameter up among this one's siblings, so it
    has to be there, and it has to carry the default the effect would use.
    """
    for group in ("effects", "conditions", "targets"):
        for one in can[group]:
            beside = {field["id"]: field for field in one["fields"]}

            for field in one["fields"]:
                if not field["unless"]:
                    continue

                assert field["unless"] in beside, f"{one['id']}.{field['id']}"


def test_the_page_reads_the_dependency_rather_than_the_effect() -> None:
    page = PAGE.read_text("utf-8")

    assert "function moot(f, values, siblings)" in page
    assert "f.unless_when.length" in page
    assert 'other.role === "switch"' in page
    # What a box left empty means, which is the whole of why `move_cards` needs
    # its value named: bottom is the default, and a depth means nothing there.
    assert "other.otherwise" in page
    assert "disabled" in page


# ----------------------------------------------------------------------
# 6. A required answer looks required
# ----------------------------------------------------------------------


def test_what_the_engine_insists_on_reaches_the_page(
    can: dict[str, Any],
) -> None:
    needed = {
        f"{owner}.{field['id']}"
        for _, owner, field in every_field(can)
        if field["required"]
    }

    assert needed == {
        "add_counter.counter",
        "add_modifier.stat",
        "event_value.key",
        "modify_event.key",
        # Both structures. Their handlers have always raised without them, and
        # a form that called such a card ready was agreeing with nothing.
        "promise.changes",
        "promise.event",
        "watch_for.effects",
        "watch_for.event",
    }


def test_the_page_says_a_field_is_required_and_says_it_once() -> None:
    """
    The form saying so before the server does is worth having. Saying it twice
    is not: it used to shout NEEDED beside the label and then repeat the same
    fact as a sentence under the box, and neither notice added anything to the
    other.
    """
    page = PAGE.read_text("utf-8")
    script = page.split("<script>")[1]

    assert "function needed(f)" in script
    assert "f.required" in script

    # One notice. The old second one is gone rather than reworded.
    assert "This one has to be filled in." not in page


def test_an_empty_required_answer_is_still_refused() -> None:
    """
    The form saying so does not replace the engine saying so.
    """
    card = a_card([{"id": "add_counter", "fields": {"amount": 2}}])

    assert check_card(card), "a card with no counter name was accepted"


# ----------------------------------------------------------------------
# 7. A target keeps its own parameters
# ----------------------------------------------------------------------


def test_every_target_the_engine_has_is_still_offered(
    can: dict[str, Any],
) -> None:
    offered = {target["id"] for target in can["targets"]}

    assert {
        "current_monster",
        "group",
        "previous_result",
        "previous_target",
        "random_monster",
        "target_deck_card",
        "target_loot",
        "target_monster",
        "target_player",
        "target_player_or_monster",
        "target_shop_item",
        "target_soul",
        "target_stack_item",
        "target_treasure",
    } <= offered


def test_a_target_with_parameters_offers_them(can: dict[str, Any]) -> None:
    by_name = {target["id"]: target for target in can["targets"]}

    assert {field["id"] for field in by_name["target_stack_item"]["fields"]} >= {
        "kinds",
        "triggers",
        "chooser",
        "count",
    }
    assert {field["id"] for field in by_name["target_treasure"]["fields"]} >= {
        "of",
        "chooser",
    }


def test_a_target_that_names_a_group_keeps_naming_one() -> None:
    """
    "That player discards a loot card" — the choice is theirs, and `chooser`
    says so by naming a group rather than by describing one in words.
    """
    card = a_card(
        [
            {
                "id": "discard_loot",
                "fields": {"count": 1},
                "aim": "target_player",
                "aim_fields": {},
                "aim_groups": {"chooser": {"id": "another_player"}},
            }
        ]
    )
    chosen = card["abilities"][0]["targets"]

    assert chosen[0] == {"another_player": {"as": "chosen_1"}}
    assert chosen[1] == {"target_player": {"chooser": "chosen_1", "as": "chosen_2"}}
    assert check_card(card) == []


def test_a_target_that_hands_back_what_it_was_given_says_so(
    can: dict[str, Any],
) -> None:
    by_name = {target["id"]: target for target in can["targets"]}

    assert by_name["group"]["gives"] == "passthrough"
    assert by_name["group"]["after"]
    assert not by_name["target_player"]["after"]


# ----------------------------------------------------------------------
# 8. Two concepts, said separately
# ----------------------------------------------------------------------


def test_require_attack_can_say_who_owes_it_and_what_is_attacked() -> None:
    """
    The card this whole pass exists for.

    "That player must attack the monster twice this turn" is two different
    things — the player who owes the attack, and the monster owed one — and the
    old form had one place to put either. `who` became free text and the
    monster had nowhere to go at all.
    """
    card = a_card(
        [
            {
                "id": "require_attack",
                "fields": {"times": 2},
                "groups": {
                    "who": {
                        "id": "target_player",
                        "fields": {"exclude_controller": True},
                    }
                },
                "aim": "current_monster",
                "aim_fields": {},
            }
        ]
    )
    owed = one_effect(card)

    assert owed["who"] == {"player_of": "chosen_1"}
    assert owed["target"] == "chosen_2"
    assert card["abilities"][0]["targets"] == [
        {"target_player": {"exclude_controller": True, "as": "chosen_1"}},
        {"current_monster": {"as": "chosen_2"}},
    ]
    assert check_card(card) == []


def test_the_thing_it_names_that_is_not_on_the_table_is_still_a_choice(
    can: dict[str, Any],
) -> None:
    """
    `what` is the third concept — "attack the monster deck" — and it is a
    closed set of one, which is a selection and never was a text box.
    """
    by_name = {one["id"]: one for one in can["effects"]}
    fields = {
        field["id"]: field for field in by_name["require_attack"]["fields"]
    }

    assert fields["what"]["choices"] == ["monster_deck"]
    assert fields["what"]["role"] == "which"
    assert fields["who"]["shown"] == "group"
    assert fields["what"]["about"] != "what"


# ----------------------------------------------------------------------
# And the rule the whole pass rests on
# ----------------------------------------------------------------------


def test_the_page_names_no_effect_of_its_own() -> None:
    """
    The renderer must never grow `if (effect === "…")`. Every effect, condition
    and target the engine has is drawn by the same code from the same metadata,
    and the page's only names are the ones it needs to build a card at all.
    """
    page = PAGE.read_text("utf-8")
    can = catalogue()
    allowed = {"self", "group", "player", "value", "card", "kind", "kinds"}

    named = sorted(
        one["id"]
        for group in ("effects", "conditions", "targets")
        for one in can[group]
        if one["id"] not in allowed and f'"{one["id"]}"' in page
    )

    assert named == []


def test_every_parameter_still_arrives_somewhere(can: dict[str, Any]) -> None:
    """
    Nothing may be dropped for being hard to draw, and every parameter has to
    land in one of the places the page knows.
    """
    for _, owner, field in every_field(can):
        assert field["shown"] in (
            "form",
            "group",
            "advanced",
            "given",
            "spelling",
            "body",
            "nested",
        ), f"{owner}.{field['id']} has nowhere to go"


def test_an_answer_is_written_into_the_card_and_not_beside_it() -> None:
    """
    Every control writes through one path walk, so the walk has to start at the
    card. It used to start at the window, where a second object of the same
    name grew and quietly took every answer: the form looked like it worked and
    the card kept nothing but its name.

    The check is the two halves together — `state` is a binding rather than a
    property of anything, so a walk that starts at the window cannot reach it.
    """
    page = PAGE.read_text("utf-8")

    assert "let state = {}" in page, "state is not a window property"
    assert "??= {}), state)" in page, "the path walk does not start at the card"
    assert "reduce((o, k) => (o[k] ??= {}), window)" not in page


def test_a_card_too_unfinished_to_build_is_not_called_ready() -> None:
    page = PAGE.read_text("utf-8")

    assert "said.error" in page
    assert page.index("said.error") < page.index("This card is ready.")


# ----------------------------------------------------------------------
# Phase two: what the audit found after the renderer landed
# ----------------------------------------------------------------------


def test_a_card_the_engine_stops_on_is_reported_and_not_raised() -> None:
    """
    "Try it in a game" answers a question, and "the engine would not play it"
    is one of the answers. Letting the error out of the request handler killed
    the connection, and the page — whose fetch simply failed — showed nothing
    at all, so pressing the button did visibly nothing.
    """
    from fsme.lab.desk.author import said_by_the_engine
    from fsme.runtime.errors import AbilityResolutionError

    said = said_by_the_engine(
        AbilityResolutionError(
            "effect 'watch_for' failed: watch_for requires the effects it will run"
        )
    )

    assert said.startswith("The engine would not play this card:")
    assert "watch_for requires the effects it will run" in said


def test_a_structure_the_handler_insists_on_is_one_the_form_insists_on(
    can: dict[str, Any],
) -> None:
    """
    `promise` raises without its changes and `watch_for` without its effects.
    Neither said so, so a card that could not be played saved as ready.
    """
    needed = {
        f"{owner}.{field['id']}"
        for _, owner, field in every_field(can)
        if field["required"] and field["role"] == STRUCTURE
    }

    assert needed == {"promise.changes", "watch_for.effects"}


def test_the_two_cards_that_used_to_save_as_ready_are_refused() -> None:
    for effect in ("watch_for", "promise"):
        card = a_card([{"id": effect, "fields": {"event": "damage_dealt"}}])
        problems = check_card(card)

        assert problems, f"{effect} with no structure was accepted"
        assert "needs" in problems[0]


def test_an_answer_another_answer_settles_is_left_out_of_the_card() -> None:
    """
    A form that greys out a question and a card that answers it anyway are two
    different cards. The runtime reads one of the two values and the printed
    text says the other.
    """
    written = [
        ("heal", {"amount": 3, "full": True}, {"full": True}),
        (
            "add_counter",
            {"counter": "egg", "amount": 4, "clear": True},
            {"counter": "egg", "clear": True},
        ),
        (
            "modify_event",
            {"key": "amount", "factor": 2, "delta": 5},
            {"key": "amount", "delta": 5},
        ),
        # Nobody chose a position, so it is the bottom, and a depth counted
        # from the top means nothing there.
        ("move_cards", {"depth_from": 6}, {}),
        # And with a position that does read it, it survives.
        (
            "move_cards",
            {"depth_from": 6, "position": "top"},
            {"depth_from": 6, "position": "top"},
        ),
    ]

    for effect, filled, expected in written:
        card = a_card([{"id": effect, "fields": filled}])
        node = one_effect(card)

        node.pop("effect")

        assert node == expected, f"{effect} wrote {node}"


def test_the_page_keeps_the_greyed_out_answer_so_it_can_come_back() -> None:
    """
    Dropped from the card, not from the form: unticking the box has to give
    the number back rather than silently having thrown it away.
    """
    page = PAGE.read_text("utf-8")

    assert "function moot(" in page
    assert "delete at(path)[key]" not in page.split("function moot(")[1][:400]


def test_a_name_the_tool_writes_is_not_a_box(can: dict[str, Any]) -> None:
    """
    Every target is bound under a name so that later steps can point at it,
    and `_pick_out` chooses that name. Offering the box took an answer it was
    about to overwrite — on all forty-six targets.
    """
    ours = {
        f"{owner}.{field['id']}"
        for _, owner, field in every_field(can)
        if field["written"] == BY_BINDING
    }

    assert ours == {f"{target['id']}.as" for target in can["targets"]}

    for _, owner, field in every_field(can):
        if field["written"] == BY_BINDING:
            assert field["shown"] == "given", f"{owner}.{field['id']}"


def test_a_name_the_tool_writes_never_reaches_the_card_from_a_form() -> None:
    card = a_card(
        [
            {
                "id": "cancel_stack",
                "fields": {},
                "aim": "target_stack_item",
                "aim_fields": {"as": "mine", "kinds": ["loot"]},
            }
        ]
    )
    chosen = card["abilities"][0]["targets"][0]["target_stack_item"]

    assert chosen["as"].startswith("chosen_")
    assert chosen["kinds"] == ["loot"]
    assert check_card(card) == []


def test_a_target_that_needs_an_earlier_step_is_offered_apart_not_dropped(
    can: dict[str, Any],
) -> None:
    """
    "Destroy what you just damaged" points an effect at `previous_target`, and
    the engine resolves it like any other. Reading "hands back what it was
    given" as "cannot be aimed at" took three targets away.
    """
    by_name = {target["id"]: target for target in can["targets"]}

    for name in ("group", "previous_target", "previous_result", "most_common"):
        assert by_name[name]["aimable"], name
        assert by_name[name]["after"], name

    assert not by_name["target_player"]["after"]
    assert all(target["aimable"] for target in can["targets"])


def test_the_page_offers_them_under_their_own_heading() -> None:
    page = PAGE.read_text("utf-8")

    assert "what an earlier step chose" in page
    assert "t.after" in page


def test_aiming_at_what_an_earlier_step_chose_makes_a_card() -> None:
    card = a_card(
        [
            {"id": "deal_damage", "fields": {"amount": 1}, "aim": "target_monster"},
            {"id": "kill", "fields": {}, "aim": "previous_target"},
        ]
    )

    assert check_card(card) == []
    assert card["abilities"][0]["effects"][1]["target"] == "chosen_2"


def test_one_number_is_one_question(can: dict[str, Any]) -> None:
    """
    `player_has_coins` reads `amount`, then `count`, then `value`, and takes
    the first it finds. Asking for all three asks the same thing three times
    and says nothing about which answer wins.
    """
    spellings = {
        f"{owner}.{field['id']}": field["instead_of"]
        for _, owner, field in every_field(can)
        if field["instead_of"]
    }

    assert spellings == {
        f"player_has_{what}.{key}": "value"
        for what in ("coins", "loot", "souls", "treasure")
        for key in ("amount", "count")
    }

    for _, owner, field in every_field(can):
        if field["instead_of"]:
            assert field["shown"] == "spelling", f"{owner}.{field['id']}"


def test_every_spelling_names_a_parameter_beside_it(can: dict[str, Any]) -> None:
    for group in ("effects", "conditions", "targets"):
        for one in can[group]:
            beside = {field["id"] for field in one["fields"]}

            for field in one["fields"]:
                if field["instead_of"]:
                    assert field["instead_of"] in beside, one["id"]


def test_a_second_spelling_is_still_read_from_a_card_that_writes_it() -> None:
    """
    Not asked is not refused. Cards already written with `amount` still load,
    because the engine still reads them.
    """
    card = a_card(
        [
            {
                "id": "if",
                "fields": {
                    "if": [
                        {"id": "player_has_coins", "fields": {"amount": 3}}
                    ],
                    "then": [{"id": "gain_coins", "fields": {"amount": 1}}],
                },
            }
        ]
    )

    assert check_card(card) == []


def test_the_page_asks_a_second_spelling_nothing() -> None:
    page = PAGE.read_text("utf-8")

    assert 'f.shown === "spelling"' in page


def test_a_branch_with_nothing_in_it_is_refused() -> None:
    """
    A branch that runs and does nothing reads exactly like one that works.
    """
    empty = a_card(
        [
            {
                "id": "if",
                "fields": {
                    "if": [{"id": "player_alive", "fields": {}}],
                    "then": [],
                    "else": [],
                },
            }
        ]
    )
    problems = check_card(empty)

    assert problems
    assert "nothing to do" in problems[0]

    filled = a_card(
        [
            {
                "id": "if",
                "fields": {
                    "if": [{"id": "player_alive", "fields": {}}],
                    "then": [{"id": "gain_coins", "fields": {"amount": 1}}],
                },
            }
        ]
    )

    assert check_card(filled) == []


def test_where_a_control_node_keeps_its_body_is_the_interpreter_s_own_word() -> None:
    """
    One statement, beside the expanders that read it — not a list here that
    goes stale the first time a control node learns a second spelling.
    """
    from fsme.runtime.interpreter import CONTROL_BODIES, CONTROL_KEYS

    assert set(CONTROL_BODIES) == set(CONTROL_KEYS)

    for name, bodies in CONTROL_BODIES.items():
        for key in bodies:
            assert key in CONTROL_KEYS[name], f"{name}.{key}"


def test_every_target_and_condition_asks_in_words(can: dict[str, Any]) -> None:
    """
    An author meets a target's parameters the moment they aim anything. They
    used to meet `as`, `count`, `maximum`, `minimum`, `prompt` and `tag` — the
    engine's own names, with nothing said about any of them.
    """
    bare = [
        f"{owner}.{field['id']}"
        for group, owner, field in every_field(can)
        if group in ("targets", "conditions")
        and field["shown"] == "form"
        and field["about"] == field["id"].replace("_", " ")
    ]

    assert bare == []
