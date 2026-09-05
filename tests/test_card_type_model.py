"""
What the engine says a card type is, and what the desk offers.

Every fact about a card type a person ever sees — which kinds there are, what
each is called, what each is, how each is used — comes from one place. These
tests are what stops a second place from appearing: they read the model and
the offer and insist the two are the same list.
"""

from __future__ import annotations

from typing import Any

from fsme.cards.types import PRINTED_NUMBERS, TYPE_WORDS, CardType
from fsme.lab.desk.author import check_card
from fsme.lab.desk.capabilities import catalogue
from fsme.runtime.vocabulary import engine_vocabulary

# ----------------------------------------------------------------------
# 1. The model
# ----------------------------------------------------------------------


def test_every_kind_of_card_the_engine_has() -> None:
    """
    Twelve, and the order they are declared in.

    Written down because the order is read: `CARD_TYPES` in the target
    resolver is this order, and it is the order two search filters offer
    their options in. A member inserted in the middle moves them.
    """
    assert [str(kind) for kind in CardType] == [
        "character",
        "treasure",
        "loot",
        "monster",
        "room",
        "bonus_soul",
        "event",
        "curse",
        "starting_item",
        "soul",
        "token",
        "other",
    ]


def test_every_kind_is_described() -> None:
    """
    A kind with no words is a kind somebody has to look up.
    """
    assert set(TYPE_WORDS) == set(CardType)


def test_the_kinds_that_print_numbers_are_a_choice_about_cards() -> None:
    """
    Six of the twelve, and the silence about the rest is deliberate — an
    absence here refuses nothing. Pinned so that changing it is a decision
    somebody makes rather than a side effect of something else.
    """
    assert {str(kind) for kind in PRINTED_NUMBERS} == {
        "character",
        "curse",
        "loot",
        "monster",
        "room",
        "treasure",
    }


def test_the_engine_settles_how_four_kinds_are_used() -> None:
    """
    Read from beside `play_loot`, `_activatable` and `_resolve_event`, not
    written down twice.

    This said three until an event was looked at properly. Nobody plays an
    event — it is turned over out of the monster deck — and that is what the
    absence was about; but what the engine does once it is turned over is
    what it does with a played loot card, and `_resolve_event` emits the same
    moment. One right answer is one right answer however the card got there.
    """
    assert dict(engine_vocabulary().used_by) == {
        "loot": "on_play",
        "treasure": "on_activate",
        "starting_item": "on_activate",
        "event": "on_play",
    }


def test_what_an_event_waits_for_is_what_a_played_card_waits_for() -> None:
    """
    The same constant, not a second string that happens to read alike.

    A value copied here would go on saying `on_play` after the engine stopped
    meaning it, which is the whole reason none of these is written down.
    """
    from fsme.rules.loot import PLAYED_BY

    used = engine_vocabulary().used_by

    assert used["event"] == str(PLAYED_BY)
    assert used["event"] == used["loot"], "two answers for one moment"


def test_the_kinds_with_no_one_moment_still_say_so() -> None:
    """
    The half that must not move. Each of these reacts to several moments and
    no one of them is *the* moment, so there is nothing to fill in.
    """
    used = engine_vocabulary().used_by

    for kind in ("monster", "room", "character", "curse"):
        assert kind not in used, kind


# ----------------------------------------------------------------------
# 2. What the card itself says
# ----------------------------------------------------------------------


def _type_field() -> Any:
    card = engine_vocabulary().node_shape("card")
    assert card is not None

    return card.params["type"]


def test_a_card_may_be_any_of_the_twelve() -> None:
    """
    The field a card writes its kind in offers every kind there is.
    """
    field = _type_field()

    assert [str(value) for value in field.values] == [str(k) for k in CardType]
    assert dict(field.values_mean) == {str(k): v for k, v in TYPE_WORDS.items()}


def test_the_checker_takes_a_card_of_any_kind() -> None:
    """
    No kind is refused, so no kind may be withheld from an author.
    """
    ability = {
        "trigger": "on_play",
        "effects": [{"effect": "gain_coins", "amount": 1}],
    }

    for kind in CardType:
        card = {
            "id": f"probe-{kind}",
            "name": "Probe",
            "type": str(kind),
            "expansion": "probe",
            "abilities": [ability],
        }

        assert check_card(card) == [], str(kind)


# ----------------------------------------------------------------------
# 3. What the desk offers
# ----------------------------------------------------------------------


def test_the_desk_offers_every_kind_the_engine_has() -> None:
    """
    The one test that forbids a second list.

    A hand-written subset, a filter, a reordering into a literal — each of
    them fails here, which is the point. The desk publishes the model or it
    publishes nothing.
    """
    offered = [one["id"] for one in catalogue()["kinds"]]

    assert set(offered) == {str(kind) for kind in CardType}
    assert len(offered) == len(set(offered))


def test_every_kind_offered_is_named_and_described() -> None:
    """
    Both, for all twelve. A kind with no name is drawn as its identifier —
    `Your bonus_soul` — which is the defect this model exists to prevent.
    """
    for one in catalogue()["kinds"]:
        assert one["name"], one["id"]
        assert one["name"] != one["id"], one["id"]
        assert one["about"], one["id"]


def test_the_words_offered_are_the_engines_own() -> None:
    """
    Not re-worded on the way out. What a kind is, is `TYPE_WORDS`.
    """
    said = {one["id"]: one["about"] for one in catalogue()["kinds"]}

    assert said == {str(kind): words for kind, words in TYPE_WORDS.items()}


def test_the_kinds_are_offered_in_the_order_an_author_meets_them() -> None:
    """
    Not the order the enum declares them in — that order is read elsewhere
    and is not about how often somebody makes one of these.
    """
    assert [one["id"] for one in catalogue()["kinds"]] == [
        "loot",
        "treasure",
        "monster",
        "character",
        "room",
        "curse",
        "starting_item",
        "event",
        "bonus_soul",
        "soul",
        "token",
        "other",
    ]


def test_the_names_a_person_reads() -> None:
    """
    The six that were always offered keep the words they had.
    """
    named = {one["id"]: one["name"] for one in catalogue()["kinds"]}

    assert named["loot"] == "Loot card"
    assert named["treasure"] == "Treasure"
    assert named["monster"] == "Monster"
    assert named["character"] == "Character"
    assert named["room"] == "Room"
    assert named["curse"] == "Curse"


def test_how_a_kind_is_used_reaches_the_desk() -> None:
    """
    Including `starting_item`, which the engine has always settled and the
    desk could not say, because it did not offer that kind at all.

    And `event`, which it settles the same way it settles a loot card: the
    desk is what this is for, because a kind the desk is told about is one it
    can put questions for instead of handing somebody the whole card.
    """
    used = {one["id"]: one["used_by"] for one in catalogue()["kinds"]}

    assert used["loot"] == "on_play"
    assert used["treasure"] == "on_activate"
    assert used["starting_item"] == "on_activate"
    assert used["event"] == "on_play"

    # No single moment is *the* moment for these, and filling one in would
    # put a trigger on a card that never fires.
    for kind in ("monster", "room", "character", "curse"):
        assert used[kind] == "", kind
