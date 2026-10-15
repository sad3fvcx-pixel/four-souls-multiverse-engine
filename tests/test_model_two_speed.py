"""
The quicker ways the digest and the generator do their work give the same
answers as the plain ones.

``state_digest`` hashes ``repr(state_fingerprint(state))``, the full digest
walks a model 2 generator's state without visiting every number, a model 2
generator hands back a stream's state it already took, and a shuffle hashes
the bytes its keys share once. None of that may change a single byte of a
digest, a state or a key: the plain way of doing each is written out here,
and the quick way is held to it.
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path
from typing import Any

import pytest

from fsme.api import load_content
from fsme.cards import CardType
from fsme.content import ContentLibrary
from fsme.game import Game
from fsme.lab.simulation.agent import ScriptedAgent
from fsme.lab.simulation.runner import _whose_move
from fsme.replay import digest
from fsme.replay.digest import state_digest, state_digest_v2, state_fingerprint
from fsme.rng.rng import RNG, KeyedRNG, keyed_state, shuffle_key
from fsme.state import GameState

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"
NAMES = ["Ann", "Bo", "Cy", "Di"]


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


def plain_digest(state: GameState) -> str:
    return hashlib.sha256(repr(state_fingerprint(state)).encode("utf-8")).hexdigest()[:32]


def plain_digest_v2(state: GameState) -> str:
    """The full digest with the generator's state walked by ``_canon``, item by item."""
    where = (GameState, "rng_state")
    held = digest._WRITTEN_AS[where]
    digest._WRITTEN_AS[where] = walked

    try:
        return state_digest_v2(state)
    finally:
        digest._WRITTEN_AS[where] = held


def walked(value: Any) -> Any:
    """How the full digest wrote a generator's state before it had a quicker way."""
    return value if value is None or type(value) is tuple else digest._canon(value)


def generator_states() -> dict[str, Any]:
    keyed = KeyedRNG(5)
    shapes: dict[str, Any] = {"no streams": keyed.get_state()}

    keyed.randint_for("dice", 1, 6)
    shapes["one stream"] = keyed.get_state()

    keyed.randint_for("target", 0, 3)
    keyed.shuffle_for("deck:loot", [])
    keyed.shuffle_for("deal:characters", [])
    shapes["two streams and counts"] = keyed.get_state()
    shapes["read back from a file"] = keyed_state(
        json.loads(json.dumps(shapes["two streams and counts"]))
    )

    legacy = RNG(5)
    legacy.randint(1, 6)
    shapes["model 1"] = legacy.get_state()

    shapes["nothing yet"] = None
    shapes["a list"] = [1, 2, [3, 4]]
    shapes["both quotes"] = {"a'b": 'c"d', "plain": (1, (2, 3), None)}
    shapes["a backslash"] = {"model": "2", "streams": {}, "shuffles": {"x\\y": 1}}
    shapes["unprintable"] = {"model": "2", "streams": {}, "shuffles": {"tab\there": 1}}
    shapes["not ascii"] = {"model": "2", "streams": {}, "shuffles": {"ünïcode": 2}}
    shapes["a tuple of odd kinds"] = (3, (1, True, 2.5, "s", None, (4, 5)), None)
    shapes["a tuple holding a list"] = (3, ([1, 2], 3), None)

    return shapes


@pytest.mark.parametrize("shape", sorted(generator_states()))
def test_both_digests_of_any_generator_state_are_the_plain_ones(
    everything: ContentLibrary, shape: str
) -> None:
    game = Game.from_content(everything, NAMES, seed=5)
    game.start()
    game.state.rng_state = generator_states()[shape]

    assert state_digest(game.state) == plain_digest(game.state)
    assert state_digest(game.state) == state_digest(game.state)
    assert state_digest_v2(game.state) == plain_digest_v2(game.state)


@pytest.mark.parametrize("shape", sorted(generator_states()))
def test_the_full_digest_writes_a_generator_state_as_canon_would(shape: str) -> None:
    value = generator_states()[shape]

    assert digest._rng(value) == walked(value)
    assert repr(digest._rng(value)) == repr(walked(value))


def test_a_bare_state_digests_as_it_always_did() -> None:
    bare = GameState()

    assert state_digest(bare) == plain_digest(bare)
    assert state_digest_v2(bare) == plain_digest_v2(bare)


@pytest.mark.parametrize("model", ["1", "2"])
def test_every_position_of_a_game_digests_the_plain_way(
    everything: ContentLibrary, model: str
) -> None:
    for seed in (3, 8):
        game = Game.from_content(everything, NAMES, seed=seed, rng_model=model)
        game.start()

        agent = ScriptedAgent(seed)

        for index in range(150):
            if game.is_over:
                break

            chosen = agent.choose(game, seats=(_whose_move(game),))
            assert chosen is not None
            game.submit(chosen[0])

            assert state_digest(game.state) == plain_digest(game.state), (seed, index)

            if index % 8 == 7:
                assert state_digest_v2(game.state) == plain_digest_v2(game.state), (seed, index)


def test_a_loaded_model_two_game_digests_the_plain_way(everything: ContentLibrary) -> None:
    game = Game.from_content(everything, NAMES, seed=4, rng_model="2")
    game.start()
    agent = ScriptedAgent(4)

    for _ in range(300):
        chosen = agent.choose(game, seats=(_whose_move(game),))
        assert chosen is not None
        game.submit(chosen[0])

        try:
            data = json.loads(json.dumps(game.save()))
        except Exception:
            continue

        back = Game.load(data, everything)

        assert state_digest(back.state) == plain_digest(back.state) == state_digest(game.state)
        assert state_digest_v2(back.state) == plain_digest_v2(back.state) == state_digest_v2(
            game.state
        )

        return

    raise AssertionError("the game never reached a position that can be saved")


# ----------------------------------------------------------------------
# The generator
# ----------------------------------------------------------------------


def taken_fresh(rng: KeyedRNG) -> dict[str, Any]:
    """A model 2 state as the generator's streams say it is right now."""
    state = rng.get_state()
    state["streams"] = {domain: stream.getstate() for domain, stream in rng._streams.items()}

    return state


def test_a_stream_state_handed_out_twice_is_the_state_it_is() -> None:
    rng = KeyedRNG(9)
    picked = random.Random(3)

    for _ in range(400):
        if picked.random() < 0.5:
            rng.randint_for(picked.choice(["dice", "target"]), 1, 6)

        before = rng.get_state()
        again = rng.get_state()

        assert before == again == taken_fresh(rng)
        assert before is not again
        assert before["streams"] is not again["streams"]


def test_a_state_handed_out_does_not_move_when_the_generator_does() -> None:
    rng = KeyedRNG(9)
    rng.randint_for("dice", 1, 6)

    taken = rng.get_state()
    kept = json.loads(json.dumps(taken))

    for _ in range(50):
        rng.randint_for("dice", 1, 6)
        rng.randint_for("target", 0, 9)

    assert json.loads(json.dumps(taken)) == kept
    assert rng.get_state() != taken

    rewound = KeyedRNG(9)
    rewound.set_state(taken)
    replayed = KeyedRNG(9)
    replayed.set_state(taken)

    assert [rewound.randint_for("dice", 1, 6) for _ in range(30)] == [
        replayed.randint_for("dice", 1, 6) for _ in range(30)
    ]


def test_a_restored_generator_hands_out_the_state_it_was_given() -> None:
    rng = KeyedRNG(12)

    for _ in range(40):
        rng.randint_for("dice", 1, 6)

    rng.randint_for("target", 0, 3)
    state = json.loads(json.dumps(rng.get_state()))

    restored = KeyedRNG(12)
    restored.set_state(state)

    assert restored.get_state() == keyed_state(state) == taken_fresh(restored)

    restored.randint_for("dice", 1, 6)
    rng.randint_for("dice", 1, 6)

    assert restored.get_state() == rng.get_state() == taken_fresh(rng)


class Card:
    def __init__(self, identifier: str, tag: int) -> None:
        self.id = identifier
        self.tag = tag


def plainly_shuffled(seed: int, domain: str, number: int, cards: list[Card]) -> list[Card]:
    copies: dict[str, int] = {}
    keyed = []

    for card in cards:
        copy = copies.get(card.id, 0)
        copies[card.id] = copy + 1
        keyed.append((shuffle_key(seed, domain, number, card.id, copy), card))

    return [card for _, card in sorted(keyed, key=lambda pair: pair[0])]


@pytest.mark.parametrize("seed", [0, 7, -7, 2**70])
def test_a_shuffle_puts_every_card_where_its_own_key_says(seed: int) -> None:
    picked = random.Random(seed)
    rng = KeyedRNG(seed)

    for number in range(6):
        cards = [
            Card(picked.choice(["pills", "bomb", "ü-card", "", "a" * 40]), tag)
            for tag in range(picked.randint(0, 60))
        ]
        expected = plainly_shuffled(seed, "deck:loot", number, cards)

        shuffled = list(cards)
        rng.shuffle_for("deck:loot", shuffled)

        assert [card.tag for card in shuffled] == [card.tag for card in expected]


def test_a_shuffled_deal_is_the_deal_the_plain_keys_give(everything: ContentLibrary) -> None:
    game = Game.from_content(everything, NAMES, seed=21, rng_model="2")
    dealt: list[Any] = [
        definition for definition in everything.definitions() if definition.type is CardType.LOOT
    ]

    expected = [card.id for card in plainly_shuffled(21, "deal:loot", 0, dealt)]
    loot = [card.id for card in game.state.loot_deck.cards]

    assert loot == expected[: len(loot)]
