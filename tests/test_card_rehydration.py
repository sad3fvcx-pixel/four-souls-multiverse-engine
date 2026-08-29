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
