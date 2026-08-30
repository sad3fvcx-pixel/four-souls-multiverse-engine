"""
Reading a card back, and the contract that makes it safe to.

Everything FSME does runs one way: somebody describes a card, the builder
writes it, the runtime plays it. This is the return path, and it is a harder
problem than it looks, because reading is not the inverse of writing. A card
file may spell the same thing several ways; the builder writes one of them; and
a reader that is merely mostly right turns a working card into a *different*
working card, with no error anywhere.

So the contract is not "most cards open". It is:

- a card that is read comes back meaning the same thing;
- reading a card that has already been read changes nothing;
- a card that cannot be read faithfully is refused, and says which part.

The last of those is what keeps the first two honest. Nothing here is allowed
to approximate.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from fsme.api import load_content
from fsme.cards.types import PRINTED_NUMBERS, CardType
from fsme.lab.desk.author import (
    UnreadableCard,
    build_card,
    check_card,
    read_card,
)
from fsme.lab.desk.capabilities import catalogue

CONTENT = Path(__file__).resolve().parents[1] / "content"
WRITTEN_BY_THE_BUILDER = ("id", "schema_version")


@pytest.fixture(scope="module")
def can() -> dict[str, Any]:
    return catalogue()


@pytest.fixture(scope="module")
def written() -> list[dict[str, Any]]:
    """
    Every shipped card that has rules, exactly as it is written on disk.

    From the files rather than from `load_content`, because the file is what a
    reader is given and the spellings are what make this hard.
    """
    found: list[dict[str, Any]] = []

    for path in sorted(CONTENT.rglob("*.json")):
        body = json.loads(path.read_text("utf-8"))

        for card in body.get("cards", ()) if isinstance(body, dict) else ():
            if card.get("abilities") or card.get("statics"):
                found.append(card)

    return found


@pytest.fixture(scope="module")
def walked(written: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Every shipped card, read and written back — once.

    Reading and building a card is tens of milliseconds and there are hundreds
    of them, so the walk happens here rather than once per test.
    """
    done: list[dict[str, Any]] = []

    for card in written:
        state, why = read(card)

        if state is None:
            done.append({"card": card, "state": None, "why": why})

            continue

        once = build_card(state)
        done.append(
            {
                "card": card,
                "state": state,
                "why": "",
                "once": once,
                "again": read_card(once),
                "twice": build_card(read_card(once)),
            }
        )

    return done


def bare(card: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in card.items() if k not in WRITTEN_BY_THE_BUILDER}


def read(card: Mapping[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """
    A card read back, or the reason it was not.
    """
    try:
        return read_card(card), ""
    except UnreadableCard as why:
        return None, str(why)


# ----------------------------------------------------------------------
# 1. The contract
# ----------------------------------------------------------------------


def test_a_card_that_is_read_comes_back_meaning_the_same_thing(
    walked: list[dict[str, Any]],
) -> None:
    """
    Not byte for byte — reading canonicalises, and it is allowed to.

    Whether it still says the same thing is asked of the reader, because the
    reader is what turns every spelling into one: two cards mean the same
    exactly when it reads them the same way.
    """
    changed = [
        one["card"].get("id")
        for one in walked
        if one["state"] is not None and one["again"] != one["state"]
    ]

    assert changed == [], changed[:10]


def test_reading_a_card_that_was_read_changes_nothing(
    walked: list[dict[str, Any]],
) -> None:
    """
    Idempotence, byte for byte.

    The first save may rewrite the file — bindings renamed, short spellings
    written long. The second must not, or opening a card twice is a card that
    drifts. This is the property that catches a reader which grows a wrapper
    on every pass.
    """
    unstable = [
        one["card"].get("id")
        for one in walked
        if one["state"] is not None
        and json.dumps(one["once"], sort_keys=True)
        != json.dumps(one["twice"], sort_keys=True)
    ]

    assert unstable == [], unstable[:10]


def test_a_card_that_is_read_still_passes_the_checker(
    walked: list[dict[str, Any]],
) -> None:
    """
    Reading and writing a card must not make one the engine would refuse.
    """
    refused = {
        one["card"].get("id"): check_card(one["once"])[0]
        for one in walked
        if one["state"] is not None and check_card(one["once"])
    }

    assert refused == {}, dict(list(refused.items())[:5])


def test_every_card_is_either_read_or_refused_by_name(
    walked: list[dict[str, Any]],
) -> None:
    """
    No third outcome. A card is opened, or it is refused with the reason.

    The share that opens is expected to move as the engine grows; that it is
    never a silent half-open is not.
    """
    silent = [
        one["card"].get("id")
        for one in walked
        if one["state"] is None and not one["why"].strip()
    ]

    assert silent == [], silent

    opened = sum(1 for one in walked if one["state"] is not None)

    # Measured at 245 of 352 when this was written. The floor guards against a
    # change that quietly stops reading most cards; it is not a target.
    assert opened >= 240, f"only {opened} of {len(walked)} cards can be read"


# ----------------------------------------------------------------------
# 2. The two cards that used to change meaning
# ----------------------------------------------------------------------


def one(written: list[dict[str, Any]], ends_with: str) -> dict[str, Any]:
    return next(card for card in written if str(card.get("id", "")).endswith(ends_with))


def test_a_card_that_names_a_player_keeps_naming_that_player(
    written: list[dict[str, Any]],
) -> None:
    """
    `jawbone` steals three cents *from a chosen player*.

    It writes that as `{"player_of": "victim"}` on a parameter nothing
    declared as taking a player, so a reader saw a whole number, dropped the
    naming, and after one more pass the card stole from its own controller
    instead. Nothing raised. This is that card.
    """
    card = one(written, "jawbone")
    state = read_card(card)
    once = build_card(state)

    assert read_card(once) == state
    assert json.dumps(once, sort_keys=True) == json.dumps(
        build_card(read_card(once)), sort_keys=True
    )

    step = once["abilities"][0]["effects"][0]
    pays, hit = step["source_player"], step["target"]

    assert isinstance(pays, Mapping), pays
    assert pays["player_of"] != hit, "the payer and the target became one player"


def test_a_condition_holding_conditions_does_not_grow(
    written: list[dict[str, Any]],
) -> None:
    """
    `stoney` dies when another monster does — "not the source of the event".

    The short spelling of a nesting condition *is* its list, so a body written
    under it reads as one more condition and the card gained a wrapper on
    every pass. It is written the long way now.
    """
    card = one(written, "stoney")
    once = build_card(read_card(card))
    twice = build_card(read_card(once))

    assert json.dumps(once, sort_keys=True) == json.dumps(twice, sort_keys=True)
    assert check_card(once) == []


def test_a_nested_condition_can_be_built_at_all() -> None:
    """
    The bug underneath `stoney`, reached the way the editor reaches it.

    Before this, a condition holding conditions was written with the page's own
    working data inside it and the checker said "unknown condition 'of'".
    """
    made = build_card(
        {
            "set": "demo",
            "card": {
                "fields": {
                    "name": "Nested",
                    "type": "loot",
                    "abilities": [
                        {
                            "fields": {
                                "trigger": "on_play",
                                "conditions": [
                                    {
                                        "id": "not",
                                        "fields": {
                                            "of": [
                                                {
                                                    "id": "is_event_source",
                                                    "fields": {},
                                                    "groups": {},
                                                }
                                            ]
                                        },
                                        "groups": {},
                                    }
                                ],
                                "effects": [
                                    {
                                        "id": "gain_coins",
                                        "fields": {"amount": 1},
                                        "groups": {},
                                    }
                                ],
                            },
                            "groups": {},
                        }
                    ],
                },
                "groups": {},
            },
        }
    )

    assert check_card(made) == []
    assert made["abilities"][0]["conditions"] == [
        {"condition": "not", "of": ["is_event_source"]}
    ]


# ----------------------------------------------------------------------
# 3. A character keeps what is printed on it
# ----------------------------------------------------------------------


def test_a_character_keeps_its_attack() -> None:
    """
    The number the builder used to throw away.

    `PRINTED_NUMBERS` said a character carries hit points and nothing else, so
    the form greyed the question out and the builder left the answer off the
    card. Nobody noticed because nothing could open a card and save it again.
    """
    made = build_card(
        {
            "set": "demo",
            "card": {
                "fields": {
                    "name": "Isaac",
                    "type": "character",
                    "health": 2,
                    "attack": 1,
                    "abilities": [],
                },
                "groups": {},
            },
        }
    )

    assert made["attack"] == 1
    assert made["health"] == 2


def test_what_each_kind_of_card_carries_is_what_it_says_it_carries() -> None:
    """
    The claim `PRINTED_NUMBERS` makes, checked against the content.

    A number a kind of card actually carries and does not declare is a number
    the form hides and the builder discards — which is exactly what happened to
    a character's attack, on 93 of the 97 shipped ones. Only the nullable
    numbers count: a field with a default is never absent and says nothing.
    """
    library = load_content(CONTENT)
    nullable = ("health", "attack", "roll", "cost")
    carried: dict[CardType, dict[str, int]] = {}
    total: dict[CardType, int] = {}

    for card in library.definitions():
        total[card.type] = total.get(card.type, 0) + 1
        held = carried.setdefault(card.type, {})

        for number in nullable:
            if getattr(card, number, None) is not None:
                held[number] = held.get(number, 0) + 1

    undeclared = []

    for kind, said in PRINTED_NUMBERS.items():
        for number, seen in carried.get(kind, {}).items():
            if number not in said:
                undeclared.append(f"{kind}: {number} on {seen} of {total[kind]}")

    assert undeclared == [], undeclared


def test_every_shipped_character_survives_being_read(
    walked: list[dict[str, Any]],
) -> None:
    """
    Over the cards themselves, not one made up for the test.
    """
    characters = [
        one
        for one in walked
        if one["card"].get("type") == "character"
        and one["card"].get("attack") is not None
        and one["state"] is not None
    ]

    assert characters, "no shipped character with an attack was read at all"

    lost = [
        one["card"].get("id")
        for one in characters
        if one["once"].get("attack") != one["card"]["attack"]
    ]

    assert lost == [], lost[:10]


# ----------------------------------------------------------------------
# 4. The metadata this needed
# ----------------------------------------------------------------------


def test_the_short_spelling_says_which_parameter_it_fills(
    can: dict[str, Any],
) -> None:
    """
    `{"gain_coins": 3}` is three of something, and only the effect knows of
    what. It knew all along and did not say it out loud.
    """
    by_name = {one["id"]: one["primary"] for one in can["effects"]}

    assert by_name["gain_coins"] == "amount"
    assert by_name["draw_loot"] == "count"

    from fsme.effects import builtin_registry

    registry = builtin_registry()
    wrong = [
        name
        for name in registry.names()
        if (registry.spec(name).primary or "") != by_name.get(name, "")
    ]

    assert wrong == [], wrong


def test_a_parameter_that_takes_a_player_says_so(can: dict[str, Any]) -> None:
    """
    `transfer_coins` resolves `source_player` with `state.player(...)` — it is
    a seat, not a number — and declared nothing. So a form offered a box for a
    number, the checker had no name to check, and reading a card back could not
    tell that `{"player_of": "victim"}` was a player at all.
    """
    effect = next(one for one in can["effects"] if one["id"] == "transfer_coins")
    pays = next(f for f in effect["fields"] if f["id"] == "source_player")

    assert pays["picks"] == "players"
    assert pays["written"] == "player_of"


def test_where_a_short_spelling_lands_is_named_once() -> None:
    """
    The key `normalise` hands a short-written value back under. Anything
    reading a card looks for the same one, so it is a constant and not a
    string written twice.
    """
    from fsme.runtime.interpreter import SHORTHAND, normalise

    _, params, _ = normalise({"gain_coins": 3})

    assert SHORTHAND in params


# ----------------------------------------------------------------------
# 5. Refusals say what stopped them
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "written_as, expect",
    [
        ({"effect": "sequence"}, "in full"),
        ({"effect": "gain_coins", "target": "nobody_binds_this"}, "binds"),
        ({"effect": "roll_dice", "store": "first"}, "later step"),
    ],
)
def test_a_step_it_cannot_read_is_named_not_guessed(
    written_as: dict[str, Any], expect: str
) -> None:
    card = {
        "id": "demo-x",
        "name": "X",
        "type": "loot",
        "expansion": "demo",
        "abilities": [{"trigger": "on_play", "effects": [written_as]}],
    }

    with pytest.raises(UnreadableCard) as refused:
        read_card(card)

    assert expect in str(refused.value)


def test_a_card_holding_something_undescribed_is_refused() -> None:
    card = {
        "id": "demo-x",
        "name": "X",
        "type": "loot",
        "expansion": "demo",
        "wingspan": 3,
        "abilities": [{"trigger": "on_play", "effects": [{"gain_coins": 1}]}],
    }

    with pytest.raises(UnreadableCard) as refused:
        read_card(card)

    assert "wingspan" in str(refused.value)


def test_a_step_that_picks_for_itself_says_why_it_is_refused(
    walked: list[dict[str, Any]],
) -> None:
    """
    Not a shrug. Folding a step's own choice up to the ability would let a
    later step reuse it, and two separate choices of the same thing become
    one — which is a card doing something different.
    """
    said = [
        row["why"] for row in walked if "picks something out for itself" in row["why"]
    ]

    assert said, "no shipped card is refused for picking something out itself"
    assert "become one" in said[0]


# ----------------------------------------------------------------------
# 6. Opening one, the way a person does
# ----------------------------------------------------------------------

PAGE = CONTENT.parent / "src/fsme/lab/desk/static/author.html"


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    A set of the author's own, so nothing here touches a real one.
    """
    where = tmp_path / "FSME"
    monkeypatch.setenv("FSME_HOME", str(where))

    return where


def a_saved_card(fields: dict[str, Any]) -> tuple[str, str]:
    """
    One card in a set of its own, saved the way the page saves it.
    """
    from fsme.lab.desk.author import make_set, save_card

    made = make_set("Looking")
    saved = save_card({"set": made["id"], "card": {"fields": fields, "groups": {}}})

    assert saved["saved"], saved["problems"]

    return made["id"], saved["card"]["id"]


A_TWO_STEP_CARD = {
    "name": "Thumbtack",
    "type": "loot",
    "abilities": [
        {
            "fields": {
                "trigger": "on_play",
                "effects": [
                    {
                        "id": "deal_damage",
                        "fields": {"amount": 2},
                        "groups": {},
                        "aim": "target_player",
                        "aim_fields": {},
                        "aim_groups": {},
                    },
                    {
                        "id": "gain_coins",
                        "fields": {"amount": 3},
                        "groups": {},
                        "aim": "controller",
                        "aim_fields": {},
                        "aim_groups": {},
                    },
                ],
            },
            "groups": {},
        }
    ],
}


def test_a_card_can_be_found_by_name_and_opened_by_identifier(
    workspace: Path,
) -> None:
    """
    The list a person reads carries both, because they are different jobs.
    """
    from fsme.lab.desk.author import sets

    set_id, card_id = a_saved_card(A_TWO_STEP_CARD)
    listed = sets()[0]["cards"]

    assert [one["name"] for one in listed] == ["Thumbtack"]
    assert [one["id"] for one in listed] == [card_id]
    assert set_id


def test_opening_a_card_gives_back_what_was_filled_in(workspace: Path) -> None:
    """
    A card is opened as the thing somebody filled in to make it — the same
    author state, so whatever draws a card being made draws this.
    """
    from fsme.lab.desk.author import open_card

    set_id, card_id = a_saved_card(A_TWO_STEP_CARD)
    opened = open_card(set_id, card_id)["card"]

    assert opened["fields"]["name"] == "Thumbtack"
    assert opened["fields"]["type"] == "loot"

    steps = opened["fields"]["abilities"][0]["fields"]["effects"]

    assert [one["id"] for one in steps] == ["deal_damage", "gain_coins"]
    assert steps[0]["fields"]["amount"] == 2
    assert steps[0]["aim"] == "target_player"
    assert steps[1]["aim"] == "controller"


def test_opening_a_card_does_not_change_it(workspace: Path) -> None:
    """
    Read only, and checked on the file rather than on a promise.
    """
    from fsme.lab.desk.author import open_card, sets

    set_id, card_id = a_saved_card(A_TWO_STEP_CARD)
    where = Path(sets()[0]["where"]) / "cards" / f"{card_id}.json"
    before = where.read_text("utf-8")

    for _ in range(3):
        open_card(set_id, card_id)

    assert where.read_text("utf-8") == before


def test_what_is_opened_rebuilds_the_card_it_came_from(workspace: Path) -> None:
    """
    The round-trip contract, reached the way a person reaches it.
    """
    from fsme.lab.desk.author import open_card, sets

    set_id, card_id = a_saved_card(A_TWO_STEP_CARD)
    where = Path(sets()[0]["where"]) / "cards" / f"{card_id}.json"
    written = json.loads(where.read_text("utf-8"))["cards"][0]
    opened = open_card(set_id, card_id)

    assert build_card(opened) == written


def test_a_card_it_cannot_read_is_refused_with_the_reason(
    workspace: Path,
) -> None:
    """
    Not opened half way. A control node is the commonest reason by far, so it
    is the one checked here.
    """
    from fsme.lab.desk.author import make_set, sets

    made = make_set("Hard")
    where = Path(sets()[0]["where"]) / "cards" / "hard-loot-branching.json"
    where.write_text(
        json.dumps(
            {
                "cards": [
                    {
                        "id": "hard-loot-branching",
                        "name": "Branching",
                        "type": "loot",
                        "expansion": made["id"],
                        "abilities": [
                            {
                                "trigger": "on_play",
                                "effects": [
                                    {
                                        "if": ["dice_equals"],
                                        "then": [{"gain_coins": 1}],
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    from fsme.lab.desk.author import open_card

    with pytest.raises(UnreadableCard) as refused:
        open_card(made["id"], "hard-loot-branching")

    said = str(refused.value)

    assert "'if'" in said
    assert "in full" in said


def test_asking_for_a_card_that_is_not_there_says_so(workspace: Path) -> None:
    from fsme.lab.desk.author import AuthorError, open_card

    set_id, _ = a_saved_card(A_TWO_STEP_CARD)

    with pytest.raises(AuthorError) as refused:
        open_card(set_id, "no-such-card")

    assert "no-such-card" in str(refused.value)


# ----------------------------------------------------------------------
# 7. The screen that shows it
# ----------------------------------------------------------------------


def script() -> str:
    return PAGE.read_text("utf-8").split("<script>")[1]


def body_of(name: str) -> str:
    """
    One function out of the page, from its opening line to the `}` that ends
    it. Sliced on the closing brace at the start of a line, because the next
    thing after a function is not always another `function`.
    """
    said = script()
    start = said.index(f"function {name}(")
    end = said.index("\n}\n", start)

    return said[start:end]


def test_the_page_can_open_a_card_and_shows_it_read_only() -> None:
    """
    Looking is its own screen, and it draws no control a card is typed into.
    """
    said = script()

    assert "function openCard(" in said
    assert "function viewing(" in said
    assert '"/api/cards/open"' in said

    looking = body_of("viewing") + body_of("readingHtml")

    for typed in ("<input", "<select", "<textarea", "setField", "setAim"):
        assert typed not in looking, f"the reading screen draws {typed}"


def test_the_page_reads_a_card_back_with_the_words_it_already_had() -> None:
    """
    The same `saidAs` a walk reads its own actions back with, and no effect
    named anywhere.
    """
    said = script()

    assert "saidAs(" in body_of("readingHtml")

    from fsme.lab.desk.capabilities import catalogue

    named = [one["id"] for one in catalogue()["effects"] if f'"{one["id"]}"' in said]

    assert named == [], named


def test_the_page_refuses_a_card_rather_than_showing_half_of_it() -> None:
    said = script()

    assert "function cannotOpen(" in said
    assert "said.unreadable" in said

    # It says the reason it was given rather than one of its own.
    assert "esc(why)" in body_of("cannotOpen")


# ----------------------------------------------------------------------
# 8. A card that changes a number rather than doing something
# ----------------------------------------------------------------------


def a_shipped_card(ends_with: str) -> dict[str, Any]:
    for path in sorted(CONTENT.rglob("*.json")):
        body = json.loads(path.read_text("utf-8"))

        for card in body.get("cards", ()) if isinstance(body, dict) else ():
            if str(card.get("id", "")).endswith(ends_with):
                return card

    raise AssertionError(f"no shipped card ending in {ends_with!r}")


def test_a_card_whose_rules_are_statics_is_read(workspace: Path) -> None:
    """
    `breakfast` does nothing and gives its holder a hit point.

    A part of a card need not do anything, and one that does not is still the
    whole card — most of a passive item is exactly this.
    """
    from fsme.lab.desk.author import make_set, open_card, save_card, sets

    breakfast = a_shipped_card("base_game-breakfast")
    made = make_set("Statics")
    saved = save_card(read_card(breakfast, set_id=made["id"]))

    assert saved["saved"], saved["problems"]

    opened = open_card(made["id"], saved["card"]["id"])["card"]
    statics = opened["fields"]["statics"]

    assert opened["fields"]["abilities"] == []
    assert len(statics) == 1
    assert statics[0]["fields"]["stat"] == "max_hp"
    assert statics[0]["fields"]["amount"] == 1
    assert sets()


def test_a_card_with_both_keeps_both(workspace: Path) -> None:
    """
    `curved_horn` does something when played *and* changes a number after.
    """
    from fsme.lab.desk.author import make_set, open_card, save_card

    horn = a_shipped_card("base_game-curved_horn")
    made = make_set("Both")
    saved = save_card(read_card(horn, set_id=made["id"]))

    assert saved["saved"], saved["problems"]

    opened = open_card(made["id"], saved["card"]["id"])["card"]

    assert opened["fields"]["abilities"], "the ability was dropped"
    assert opened["fields"]["statics"], "the static was dropped"
    assert opened["fields"]["statics"][0]["fields"]["stat"] == "attack"
    # And a condition inside the static came back as a condition, not as text.
    inside = opened["fields"]["statics"][0]["fields"]["conditions"]

    assert [one["id"] for one in inside] == ["first_attack_roll"]


def test_every_shipped_card_with_statics_reads_or_says_why() -> None:
    """
    Over all of them, not the two picked out above.
    """
    holding = [
        card
        for path in sorted(CONTENT.rglob("*.json"))
        for card in (
            json.loads(path.read_text("utf-8")).get("cards", ())
            if isinstance(json.loads(path.read_text("utf-8")), dict)
            else ()
        )
        if card.get("statics")
    ]

    assert len(holding) > 20, len(holding)

    silent = []
    opened = 0

    for card in holding:
        state, why = read(card)

        if state is not None:
            opened += 1
        elif not why.strip():
            silent.append(card.get("id"))

    assert silent == [], silent
    # Measured at 29 of 32 when this was written; the three refused are
    # refused for reasons that have nothing to do with statics.
    assert opened >= 25, f"only {opened} of {len(holding)} read"


def test_a_part_that_does_nothing_is_not_shown_as_a_dash() -> None:
    """
    A static has no things that happen, and the reading screen used to print a
    dash where they would go — an answer to a question nobody asked of it.
    """
    reading = body_of("readingHtml")

    assert "&mdash;" not in reading
    assert "saidOf(part)" in reading

    # The words a part says about itself are its own first questions, whichever
    # kind of part it is, so there is one function and not one per kind.
    about = body_of("saidOf")

    assert 'f.asked === "first"' in about
    assert "ability" not in about and "static" not in about


# ----------------------------------------------------------------------
# 9. Changing one that exists, without keeping it
# ----------------------------------------------------------------------


def test_a_card_opened_is_already_what_the_constructor_would_build(
    workspace: Path,
) -> None:
    """
    The whole reason there is nothing to convert.

    What comes back from opening a card is the same author state a card being
    made carries, so building it again gives the card back unchanged.
    """
    from fsme.lab.desk.author import open_card, sets

    set_id, card_id = a_saved_card(A_TWO_STEP_CARD)
    opened = open_card(set_id, card_id)
    where = Path(sets()[0]["where"]) / "cards" / f"{card_id}.json"

    assert build_card(opened) == json.loads(where.read_text("utf-8"))["cards"][0]


def test_changing_one_value_changes_one_thing(workspace: Path) -> None:
    """
    Two damage becomes three, and nothing else about the card moves.
    """
    from fsme.lab.desk.author import open_card

    set_id, card_id = a_saved_card(A_TWO_STEP_CARD)
    opened = open_card(set_id, card_id)
    before = build_card(opened)

    steps = opened["card"]["fields"]["abilities"][0]["fields"]["effects"]
    steps[0]["fields"]["amount"] = 3

    after = build_card(opened)
    moved = [
        key
        for key in set(before) | set(after)
        if json.dumps(before.get(key), sort_keys=True)
        != json.dumps(after.get(key), sort_keys=True)
    ]

    assert moved == ["abilities"], moved

    was = before["abilities"][0]["effects"]
    now = after["abilities"][0]["effects"]

    assert was[0]["amount"] == 2 and now[0]["amount"] == 3
    assert was[1] == now[1], "the other action moved"
    assert (
        before["abilities"][0]["targets"] == after["abilities"][0]["targets"]
    ), "what it picks out moved"


def test_changing_a_card_does_not_write_it(workspace: Path) -> None:
    """
    Opening, changing and building leaves the file exactly as it was. Keeping
    a change is a later step, and until it exists nothing may write.
    """
    from fsme.lab.desk.author import open_card, sets

    set_id, card_id = a_saved_card(A_TWO_STEP_CARD)
    where = Path(sets()[0]["where"]) / "cards" / f"{card_id}.json"
    before = where.read_text("utf-8")

    opened = open_card(set_id, card_id)
    opened["card"]["fields"]["abilities"][0]["fields"]["effects"][0]["fields"][
        "amount"
    ] = 99
    build_card(opened)
    check_card(build_card(opened))

    assert where.read_text("utf-8") == before


def test_a_changed_card_is_still_a_card_the_engine_takes(workspace: Path) -> None:
    from fsme.lab.desk.author import open_card

    set_id, card_id = a_saved_card(A_TWO_STEP_CARD)
    opened = open_card(set_id, card_id)
    opened["card"]["fields"]["abilities"][0]["fields"]["effects"][0]["fields"][
        "amount"
    ] = 3

    assert check_card(build_card(opened)) == []


# ----------------------------------------------------------------------
# 10. The screens
# ----------------------------------------------------------------------


def test_the_walk_can_be_pointed_at_a_card_that_exists() -> None:
    """
    Nothing is converted: the walk is pointed at the parts the card has, and
    the list it walks is found by what it is a list of.
    """
    said = script()

    assert "function startFrom(" in said
    assert "function partsOf(" in said

    # Which lists hold parts, and where a part keeps what it does, are asked of
    # the shapes rather than named.
    where = body_of("partsOf") + body_of("doesIn")

    assert 'f.a_list_of === "step"' in where
    assert "abilities" not in where and "statics" not in where

    # And it does not build a card of its own — it uses the one in hand.
    made = body_of("startFrom")

    assert "state.card.fields = " not in made
    assert "openPart(" in made


def test_a_card_the_walk_cannot_show_whole_is_not_opened_for_changing() -> None:
    """
    It shows one part and what that part does. A card with more than one, or
    doing something the questions do not offer, would be shown half.
    """
    said = script()

    assert "function walkable(" in said

    rule = body_of("walkable")

    # How many parts a card has is no longer a reason to refuse it — the walk
    # asks about each in turn. What it still refuses is an action it does not
    # offer, which is the rule it already applies when making a card.
    assert "finishable(e)" in rule
    assert "length !== 1" not in rule, "the walk still refuses a card by its shape"
    # The reading screen only offers the way in when the rule allows it.
    assert "walkable()" in body_of("viewing")
    assert "startFrom()" in body_of("viewing")


def test_a_card_that_was_opened_can_be_kept() -> None:
    """
    Both a card being made and a card that was opened are offered keeping —
    said in their own words, because writing a new card and writing over one
    that is already there are not the same thing to the person doing it.
    """
    finishing = body_of("done")

    assert "save()" in finishing, "the finishing screen cannot keep a card"

    # One button either way, because it does the same thing either way. What
    # differs is what it is called, because writing a new card and writing
    # over one that is already there are not the same thing to a person.
    assert "Keep this change" in finishing
    assert "Save this card" in finishing


def test_keeping_a_card_that_was_opened_says_what_it_will_do() -> None:
    """
    A file somebody wrote by hand comes back written the one way this writes
    cards. That is a thing to say before it happens, not after.
    """
    finishing = body_of("done")

    assert "editing ?" in finishing or "${editing" in finishing
    assert "written out again" in finishing, "nobody is told the file is rewritten"


def test_an_opened_card_keeps_the_identity_it_was_read_under() -> None:
    """
    The page carries back what the open gave it, untouched. Nothing on the
    page makes it, reads it, or decides anything from it.
    """
    opening = body_of("openCard")

    assert "said.opened" in opening, "the page drops which card it opened"


def test_a_card_being_made_carries_no_identity() -> None:
    """
    Until it has been kept once there is no file behind it, so there is
    nothing to carry and nothing that could point at somebody else's card.
    """
    starting = body_of("startCard")

    assert "opened" not in starting


def test_keeping_a_card_carries_what_it_became() -> None:
    """
    A save makes the file say something new, so the page takes back what the
    card is now — otherwise keeping it twice would be refused the second time
    for a change the person made themselves.
    """
    keeping = body_of("save")

    assert "said.opened" in keeping, "the page keeps a stale fingerprint"


def test_a_refused_keeping_is_not_reported_as_saved() -> None:
    """
    A card refused because its file changed has not been saved, and the
    reason belongs on the screen rather than a cheerful sentence.
    """
    keeping = body_of("save")

    assert "said.saved" in keeping
    assert "said.changed" in keeping, "the page cannot tell a refusal from a fault"


# ----------------------------------------------------------------------
# 11. The contract for changing a card that has several parts
# ----------------------------------------------------------------------
#
# Written before the screens that would do it, and at the level of the card
# rather than the page: editing is mutating author state, so whether a card
# with several parts *can* be edited is a question about the pipeline, and it
# can be answered now.


@lru_cache(maxsize=1)
def _part_lists() -> tuple[str, ...]:
    """
    The card's own lists of parts, in the order it declares them.

    Found by asking the shapes rather than by name, and asked once: building
    the catalogue is milliseconds and there are hundreds of cards.
    """
    can = catalogue()
    known = {s["id"] for sec in ("abilities", "statics") for s in can[sec]}
    card = next(s for s in can["cards"] if s["id"] == "card")

    return tuple(f["id"] for f in card["fields"] if f["a_list_of"] in known)


def parts_of(state: Mapping[str, Any]) -> list[tuple[str, int, dict[str, Any]]]:
    """
    Every part of a card, in the order the card declares its lists.
    """
    return [
        (where, index, part)
        for where in _part_lists()
        for index, part in enumerate(state["card"]["fields"].get(where) or ())
    ]


def a_number_in(part: Mapping[str, Any]) -> str:
    """
    A field of this part holding a whole number somebody could change.
    """
    for key, value in part["fields"].items():
        if isinstance(value, bool):
            continue

        if isinstance(value, int):
            return key

    return ""


@pytest.fixture(scope="module")
def many(walked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Every shipped card that reads and has more than one part.

    Off the walk that already read them all, rather than reading them again.
    """
    return [
        {"card": one["card"], "state": one["state"]}
        for one in walked
        if one["state"] is not None and len(parts_of(one["state"])) > 1
    ]


def test_there_are_cards_with_several_parts_to_talk_about(
    many: list[dict[str, Any]],
) -> None:
    assert len(many) > 20, len(many)


def test_a_card_with_several_parts_rebuilds_unchanged(
    many: list[dict[str, Any]],
) -> None:
    """
    Reading and writing one back leaves it as it was — the same contract as
    for a card with one part, checked where it is likelier to break.
    """
    changed = [
        one["card"].get("id")
        for one in many
        if read_card(build_card(one["state"])) != one["state"]
    ]

    assert changed == [], changed[:10]


def test_changing_one_part_leaves_the_others_alone(
    many: list[dict[str, Any]],
) -> None:
    """
    The invariant multi-part editing rests on.

    A card is a list of parts, and changing a number inside one of them must
    move that part and nothing else — not the part beside it, and not what
    either of them picks out.
    """
    spread = []

    for one in many:
        before = build_card(one["state"])
        parts = parts_of(one["state"])

        for where, index, part in parts:
            key = a_number_in(part)

            if not key:
                continue

            was = part["fields"][key]
            part["fields"][key] = was + 7
            after = build_card(one["state"])
            part["fields"][key] = was

            for other, at_index, _ in parts:
                if (other, at_index) == (where, index):
                    continue

                mine = json.dumps(after[other][at_index], sort_keys=True)
                theirs = json.dumps(before[other][at_index], sort_keys=True)

                if mine != theirs:
                    spread.append(
                        f"{one['card'].get('id')}: changing {where}[{index}].{key}"
                        f" moved {other}[{at_index}]"
                    )

    assert spread == [], spread[:8]


def test_changing_one_part_does_change_that_part(
    many: list[dict[str, Any]],
) -> None:
    """
    And the change is not quietly dropped, which the test above would not
    notice on its own.
    """
    stuck = []

    for one in many:
        before = build_card(one["state"])

        for where, index, part in parts_of(one["state"]):
            key = a_number_in(part)

            if not key:
                continue

            was = part["fields"][key]
            part["fields"][key] = was + 7
            after = build_card(one["state"])
            part["fields"][key] = was

            if json.dumps(after[where][index], sort_keys=True) == json.dumps(
                before[where][index], sort_keys=True
            ):
                stuck.append(f"{one['card'].get('id')}: {where}[{index}].{key}")

    assert stuck == [], stuck[:8]


def test_a_card_with_several_parts_still_passes_the_checker_after_a_change(
    many: list[dict[str, Any]],
) -> None:
    refused = {}

    for one in many[:40]:
        for where, index, part in parts_of(one["state"]):
            key = a_number_in(part)

            if not key:
                continue

            was = part["fields"][key]
            part["fields"][key] = was + 1
            said = check_card(build_card(one["state"]))
            part["fields"][key] = was

            if said:
                refused[f"{one['card'].get('id')} {where}[{index}].{key}"] = said[0]

    assert refused == {}, dict(list(refused.items())[:5])


def test_the_order_of_the_parts_survives(many: list[dict[str, Any]]) -> None:
    """
    A card's second ability is its second ability after being read.
    """
    wrong = []

    for one in many:
        built = build_card(one["state"])

        for where, index, part in parts_of(one["state"]):
            written = built[where][index]

            for key, value in part["fields"].items():
                if isinstance(value, (int, str)) and not isinstance(value, bool):
                    if key in written and written[key] != value:
                        wrong.append(f"{one['card'].get('id')} {where}[{index}].{key}")

    assert wrong == [], wrong[:8]


# ----------------------------------------------------------------------
# 12. Editing a card that has several parts
# ----------------------------------------------------------------------


A_CARD_WITH_BOTH = {
    "name": "Curved Thing",
    "type": "treasure",
    "abilities": [
        {
            "fields": {
                "trigger": "on_activate",
                "effects": [
                    {
                        "id": "gain_coins",
                        "fields": {"amount": 1},
                        "groups": {},
                        "aim": "controller",
                        "aim_fields": {},
                        "aim_groups": {},
                    }
                ],
            },
            "groups": {},
        }
    ],
    "statics": [
        {
            "fields": {"stat": "attack", "amount": 1, "scope": "controller"},
            "groups": {},
        }
    ],
}


def test_a_card_with_an_ability_and_a_static_opens(workspace: Path) -> None:
    """
    Both parts come back, each as the node it is.
    """
    from fsme.lab.desk.author import open_card

    set_id, card_id = a_saved_card(A_CARD_WITH_BOTH)
    opened = open_card(set_id, card_id)
    parts = parts_of(opened)

    assert [(where, index) for where, index, _ in parts] == [
        ("abilities", 0),
        ("statics", 0),
    ]
    assert parts[0][2]["fields"]["trigger"] == "on_activate"
    assert parts[1][2]["fields"]["stat"] == "attack"


def test_changing_the_ability_leaves_the_static_alone(workspace: Path) -> None:
    from fsme.lab.desk.author import open_card

    set_id, card_id = a_saved_card(A_CARD_WITH_BOTH)
    opened = open_card(set_id, card_id)
    before = build_card(opened)

    opened["card"]["fields"]["abilities"][0]["fields"]["effects"][0]["fields"][
        "amount"
    ] = 6
    after = build_card(opened)

    assert after["statics"] == before["statics"]
    assert after["abilities"][0]["effects"][0]["amount"] == 6
    assert before["abilities"][0]["effects"][0]["amount"] == 1


def test_changing_the_static_leaves_the_ability_alone(workspace: Path) -> None:
    from fsme.lab.desk.author import open_card

    set_id, card_id = a_saved_card(A_CARD_WITH_BOTH)
    opened = open_card(set_id, card_id)
    before = build_card(opened)

    opened["card"]["fields"]["statics"][0]["fields"]["amount"] = 4
    after = build_card(opened)

    assert after["abilities"] == before["abilities"]
    assert after["statics"][0]["amount"] == 4
    assert before["statics"][0]["amount"] == 1


def test_changing_one_of_two_abilities_leaves_the_other(workspace: Path) -> None:
    from fsme.lab.desk.author import open_card

    two = dict(A_CARD_WITH_BOTH)
    two = json.loads(json.dumps(A_CARD_WITH_BOTH))
    two["name"] = "Two Ways"
    two.pop("statics")
    two["abilities"].append(
        {
            "fields": {
                "trigger": "turn_start",
                "effects": [
                    {
                        "id": "heal",
                        "fields": {"amount": 2},
                        "groups": {},
                        "aim": "controller",
                        "aim_fields": {},
                        "aim_groups": {},
                    }
                ],
            },
            "groups": {},
        }
    )

    set_id, card_id = a_saved_card(two)
    opened = open_card(set_id, card_id)
    before = build_card(opened)

    opened["card"]["fields"]["abilities"][1]["fields"]["effects"][0]["fields"][
        "amount"
    ] = 5
    after = build_card(opened)

    assert after["abilities"][0] == before["abilities"][0]
    assert after["abilities"][1]["effects"][0]["amount"] == 5


def test_a_changed_multi_part_card_still_passes_the_checker(
    workspace: Path,
) -> None:
    from fsme.lab.desk.author import open_card

    set_id, card_id = a_saved_card(A_CARD_WITH_BOTH)
    opened = open_card(set_id, card_id)
    opened["card"]["fields"]["statics"][0]["fields"]["amount"] = 3
    opened["card"]["fields"]["abilities"][0]["fields"]["effects"][0]["fields"][
        "amount"
    ] = 2

    assert check_card(build_card(opened)) == []


def test_an_unchanged_multi_part_card_rebuilds_identically(
    workspace: Path,
) -> None:
    from fsme.lab.desk.author import open_card, sets

    set_id, card_id = a_saved_card(A_CARD_WITH_BOTH)
    where = Path(sets()[0]["where"]) / "cards" / f"{card_id}.json"
    written = json.loads(where.read_text("utf-8"))["cards"][0]

    assert build_card(open_card(set_id, card_id)) == written


def test_more_cards_can_be_changed_now_than_before(walked: list[dict[str, Any]]) -> None:
    """
    The point of the stage, in a number.

    The walk used to open a card only when it had exactly one part. It asks
    about each part in turn now, so what is left out is what a card *does* —
    an action the walk does not offer — and never how it is put together.
    """
    offers = {
        one["id"]
        for one in catalogue()["effects"]
        if not one.get("a_step") and not one["replacing"] and finishable_here(one)
    }
    one_part, any_parts = 0, 0

    for row in walked:
        if row["state"] is None:
            continue

        parts = parts_of(row["state"])
        fine = all(
            step["id"] in offers
            for _, _, part in parts
            for step in steps_in(part)
        )

        if fine:
            any_parts += 1

        if fine and len(parts) == 1 and steps_in(parts[0][2]):
            one_part += 1

    assert one_part >= 180, one_part
    assert any_parts >= 225, any_parts
    assert any_parts > one_part


def finishable_here(effect: Mapping[str, Any]) -> bool:
    return all(
        not f["required"] or (f["asked"] != "never" and f["shown"] == "form")
        for f in effect["fields"]
    )


@lru_cache(maxsize=1)
def _where_a_part_keeps_what_it_does() -> Mapping[str, str]:
    """
    For each kind of part, the field it calls a list of steps.

    Asked of the shapes once: building the catalogue is milliseconds and there
    are hundreds of parts.
    """
    can = catalogue()

    return {
        shape["id"]: next(
            (f["id"] for f in shape["fields"] if f["a_list_of"] == "step"), ""
        )
        for section in ("abilities", "statics")
        for shape in can[section]
    }


def steps_in(part: Mapping[str, Any]) -> list[dict[str, Any]]:
    """
    What a part holds that happens, found by asking its shape.
    """
    holds = _where_a_part_keeps_what_it_does().get(part["id"], "")

    return part["fields"].get(holds, []) if holds else []


# ----------------------------------------------------------------------
# 13. The screens for it
# ----------------------------------------------------------------------


def test_the_page_asks_which_part_only_when_there_is_a_choice() -> None:
    said = script()

    assert "function chooseWhich(" in said
    assert "function openPart(" in said

    # One part is not a choice, so it is not put as one.
    beginning = body_of("startFrom")

    assert "parts.length === 1" in beginning
    assert "chooseWhich()" in beginning


def test_the_parts_screen_is_drawn_from_the_card_shape() -> None:
    """
    The lists are the card's own and so are the words above them.
    """
    screen = body_of("chooseWhich")

    assert "asksOf(list)" in screen
    assert "partsOf()" in screen
    assert "abilities" not in screen and "statics" not in screen
    # It reads the parts back rather than offering controls for them.
    assert "saidAs(" in screen and "saidOf(" in screen

    for typed in ("<input", "<select", "<textarea", "setField"):
        assert typed not in screen, f"the parts screen draws {typed}"


def test_a_part_with_nothing_that_happens_is_asked_about_itself() -> None:
    """
    A static holds no actions, so its own questions are what there is to ask —
    through the same `ask`, because a part's questions are questions.
    """
    opening = body_of("openPart")

    assert "does ? sofar() : ask(0)" in opening

    # And what is being asked about is a node either way.
    about = body_of("asking")

    assert "walk.list" in about
    assert "walk.where" in about


# ----------------------------------------------------------------------
# 14. The contract for keeping a change
# ----------------------------------------------------------------------
#
# Written before the flow that would do it. Saving is the first thing in this
# whole chain that writes over somebody's file, so what it must and must not do
# is settled here rather than discovered afterwards.


def a_card_in_a_set(fields: dict[str, Any], named: str = "Keeping") -> tuple[str, str, Path]:
    """
    One card saved into a set of its own, and the file it went into.
    """
    from fsme.lab.desk.author import make_set, save_card

    made = make_set(named)
    saved = save_card({"set": made["id"], "card": {"fields": fields, "groups": {}}})

    assert saved["saved"], saved["problems"]

    return made["id"], saved["card"]["id"], Path(saved["where"])


def test_saving_a_card_nobody_changed_changes_nothing(workspace: Path) -> None:
    """
    Scenario A. Opening a card and keeping it must not move a byte.
    """
    from fsme.lab.desk.author import open_card, save_card

    set_id, card_id, where = a_card_in_a_set(A_TWO_STEP_CARD)
    before = where.read_text("utf-8")

    said = save_card(open_card(set_id, card_id))

    assert said["saved"]
    assert where.read_text("utf-8") == before


def test_changing_one_value_and_keeping_it_keeps_the_rest(workspace: Path) -> None:
    """
    Scenario B. The changed thing changes; nothing else does.
    """
    from fsme.lab.desk.author import open_card, save_card

    set_id, card_id, where = a_card_in_a_set(A_TWO_STEP_CARD)
    before = json.loads(where.read_text("utf-8"))["cards"][0]

    opened = open_card(set_id, card_id)
    opened["card"]["fields"]["abilities"][0]["fields"]["effects"][0]["fields"][
        "amount"
    ] = 5

    assert save_card(opened)["saved"]

    after = json.loads(where.read_text("utf-8"))["cards"][0]

    assert after["abilities"][0]["effects"][0]["amount"] == 5
    assert after["abilities"][0]["effects"][1] == before["abilities"][0]["effects"][1]
    assert after["abilities"][0]["targets"] == before["abilities"][0]["targets"]

    for key in ("id", "name", "type", "expansion", "schema_version"):
        assert after[key] == before[key], key

    # And opening it again gives back what was kept.
    assert open_card(set_id, card_id)["card"] == read_card(after)["card"]


def test_a_change_that_breaks_the_card_is_not_kept(workspace: Path) -> None:
    """
    Scenario C. The file stays as it was and the reason is said.
    """
    from fsme.lab.desk.author import open_card, save_card

    set_id, card_id, where = a_card_in_a_set(A_TWO_STEP_CARD)
    before = where.read_text("utf-8")

    opened = open_card(set_id, card_id)
    opened["card"]["fields"]["abilities"][0]["fields"]["effects"][0]["fields"][
        "amount"
    ] = "lots"
    said = save_card(opened)

    assert not said["saved"]
    assert said["problems"]
    assert where.read_text("utf-8") == before


def test_keeping_a_change_to_one_part_keeps_the_others(workspace: Path) -> None:
    """
    The multi-part case, written to disk rather than only in hand.
    """
    from fsme.lab.desk.author import open_card, save_card

    set_id, card_id, where = a_card_in_a_set(A_CARD_WITH_BOTH)
    before = json.loads(where.read_text("utf-8"))["cards"][0]

    opened = open_card(set_id, card_id)
    opened["card"]["fields"]["statics"][0]["fields"]["amount"] = 4

    assert save_card(opened)["saved"]

    after = json.loads(where.read_text("utf-8"))["cards"][0]

    assert after["abilities"] == before["abilities"]
    assert after["statics"][0]["amount"] == 4


def test_saving_can_only_ever_write_into_the_author_s_own_sets(
    workspace: Path,
) -> None:
    """
    The shipped cards cannot be touched by any of this, and not by care —
    by where the writing goes. A set is a directory under the author's own
    workspace, and that is the only place a card is written or read from.
    """
    from fsme.content.workspace import sets_directory
    from fsme.lab.desk.author import open_card, save_card

    set_id, card_id, where = a_card_in_a_set(A_TWO_STEP_CARD)

    assert sets_directory() in where.parents
    assert CONTENT not in where.parents

    said = save_card(open_card(set_id, card_id))

    assert sets_directory() in Path(said["where"]).parents


def test_the_shipped_cards_are_not_reachable_from_a_set(workspace: Path) -> None:
    """
    Nothing in `content/` appears in the author's sets, so nothing there can
    be opened and therefore nothing there can be written over.
    """
    from fsme.lab.desk.author import sets

    a_card_in_a_set(A_TWO_STEP_CARD)
    mine = {card["id"] for one in sets() for card in one["cards"]}
    shipped = {
        card["id"]
        for path in CONTENT.rglob("*.json")
        for card in json.loads(path.read_text("utf-8")).get("cards", ())
        if isinstance(json.loads(path.read_text("utf-8")), dict)
    }

    assert mine & shipped == set()


# --- the identity a card is kept under --------------------------------------
#
# A card's identifier is what everything else calls it by — a scenario file
# names cards by identifier, typed by hand. So the identifier is the card's
# own, settled when it is first saved, and a card that is opened carries it
# back. Renaming changes what the card is called, not which card it is.


def test_build_card_keeps_the_display_name_apart_from_the_identity() -> None:
    """
    Two different things, and a card carries both.
    """
    card = build_card({"set": "probe", "card": {"fields": A_TWO_STEP_CARD}})

    assert card["name"] == "Thumbtack"
    assert card["id"] == "probe-loot-thumbtack"


def test_a_new_card_still_takes_its_identity_from_its_name() -> None:
    """
    A card nobody has saved has no identity yet, so its name gives it one.
    That is the only moment the name decides anything.
    """
    card = build_card({"set": "probe", "card": {"fields": A_TWO_STEP_CARD}})

    assert card["id"] == "probe-loot-thumbtack"


def test_an_opened_card_carries_the_identity_it_was_read_under(
    workspace: Path,
) -> None:
    """
    Nothing else can tell which file a card came out of.
    """
    from fsme.lab.desk.author import open_card

    set_id, card_id, _ = a_card_in_a_set(A_TWO_STEP_CARD)
    opened = open_card(set_id, card_id)

    assert opened["opened"]["card"] == card_id


def test_an_opened_card_carries_what_the_file_was(workspace: Path) -> None:
    """
    And what the file said at the moment it was read, so a change to it
    afterwards can be noticed.
    """
    from fsme.lab.desk.author import open_card

    set_id, card_id, where = a_card_in_a_set(A_TWO_STEP_CARD)
    first = open_card(set_id, card_id)["opened"]["fingerprint"]

    assert first

    where.write_text(where.read_text("utf-8") + "\n", encoding="utf-8")

    assert open_card(set_id, card_id)["opened"]["fingerprint"] != first


def test_renaming_a_card_keeps_its_identity(workspace: Path) -> None:
    """
    Open it, call it something else, keep it. It is the same card: the same
    identifier, in the same file, under a new name — and no second copy
    anywhere, because nothing new was made.
    """
    from fsme.lab.desk.author import open_card, save_card, sets

    set_id, card_id, where = a_card_in_a_set(A_TWO_STEP_CARD)

    opened = open_card(set_id, card_id)
    opened["card"]["fields"]["name"] = "Drawing Pin"
    said = save_card(opened)

    assert said["saved"], said["problems"]
    assert said["card"]["id"] == card_id
    assert said["card"]["name"] == "Drawing Pin"
    assert Path(said["where"]) == where

    kept = sorted(p.name for p in where.parent.glob("*.json"))

    assert kept == [where.name], kept
    assert [one["name"] for one in sets()[0]["cards"]] == ["Drawing Pin"]

    # And opening it again gives the new name under the old identifier.
    again = open_card(set_id, card_id)

    assert again["card"]["fields"]["name"] == "Drawing Pin"
    assert again["opened"]["card"] == card_id


def test_renaming_a_card_makes_no_file_under_the_new_name(
    workspace: Path,
) -> None:
    """
    The name-shaped path is never written, so there is nothing to clean up
    and nothing that could be opened as a card of its own.
    """
    from fsme.lab.desk.author import open_card, save_card

    set_id, card_id, where = a_card_in_a_set(A_TWO_STEP_CARD)

    opened = open_card(set_id, card_id)
    opened["card"]["fields"]["name"] = "Drawing Pin"

    assert save_card(opened)["saved"]
    assert not (where.parent / f"{set_id}-loot-drawing_pin.json").exists()


# --- a file that changed while somebody was working on it -------------------


def test_a_card_changed_underneath_is_not_overwritten(workspace: Path) -> None:
    """
    Somebody opens a card. The file changes — another window, a text editor, a
    copy pulled from somewhere. Keeping the first one's change must not throw
    the other away.
    """
    from fsme.lab.desk.author import open_card, save_card

    set_id, card_id, where = a_card_in_a_set(A_TWO_STEP_CARD)
    opened = open_card(set_id, card_id)

    meanwhile = json.loads(where.read_text("utf-8"))
    meanwhile["cards"][0]["abilities"][0]["effects"][0]["amount"] = 99
    where.write_text(json.dumps(meanwhile, indent=2) + "\n", encoding="utf-8")
    outside = where.read_text("utf-8")

    opened["card"]["fields"]["abilities"][0]["fields"]["effects"][0]["fields"][
        "amount"
    ] = 3
    said = save_card(opened)

    assert not said["saved"], "the other change was thrown away"
    assert said["changed"]
    assert where.read_text("utf-8") == outside


def test_a_card_changed_underneath_says_why(workspace: Path) -> None:
    """
    And says it in words, rather than only in a flag.
    """
    from fsme.lab.desk.author import open_card, save_card

    set_id, card_id, where = a_card_in_a_set(A_TWO_STEP_CARD)
    opened = open_card(set_id, card_id)

    where.write_text(where.read_text("utf-8") + "\n", encoding="utf-8")

    said = save_card(opened)

    assert not said["saved"]
    assert said["problems"]
    assert "changed" in " ".join(said["problems"]).lower()


def test_a_card_that_went_away_underneath_is_not_quietly_remade(
    workspace: Path,
) -> None:
    """
    Deleted somewhere else while it was open. Saving would put it back
    without anybody asking for it.
    """
    from fsme.lab.desk.author import open_card, save_card

    set_id, card_id, where = a_card_in_a_set(A_TWO_STEP_CARD)
    opened = open_card(set_id, card_id)
    where.unlink()

    said = save_card(opened)

    assert not said["saved"]
    assert said["changed"]
    assert not where.exists()


def test_a_card_saved_twice_from_one_opening_is_refused_the_second_time(
    workspace: Path,
) -> None:
    """
    The first keeping is the change; the second is working from a card that
    is no longer what is on disk, which is the same problem by another route.
    """
    from fsme.lab.desk.author import open_card, save_card

    set_id, card_id, _ = a_card_in_a_set(A_TWO_STEP_CARD)
    opened = open_card(set_id, card_id)
    opened["card"]["fields"]["abilities"][0]["fields"]["effects"][0]["fields"][
        "amount"
    ] = 4

    assert save_card(opened)["saved"]

    opened["card"]["fields"]["abilities"][0]["fields"]["effects"][0]["fields"][
        "amount"
    ] = 5

    assert not save_card(opened)["saved"]


def test_an_identity_that_is_not_a_card_identifier_is_refused(
    workspace: Path,
) -> None:
    """
    The identifier names a file, so it may only ever be a name — never a way
    out of the set it belongs to.
    """
    from fsme.lab.desk.author import AuthorError, open_card, save_card

    set_id, card_id, _ = a_card_in_a_set(A_TWO_STEP_CARD)
    opened = open_card(set_id, card_id)

    for pretending in ("../elsewhere", "a/b", "", "Thumbtack.json"):
        opened["opened"]["card"] = pretending

        with pytest.raises(AuthorError):
            save_card(opened)


# --- nothing half written ---------------------------------------------------


def test_a_save_that_fails_leaves_the_card_exactly_as_it_was(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The write goes somewhere else first and only then becomes the card, so a
    failure at the worst moment leaves the old card whole rather than half of
    a new one.
    """
    import fsme.lab.desk.author as author

    set_id, card_id, where = a_card_in_a_set(A_TWO_STEP_CARD)
    before = where.read_text("utf-8")

    opened = author.open_card(set_id, card_id)
    opened["card"]["fields"]["abilities"][0]["fields"]["effects"][0]["fields"][
        "amount"
    ] = 7

    def refuse(*_: Any, **__: Any) -> None:
        raise OSError("the disk went away")

    monkeypatch.setattr(author.os, "replace", refuse)

    with pytest.raises(OSError):
        author.save_card(opened)

    assert where.read_text("utf-8") == before


def test_a_save_that_fails_leaves_nothing_behind(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    And no half-written file sitting beside it either.
    """
    import fsme.lab.desk.author as author

    set_id, card_id, where = a_card_in_a_set(A_TWO_STEP_CARD)

    opened = author.open_card(set_id, card_id)

    def refuse(*_: Any, **__: Any) -> None:
        raise OSError("the disk went away")

    monkeypatch.setattr(author.os, "replace", refuse)

    with pytest.raises(OSError):
        author.save_card(opened)

    assert [p.name for p in where.parent.iterdir()] == [where.name]


def test_a_card_is_never_seen_half_written(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A reader that looks at the moment a card is being kept sees the old card
    or the new one, never part of either. The write happens beside the card
    and replaces it in one step, so there is no moment to catch.
    """
    import fsme.lab.desk.author as author

    set_id, card_id, where = a_card_in_a_set(A_TWO_STEP_CARD)
    seen: list[Any] = []
    replace = author.os.replace

    def look(source: Any, target: Any) -> None:
        # Whatever is at the card's own path while the new one is being
        # written must still be a whole card.
        seen.append(json.loads(Path(target).read_text("utf-8")))
        replace(source, target)

    opened = author.open_card(set_id, card_id)
    opened["card"]["fields"]["abilities"][0]["fields"]["effects"][0]["fields"][
        "amount"
    ] = 7

    monkeypatch.setattr(author.os, "replace", look)

    assert author.save_card(opened)["saved"]

    assert seen, "the card was written some other way"
    assert seen[0]["cards"][0]["abilities"][0]["effects"][0]["amount"] == 2
    assert (
        json.loads(where.read_text("utf-8"))["cards"][0]["abilities"][0]["effects"][
            0
        ]["amount"]
        == 7
    )


def test_a_card_sharing_a_file_with_others_is_not_kept(workspace: Path) -> None:
    """
    A set written by hand may keep several cards in one file. Keeping one of
    them would write a file named after that card and leave the file it came
    from — the same card twice, in two places, both loading. So it is refused
    while nothing here knows how to write one card back into a file of many.
    """
    from fsme.lab.desk.author import make_set, open_card, save_card

    made = make_set("Together")
    both = Path(made["where"]) / "cards" / "a_few.json"
    first = build_card({"set": made["id"], "card": {"fields": A_TWO_STEP_CARD}})
    second = build_card({"set": made["id"], "card": {"fields": A_CARD_WITH_BOTH}})
    both.write_text(
        json.dumps({"cards": [first, second]}, indent=2) + "\n", encoding="utf-8"
    )

    opened = open_card(made["id"], first["id"])
    said = save_card(opened)

    assert not said["saved"]
    assert said["changed"]
    assert [p.name for p in both.parent.iterdir()] == [both.name]
    assert len(json.loads(both.read_text("utf-8"))["cards"]) == 2


# --- keeping a card, and then keeping it again ------------------------------


def test_a_card_that_was_kept_comes_back_with_its_identity(
    workspace: Path,
) -> None:
    """
    Saving a card makes its file say something new, which is exactly what the
    check before a save looks for. So a save says what the card is now, and
    whoever kept it can carry on from there rather than being told the card
    changed underneath them by themselves.
    """
    from fsme.lab.desk.author import open_card, save_card

    set_id, card_id, where = a_card_in_a_set(A_TWO_STEP_CARD)
    opened = open_card(set_id, card_id)
    opened["card"]["fields"]["abilities"][0]["fields"]["effects"][0]["fields"][
        "amount"
    ] = 4
    said = save_card(opened)

    assert said["saved"]
    assert said["opened"]["card"] == card_id
    assert said["opened"]["file"] == where.name
    assert said["opened"]["fingerprint"]
    assert said["opened"]["fingerprint"] != opened["opened"]["fingerprint"]


def test_a_card_can_be_kept_twice_running(workspace: Path) -> None:
    """
    Change, keep, change again, keep again — which is what somebody does.
    """
    from fsme.lab.desk.author import open_card, save_card

    set_id, card_id, where = a_card_in_a_set(A_TWO_STEP_CARD)
    holding = open_card(set_id, card_id)

    for amount in (4, 5, 6):
        holding["card"]["fields"]["abilities"][0]["fields"]["effects"][0]["fields"][
            "amount"
        ] = amount
        said = save_card(holding)

        assert said["saved"], said["problems"]

        holding["opened"] = said["opened"]

    written = json.loads(where.read_text("utf-8"))["cards"][0]

    assert written["abilities"][0]["effects"][0]["amount"] == 6
    assert written["id"] == card_id


def test_a_card_that_was_made_here_is_given_an_identity_to_keep(
    workspace: Path,
) -> None:
    """
    A card being made has no identity until it is first kept. After that it
    has one, and renaming it will not make a second card.
    """
    from fsme.lab.desk.author import make_set, save_card

    made = make_set("Fresh")
    said = save_card(
        {"set": made["id"], "card": {"fields": A_TWO_STEP_CARD, "groups": {}}}
    )

    assert said["saved"]
    assert said["opened"]["card"] == said["card"]["id"]

    # Renamed and kept again from what the save gave back: still one card.
    again = {
        "set": made["id"],
        "card": {"fields": dict(A_TWO_STEP_CARD, name="Drawing Pin"), "groups": {}},
        "opened": said["opened"],
    }
    kept = save_card(again)

    assert kept["saved"], kept["problems"]
    assert kept["card"]["id"] == said["card"]["id"]
    assert kept["card"]["name"] == "Drawing Pin"
    assert len(list(Path(said["where"]).parent.glob("*.json"))) == 1


# --- a card being made, and one that is already there ------------------------
#
# The one route the carried identity cannot cover. A card being made has never
# been saved, so it has no identity and no fingerprint — there is nothing to
# compare. Its identifier is made out of its name and type, so two cards named
# the same in one set want the same identifier, and the second used to take
# the first one's place without a word.


def test_a_new_card_does_not_write_over_one_already_there(
    workspace: Path,
) -> None:
    """
    Somebody makes a second card and calls it what the first one is called.
    That is a thing to say, not a thing to do quietly.
    """
    from fsme.lab.desk.author import save_card

    set_id, card_id, where = a_card_in_a_set(A_TWO_STEP_CARD)
    before = where.read_text("utf-8")

    said = save_card(
        {"set": set_id, "card": {"fields": A_TWO_STEP_CARD, "groups": {}}}
    )

    assert not said["saved"]
    assert said["problems"]
    assert where.read_text("utf-8") == before
    assert [p.name for p in where.parent.iterdir()] == [where.name]


def test_the_card_it_would_have_written_over_is_named(workspace: Path) -> None:
    """
    Said in the words the person used, so they know which card they mean.
    """
    from fsme.lab.desk.author import save_card

    set_id, _, _ = a_card_in_a_set(A_TWO_STEP_CARD)
    said = save_card(
        {"set": set_id, "card": {"fields": A_TWO_STEP_CARD, "groups": {}}}
    )

    assert "Thumbtack" in " ".join(said["problems"])


def test_a_card_that_was_opened_is_not_refused_for_being_itself(
    workspace: Path,
) -> None:
    """
    The card that is already there is this one. Carrying its identity is what
    says so, and it is the difference between keeping a card and making a
    second one with the same name.
    """
    from fsme.lab.desk.author import open_card, save_card

    set_id, card_id, _ = a_card_in_a_set(A_TWO_STEP_CARD)
    said = save_card(open_card(set_id, card_id))

    assert said["saved"], said["problems"]
    assert said["card"]["id"] == card_id


def test_a_new_card_may_take_a_name_nobody_else_has(workspace: Path) -> None:
    """
    And the ordinary case still works: a second card, called something else.
    """
    from fsme.lab.desk.author import save_card

    set_id, _, where = a_card_in_a_set(A_TWO_STEP_CARD)
    said = save_card(
        {
            "set": set_id,
            "card": {
                "fields": dict(A_TWO_STEP_CARD, name="Drawing Pin"),
                "groups": {},
            },
        }
    )

    assert said["saved"], said["problems"]
    assert len(list(where.parent.glob("*.json"))) == 2


def test_a_new_card_clashing_with_one_in_a_shared_file_is_refused(
    workspace: Path,
) -> None:
    """
    What clashes is the identifier, not the file name. A set written by hand
    may keep its cards anywhere, and a card is still already there.
    """
    from fsme.lab.desk.author import make_set, save_card

    made = make_set("Elsewhere")
    already = build_card({"set": made["id"], "card": {"fields": A_TWO_STEP_CARD}})
    both = Path(made["where"]) / "cards" / "a_few.json"
    both.write_text(
        json.dumps({"cards": [already]}, indent=2) + "\n", encoding="utf-8"
    )

    said = save_card(
        {"set": made["id"], "card": {"fields": A_TWO_STEP_CARD, "groups": {}}}
    )

    assert not said["saved"]
    assert [p.name for p in both.parent.iterdir()] == [both.name]
