"""
Offering the words somebody has already used, without making them the only ones.

Three of the things a card writes have no closed set: what a counter is called,
which families a card belongs to, and what cards are called. The engine has
always accepted any word for all three, and must go on doing so — a set that
invents a counter is the ordinary case, not an error. What it did not do was
*say* which words had been used, so an author typing into an empty box was
being asked to remember a spelling the machine was holding.

So the fix is a suggestion and not a domain, and the difference is the whole
point of this file. Every test here that offers a word is paired with one that
writes a word nobody has ever written and insists the card is still correct.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from fsme.cards import validate_card
from fsme.content.suggestions import from_roots, gathered, pools_by_key
from fsme.content.vocabulary import (
    CARD_NAME_POOL,
    COUNTER_POOL,
    POOLS,
    TAG_POOL,
    ParamShape,
    Vocabulary,
)
from fsme.lab.desk import author
from fsme.lab.desk.capabilities import catalogue
from fsme.runtime.vocabulary import engine_vocabulary

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"

PAGE = (
    Path(__file__).resolve().parents[1]
    / "src/fsme/lab/desk/static/author.html"
)

EXPANSION = "example_expansion"


@pytest.fixture(scope="module")
def vocabulary() -> Vocabulary:
    return engine_vocabulary()


@pytest.fixture(scope="module")
def keys(vocabulary: Vocabulary) -> dict[str, str]:
    return dict(pools_by_key(vocabulary))


@pytest.fixture(scope="module")
def shipped(keys: dict[str, str]) -> dict[str, list[str]]:
    return from_roots([CONTENT_ROOT], keys)


@pytest.fixture(scope="module")
def can() -> dict[str, Any]:
    return catalogue()


@pytest.fixture(scope="module")
def page() -> str:
    return PAGE.read_text("utf-8")


def every_parameter(vocabulary: Vocabulary):
    """
    Every parameter of every shape there is, with where it came from.
    """
    for table in (
        vocabulary.shapes,
        vocabulary.condition_shapes,
        vocabulary.target_shapes,
        vocabulary.node_shapes,
    ):
        for owner, shape in table.items():
            for name, parameter in shape.params.items():
                yield f"{owner}.{name}", parameter


def a_card(*abilities: Any, name: str = "Dark Coin", **also: Any) -> dict:
    card: dict[str, Any] = {
        "id": "example_expansion-loot-dark_coin",
        "name": name,
        "type": "loot",
        "expansion": EXPANSION,
        "schema_version": "1",
    }

    if abilities:
        card["abilities"] = list(abilities)

    return card | also


def complaints(vocabulary: Vocabulary, card: dict) -> list[str]:
    return validate_card(
        card,
        known_effects=vocabulary.effects,
        known_triggers=vocabulary.triggers,
        known_conditions=vocabulary.conditions,
        known_targets=vocabulary.targets,
        shapes=vocabulary.shapes,
        condition_shapes=vocabulary.condition_shapes,
        target_shapes=vocabulary.target_shapes,
        node_shapes=vocabulary.node_shapes,
    )


# ------------------------------------------------------------ what is declared


def test_every_counter_tag_and_name_draws_from_a_pool(
    vocabulary: Vocabulary,
) -> None:
    """
    Not a sample of them. Every parameter spelt one of these three words is a
    word out of an open vocabulary, and one that quietly was not would be the
    one box on the page that stayed empty for no reason anybody could see.
    """
    wants = {
        "counter": COUNTER_POOL,
        "tag": TAG_POOL,
        "tags": TAG_POOL,
        "named": CARD_NAME_POOL,
        "name": CARD_NAME_POOL,
    }

    found = {
        where: parameter.suggest_from
        for where, parameter in every_parameter(vocabulary)
        if where.rsplit(".", 1)[-1] in wants
    }

    assert found, "nothing named a counter, a tag or a name"

    for where, pool in found.items():
        assert pool == wants[where.rsplit(".", 1)[-1]], where


def test_an_event_key_is_offered_nothing(vocabulary: Vocabulary) -> None:
    """
    `modify_event.key` names a field of the event being replaced, and which
    fields there are depends on the trigger the *ability* names — which is not
    in the node and not anywhere else this could read. A pooled list of the
    keys other cards happened to use would offer `cents` to somebody editing a
    damage watcher, so there is no list and the box stays plain.
    """
    keys = [
        where
        for where, parameter in every_parameter(vocabulary)
        if where.rsplit(".", 1)[-1] == "key"
    ]

    assert keys

    for where in keys:
        owner, name = where.rsplit(".", 1)
        shape = (
            vocabulary.shapes.get(owner)
            or vocabulary.condition_shapes.get(owner)
        )

        assert shape is not None
        assert shape.params[name].suggest_from == "", where


def test_a_pool_is_never_also_a_closed_list(vocabulary: Vocabulary) -> None:
    for where, parameter in every_parameter(vocabulary):
        if parameter.suggest_from:
            assert not parameter.values, where
            assert parameter.suggest_from in POOLS, where


def test_holding_both_is_refused_where_it_is_written() -> None:
    """
    Not pinned by this test alone: the shape refuses it, so there is no way to
    build one and nothing downstream has to cope with one.
    """
    with pytest.raises(ValueError, match="both values"):
        ParamShape("counter", "text", values=("charge",), suggest_from=COUNTER_POOL)

    with pytest.raises(ValueError, match="no such pool"):
        ParamShape("counter", "text", suggest_from="spaghetti")


def test_a_pool_is_not_a_choice(vocabulary: Vocabulary) -> None:
    """
    A closed list makes a parameter a `which`, which is drawn as a dropdown.
    A pool must not: the whole point is that the box stays a box.
    """
    for where, parameter in every_parameter(vocabulary):
        if parameter.suggest_from and not parameter.role == "structure":
            assert parameter.role == "names", where


def test_which_keys_feed_which_pool_is_read_off_the_shapes(
    keys: dict[str, str],
) -> None:
    assert keys == {
        "counter": COUNTER_POOL,
        "tag": TAG_POOL,
        "tags": TAG_POOL,
        "named": CARD_NAME_POOL,
        "name": CARD_NAME_POOL,
    }


def test_one_word_drawing_from_two_pools_is_refused() -> None:
    """
    A pool is one namespace, so a key belongs to one. Two would mean guessing
    which pool a written word went into, and a guess there puts event keys in
    with counter names.
    """
    from fsme.content.vocabulary import ConditionShape

    muddled = Vocabulary(
        condition_shapes={
            "one": ConditionShape(
                "one", {"counter": ParamShape("counter", "text",
                                              suggest_from=COUNTER_POOL)}
            ),
            "two": ConditionShape(
                "two", {"counter": ParamShape("counter", "text",
                                              suggest_from=TAG_POOL)}
            ),
        }
    )

    with pytest.raises(ValueError, match="two pools"):
        pools_by_key(muddled)


# ----------------------------------------------------------- where words come from


def test_the_words_come_out_of_the_content(
    shipped: dict[str, list[str]],
) -> None:
    """
    Measured against the cards, not against a list written here. If somebody
    adds a card with a new counter on it, this test wants updating — and that
    is the point: the pool is the corpus.
    """
    assert shipped[COUNTER_POOL] == [
        "charge",
        "egg",
        "fistula",
        "gold",
        "knot",
        "nuke",
        "paw",
        "poo",
        "tear",
    ]
    assert "guppy" in shipped[TAG_POOL]
    assert "eternal" in shipped[TAG_POOL]
    assert "The Bloat" in shipped[CARD_NAME_POOL]
    assert len(shipped[CARD_NAME_POOL]) > 500


def test_the_counter_namespace_is_one_pool(keys: dict[str, str]) -> None:
    """
    A counter put on by an effect is the counter a condition asks about and the
    counter a cost is paid in. Gathering them apart would offer an author half
    the words they have used.
    """
    pools = gathered(
        [
            a_card(
                {
                    "trigger": "on_play",
                    "effects": [
                        {"effect": "add_counter", "target": "self",
                         "counter": "written_by_an_effect"}
                    ],
                    "conditions": [
                        {"card_counters": {"counter": "read_by_a_condition"}}
                    ],
                    "cost": {"counters": {"counter": "paid_as_a_cost"}},
                }
            )
        ],
        keys,
    )

    assert pools[COUNTER_POOL] == [
        "paid_as_a_cost",
        "read_by_a_condition",
        "written_by_an_effect",
    ]


def test_tags_come_from_what_cards_declare(keys: dict[str, str]) -> None:
    """
    A tag parameter is matched against the card's own `tags`, so that is where
    the words are. A card merely *asking* for a family also names one, and both
    ends feed the same pool because they are the same namespace.
    """
    pools = gathered(
        [
            a_card(tags=["a_family_a_card_declares"]),
            a_card(
                {
                    "trigger": "on_play",
                    "targets": [
                        {"target_treasure": {"tag": "a_family_a_card_asks_for",
                                             "as": "it"}}
                    ],
                    "effects": [{"effect": "destroy_treasure", "target": "it"}],
                }
            ),
        ],
        keys,
    )

    assert pools[TAG_POOL] == [
        "a_family_a_card_asks_for",
        "a_family_a_card_declares",
    ]


def test_names_come_from_what_cards_are_called(keys: dict[str, str]) -> None:
    pools = gathered([a_card(name="Something Nobody Has Written")], keys)

    assert pools[CARD_NAME_POOL] == ["Something Nobody Has Written"]


def test_every_pool_comes_back_even_with_nothing_in_it(
    keys: dict[str, str],
) -> None:
    """
    A page that has to tell "no words yet" from "no such pool" is a page that
    will get it wrong once.
    """
    assert gathered([], keys) == {pool: [] for pool in POOLS}


def test_a_root_that_is_not_there_is_no_words_rather_than_a_failure(
    keys: dict[str, str], tmp_path: Path
) -> None:
    assert from_roots([tmp_path / "nowhere"], keys) == {
        pool: [] for pool in POOLS
    }


def test_a_set_being_edited_still_offers_its_other_cards(
    keys: dict[str, str], tmp_path: Path
) -> None:
    """
    Nothing is checked on the way through. A form that offered no words because
    one file was mid-edit would stop working exactly when somebody is working.
    """
    root = tmp_path / "root"
    (root / EXPANSION / "cards").mkdir(parents=True)
    (root / EXPANSION / "manifest.json").write_text(
        json.dumps({"id": EXPANSION, "name": "Example", "schema_version": "1"}),
        encoding="utf-8",
    )
    (root / EXPANSION / "cards" / "good.json").write_text(
        json.dumps({"cards": [a_card(name="A Readable Card")]}), encoding="utf-8"
    )
    (root / EXPANSION / "cards" / "broken.json").write_text(
        "{ this is not json", encoding="utf-8"
    )

    assert from_roots([root], keys)[CARD_NAME_POOL] == ["A Readable Card"]


def test_the_author_is_offered_the_shipped_words_and_their_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Both ends of the same question: the cards we ship hold nearly every word an
    author wants, and their own sets hold the one they invented last week. The
    game loads both, so a form offering one of them offers half an answer.
    """
    monkeypatch.setenv("FSME_HOME", str(tmp_path))

    mine = author.sets_directory() / "mine"
    (mine / "cards").mkdir(parents=True)
    (mine / "manifest.json").write_text(
        json.dumps({"id": "mine", "name": "Mine", "schema_version": "1"}),
        encoding="utf-8",
    )
    (mine / "cards" / "one.json").write_text(
        json.dumps(
            {
                "cards": [
                    a_card(
                        {
                            "trigger": "on_play",
                            "effects": [
                                {"effect": "add_counter", "target": "self",
                                 "counter": "a_counter_of_my_own"}
                            ],
                        }
                    )
                ]
            }
        ),
        encoding="utf-8",
    )

    pools = author.suggestions(CONTENT_ROOT)

    assert "a_counter_of_my_own" in pools[COUNTER_POOL]
    assert "charge" in pools[COUNTER_POOL]


# ------------------------------------------------------- nothing is refused


def test_a_counter_nobody_has_used_is_a_correct_card(
    vocabulary: Vocabulary, shipped: dict[str, list[str]]
) -> None:
    assert "unheard_of" not in shipped[COUNTER_POOL]
    assert (
        complaints(
            vocabulary,
            a_card(
                {
                    "trigger": "on_play",
                    "effects": [
                        {"effect": "add_counter", "target": "self",
                         "counter": "unheard_of"}
                    ],
                }
            ),
        )
        == []
    )


def test_a_tag_and_a_card_name_nobody_has_used_are_correct_too(
    vocabulary: Vocabulary,
) -> None:
    assert (
        complaints(
            vocabulary,
            a_card(
                {
                    "trigger": "on_play",
                    "targets": [
                        {
                            "target_deck_card": {
                                "deck": "treasure",
                                "tag": "unheard_of",
                                "named": "No Such Card",
                                "as": "it",
                            }
                        }
                    ],
                    "effects": [{"effect": "destroy_treasure", "target": "it"}],
                },
                tags=["unheard_of_family"],
            ),
        )
        == []
    )


def test_a_new_word_survives_being_written_and_read_back(
    keys: dict[str, str]
) -> None:
    """
    Round trip through the desk's reader and writer, which is where a value the
    editor did not recognise would be dropped. The author's meaning is the word
    they typed, and it comes back the word they typed.
    """
    card = a_card(
        {
            "trigger": "on_play",
            "targets": [
                {
                    "target_deck_card": {
                        "deck": "treasure",
                        "tag": "brand_new_family",
                        "named": "A Card Nobody Has Made",
                        "as": "it",
                    }
                }
            ],
            "effects": [
                {"effect": "add_counter", "target": "it",
                 "counter": "brand_new_counter", "amount": 3}
            ],
        },
        name="A Card Nobody Has Made",
        tags=["brand_new_family"],
    )

    written = author.build_card(author.read_card(card))

    assert gathered([written], keys) == gathered([card], keys)
    assert gathered([written], keys) == {
        CARD_NAME_POOL: ["A Card Nobody Has Made"],
        COUNTER_POOL: ["brand_new_counter"],
        TAG_POOL: ["brand_new_family"],
    }


def test_every_word_in_the_corpus_survives_being_read_and_written(
    keys: dict[str, str],
) -> None:
    """
    The corpus is the regression test. Declaring a pool changed no value, so
    the words a thousand cards were written with are the words they still hold.

    Card for card rather than pool against pool: a card that dropped a counter
    another card also uses would leave the pools identical and the card wrong.
    """
    from fsme.content import ContentLoader

    loader = ContentLoader()
    seen = 0

    for card in loader.raw_cards(CONTENT_ROOT):
        written = author.build_card(author.read_card(dict(card)))

        assert gathered([written], keys) == gathered([dict(card)], keys), (
            card["id"]
        )
        seen += 1

    assert seen == 1045


# --------------------------------------------------------------- the page


def test_the_engine_publishes_the_pool_a_field_draws_from(
    can: dict[str, Any],
) -> None:
    counters = [
        field
        for one in can["effects"]
        if one["id"] == "add_counter"
        for field in one["fields"]
        if field["id"] == "counter"
    ]

    assert len(counters) == 1
    assert counters[0]["suggest_from"] == COUNTER_POOL
    assert counters[0]["choices"] == []
    assert counters[0]["role"] == "names"


def test_the_capability_catalogue_holds_no_words(can: dict[str, Any]) -> None:
    """
    What the engine can do, which is the same with no cards loaded at all. The
    words are content and arrive from somewhere that has some.
    """
    said = set(re.findall(r'"([^"]*)"', json.dumps(can)))

    for word in ("charge", "egg", "guppy", "passive", "The Bloat"):
        assert word not in said


def test_the_page_offers_the_words_without_closing_the_box(page: str) -> None:
    """
    A `datalist` and not a `select`. Read off the page, because only the page
    knows what it draws — and what it must not draw is a list somebody cannot
    type past.
    """
    control = page.split("function valueHtml(")[1].split("\nfunction ")[0]

    assert "f.suggest_from ? (pools[f.suggest_from] || [])" in control
    assert "<datalist" in control
    assert 'list="${listed}"' in control


def test_the_page_decides_by_metadata_and_not_by_what_a_card_is(
    page: str,
) -> None:
    """
    The one rule the renderer has: nothing in it may know the name of an
    effect, a card or a pool. It reads `suggest_from` and looks the words up.
    """
    control = page.split("function valueHtml(")[1].split("\nfunction ")[0]

    for named in ("counters", "card_names", "add_counter", "guppy", "charge"):
        assert named not in control


def test_the_page_works_when_there_are_no_words_at_all(page: str) -> None:
    assert "pools = {};" in page
    assert "said.pools || {}" in page
    assert "pool.length ?" in page


# ------------------------------------------------------------- regressions


def test_a_closed_list_is_still_closed(vocabulary: Vocabulary) -> None:
    """
    `values` and `domain_from` are untouched: they mean what they meant, and a
    parameter that has one still refuses everything else.
    """
    deck = vocabulary.shape("move_cards").params["deck"]

    assert deck.values
    assert deck.role == "which"
    assert deck.suggest_from == ""

    assert complaints(
        vocabulary,
        a_card(
            {
                "trigger": "on_play",
                "effects": [{"effect": "move_cards", "deck": "spaghetti"}],
            }
        ),
    ) != []


def test_a_dependent_choice_is_still_dependent(vocabulary: Vocabulary) -> None:
    stat = vocabulary.node_shape("static").params["stat"]

    assert stat.domain_from == "scope"
    assert stat.suggest_from == ""


def test_an_event_key_is_still_a_plain_box(can: dict[str, Any]) -> None:
    key = [
        field
        for one in can["effects"]
        if one["id"] == "modify_event"
        for field in one["fields"]
        if field["id"] == "key"
    ]

    assert len(key) == 1
    assert key[0]["suggest_from"] == ""
    assert key[0]["choices"] == []
    assert key[0]["role"] == "names"
