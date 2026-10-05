"""
The two RNG models.

Model 1 is the generator every game so far was played on, and is still the one
a game gets unless it asks: everything here that touches it checks that it is
exactly what it was. Model 2 gives each kind of randomness a stream of its
own and shuffles a deck by a key per card, so that taking one card out of the
game leaves every other card where it was — the contract it is held to below,
down to the bytes it hashes.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import random
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from fsme.api import load_content
from fsme.cards import CardType
from fsme.commands import Command, CommandType
from fsme.content import ContentLibrary
from fsme.game import Game
from fsme.journal import Journal, JournalFormatError, JournalKeeper, replay_journal
from fsme.journal.entry import KEYED_JOURNAL_FORMAT
from fsme.lab.simulation.agent import ScriptedAgent
from fsme.lab.simulation.runner import _whose_move
from fsme.replay import Recorder, Recording, ReplayFormatError, ReplayPlayer
from fsme.replay.digest import state_digest, state_digest_v2
from fsme.replay.recording import KEYED_REPLAY_FORMAT
from fsme.rng.rng import (
    DEAL_DOMAINS,
    DECK_DOMAINS,
    DEFAULT_RNG_MODEL,
    DOMAINS,
    RNG,
    STREAM_DOMAINS,
    KeyedRNG,
    RNGError,
    UnknownRNGDomain,
    keyed_state,
    rng_for,
    shuffle_key,
    stream_seed,
)
from fsme.rules.setup import SetupError, new_game
from fsme.serialization import SAVE_FORMAT_VERSION, SaveError
from fsme.serialization.game_save import KEYED_SAVE_FORMAT

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"
NAMES = ["Ann", "Bo", "Cy", "Di"]


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


class Card:
    """Something shuffled by its definition id, which is all a shuffle reads."""

    def __init__(self, identifier: str, tag: int = 0) -> None:
        self.id = identifier
        self.tag = tag

    def __repr__(self) -> str:
        return f"Card({self.id!r}, {self.tag})"


def cards(*identifiers: str) -> list[Card]:
    return [Card(identifier) for identifier in identifiers]


def ids(sequence: list[Any]) -> list[str]:
    return [one.id for one in sequence]


def shuffled(seed: int, domain: str, sequence: list[Any], *, before: int = 0) -> list[Any]:
    rng = KeyedRNG(seed)

    for _ in range(before):
        rng.shuffle_for(domain, [])

    out = list(sequence)
    rng.shuffle_for(domain, out)

    return out


# ----------------------------------------------------------------------
# The domains
# ----------------------------------------------------------------------


def test_the_domains_are_a_closed_list() -> None:
    assert DEAL_DOMAINS == {
        "deal:loot", "deal:treasure", "deal:monster", "deal:room", "deal:characters"
    }
    assert DECK_DOMAINS == {"deck:loot", "deck:treasure", "deck:monster", "deck:room"}
    assert STREAM_DOMAINS == {"dice", "target"}
    assert DOMAINS == DEAL_DOMAINS | DECK_DOMAINS | STREAM_DOMAINS
    assert not DEAL_DOMAINS & DECK_DOMAINS
    assert all(domain.isascii() for domain in DOMAINS)


@pytest.mark.parametrize("model", ["1", "2"])
@pytest.mark.parametrize("domain", ["", "deck:Loot", "deal:loot ", "other:x", "deck:shop"])
def test_an_unknown_domain_is_refused_on_either_model(model: str, domain: str) -> None:
    rng = rng_for(5, model)

    with pytest.raises(UnknownRNGDomain):
        rng.randint_for(domain, 1, 6)

    with pytest.raises(UnknownRNGDomain):
        rng.shuffle_for(domain, cards("a", "b"))


@pytest.mark.parametrize("model", ["1", "2"])
def test_a_domain_is_refused_for_the_wrong_kind_of_draw(model: str) -> None:
    rng = rng_for(5, model)

    with pytest.raises(UnknownRNGDomain):
        rng.randint_for("deck:loot", 1, 6)

    with pytest.raises(UnknownRNGDomain):
        rng.shuffle_for("dice", cards("a", "b"))


def test_model_two_has_no_draw_without_a_domain() -> None:
    rng = KeyedRNG(5)

    with pytest.raises(RNGError):
        rng.randint(1, 6)

    with pytest.raises(RNGError):
        rng.random()

    with pytest.raises(RNGError):
        rng.choice([1, 2])

    with pytest.raises(RNGError):
        rng.shuffle(cards("a", "b"))


def test_there_is_no_third_model() -> None:
    with pytest.raises(RNGError):
        rng_for(5, "3")

    assert DEFAULT_RNG_MODEL == "1"
    assert type(rng_for(5)) is RNG
    assert type(rng_for(5, "2")) is KeyedRNG


# ----------------------------------------------------------------------
# Streams
# ----------------------------------------------------------------------


def reference_stream_seed(seed: int, domain: str) -> int:
    digest = hashlib.sha256(
        b"fsme-rng/2\x00stream\x00" + str(seed).encode("ascii") + b"\x00" + domain.encode("ascii")
    ).digest()

    return int.from_bytes(digest[:8], "big")


@pytest.mark.parametrize("seed", [0, 1, -1, 7, -7, 2**63, -(2**63), 2**70, 10**30])
@pytest.mark.parametrize("domain", sorted(STREAM_DOMAINS))
def test_a_stream_is_seeded_by_the_contract(seed: int, domain: str) -> None:
    assert stream_seed(seed, domain) == reference_stream_seed(seed, domain)
    assert 0 <= stream_seed(seed, domain) < 2**64


def test_stream_seeds_are_pinned() -> None:
    assert stream_seed(0, "dice") == 0x8216C8A81E0D0F45
    assert stream_seed(-7, "target") == 0xBAB0BF8D41F9C009
    assert stream_seed(2**70, "dice") == 0x13AD755EC84BEFAA


def test_streams_are_the_same_for_the_same_seed_and_apart_otherwise() -> None:
    seeds = list(range(-300, 301)) + [2**64 + 5, -(2**64) - 5]
    made = {
        (seed, domain): stream_seed(seed, domain)
        for seed in seeds
        for domain in STREAM_DOMAINS
    }

    assert len(set(made.values())) == len(made)
    assert all(stream_seed(n, "dice") != stream_seed(-n, "dice") for n in range(1, 300))
    assert stream_seed(12, "dice") == stream_seed(12, "dice")


def test_a_stream_draws_the_same_numbers_for_the_same_seed() -> None:
    def rolls(seed: int) -> list[int]:
        rng = KeyedRNG(seed)
        return [rng.randint_for("dice", 1, 6) for _ in range(8)]

    assert rolls(42) == [3, 6, 3, 1, 2, 6, 3, 3]
    assert rolls(42) == rolls(42)
    assert rolls(42) != rolls(-42)


@pytest.mark.parametrize("seed", [True, False, 1.0, "5", None])
def test_a_model_two_seed_is_a_whole_number_and_never_a_bool(seed: Any) -> None:
    with pytest.raises(TypeError):
        stream_seed(seed, "dice")

    with pytest.raises(TypeError):
        KeyedRNG(seed)


def test_one_domain_does_not_move_another() -> None:
    picked = random.Random(7)

    for _ in range(100):
        seed = picked.randint(-(10**6), 10**6)

        alone = KeyedRNG(seed)
        expected = [alone.randint_for("dice", 1, 6) for _ in range(30)]

        busy = KeyedRNG(seed)
        rolled: list[int] = []

        while len(rolled) < 30:
            domain = picked.choice(sorted(DOMAINS))

            if domain == "dice":
                rolled.append(busy.randint_for("dice", 1, 6))
            elif domain in STREAM_DOMAINS:
                busy.randint_for(domain, 0, picked.randint(0, 9))
            else:
                busy.shuffle_for(domain, cards(*[str(i) for i in range(picked.randint(0, 20))]))

        assert rolled == expected


# ----------------------------------------------------------------------
# Keyed shuffles
# ----------------------------------------------------------------------


def reference_key(seed: int, domain: str, number: int, identifier: str, copy: int) -> bytes:
    named = identifier.encode("utf-8")

    return hashlib.sha256(
        b"fsme-rng/2\x00shuffle\x00"
        + str(seed).encode("ascii")
        + b"\x00"
        + domain.encode("ascii")
        + b"\x00"
        + str(number).encode("ascii")
        + b"\x00"
        + len(named).to_bytes(4, "big")
        + named
        + str(copy).encode("ascii")
    ).digest()


def test_a_card_is_keyed_by_the_contract() -> None:
    for identifier in ("a", "loot_deck-bombs-base_game-bomb", "ünïcode", ""):
        assert shuffle_key(42, "deck:loot", 3, identifier, 1) == reference_key(
            42, "deck:loot", 3, identifier, 1
        )

    assert shuffle_key(42, "deck:loot", 0, "a", 0).hex()[:16] == "0e4d03b59907b214"


def test_a_shuffle_is_pinned_and_repeatable() -> None:
    deck = cards("a", "b", "c", "d", "e", "f")

    assert ids(shuffled(42, "deck:loot", deck)) == ["a", "d", "e", "b", "c", "f"]
    assert ids(shuffled(42, "deck:loot", deck)) == ids(shuffled(42, "deck:loot", deck))


def test_a_shuffle_does_not_depend_on_the_order_it_was_handed() -> None:
    deck = cards(*[f"c{i}" for i in range(60)])

    assert ids(shuffled(9, "deck:treasure", deck)) == ids(
        shuffled(9, "deck:treasure", list(reversed(deck)))
    )


def test_taking_a_card_out_or_putting_one_in_leaves_the_others_in_order() -> None:
    deck = cards(*[f"c{i}" for i in range(80)])

    for seed in range(60):
        whole = ids(shuffled(seed, "deck:loot", deck))

        for gone in random.Random(seed).sample(range(80), 3):
            less = [card for index, card in enumerate(deck) if index != gone]

            assert ids(shuffled(seed, "deck:loot", less)) == [
                one for one in whole if one != f"c{gone}"
            ]

        more = ids(shuffled(seed, "deck:loot", deck + cards("new")))

        assert [one for one in more if one != "new"] == whole


def test_copies_of_one_card_are_told_apart_by_their_copy_number() -> None:
    keys = {shuffle_key(3, "deck:loot", 0, "pills", copy) for copy in range(4)}

    assert len(keys) == 4

    one = [Card("pills", 1), Card("pills", 2), Card("bomb", 3), Card("pills", 4)]
    other = [one[3], one[2], one[1], one[0]]

    assert ids(shuffled(3, "deck:loot", one)) == ids(shuffled(3, "deck:loot", other))
    assert sorted(card.tag for card in shuffled(3, "deck:loot", one)) == [1, 2, 3, 4]


def test_each_shuffle_of_a_domain_is_a_new_one() -> None:
    deck = cards(*[f"c{i}" for i in range(40)])

    orders = {tuple(ids(shuffled(5, "deck:loot", deck, before=n))) for n in range(6)}

    assert len(orders) == 6


def test_the_shuffle_count_belongs_to_its_domain() -> None:
    deck = cards(*[f"c{i}" for i in range(40)])

    busy = KeyedRNG(11)
    busy.shuffle_for("deck:treasure", cards("x", "y"))
    busy.randint_for("dice", 1, 6)
    busy.shuffle_for("deal:loot", list(deck))

    mine = list(deck)
    busy.shuffle_for("deck:loot", mine)

    assert ids(mine) == ids(shuffled(11, "deck:loot", deck))


def test_the_deal_and_the_game_never_share_a_shuffle() -> None:
    """
    The first shuffle of a deck during the game is not the deal again.

    Were they one domain, the game's first rebuild of a deck would be keyed
    like the deal, and would put its cards back in the order they were dealt.
    """
    deck = cards(*[f"c{i}" for i in range(40)])

    rng = KeyedRNG(17)
    dealt = list(deck)
    rng.shuffle_for("deal:loot", dealt)

    rebuilt = list(deck)
    rng.shuffle_for("deck:loot", rebuilt)

    assert ids(dealt) != ids(rebuilt)
    assert rng.get_state()["shuffles"] == {"deal:loot": 1, "deck:loot": 1}


def test_a_shuffle_never_asks_random(monkeypatch: pytest.MonkeyPatch) -> None:
    rng = KeyedRNG(4)

    def refuse(*_: Any, **__: Any) -> None:
        raise AssertionError("a keyed shuffle reached random.Random")

    monkeypatch.setattr(random, "Random", refuse)

    deck = cards(*[f"c{i}" for i in range(30)])
    rng.shuffle_for("deck:monster", deck)


def test_a_shuffle_is_the_same_whatever_python_hashes_with() -> None:
    probe = (
        "from fsme.rng.rng import KeyedRNG, stream_seed\n"
        "class C:\n"
        "    def __init__(self, i): self.id = i\n"
        "deck = [C(f'c{i}') for i in range(50)]\n"
        "rng = KeyedRNG(-7)\n"
        "rng.shuffle_for('deck:monster', deck)\n"
        "print([c.id for c in deck], stream_seed(-7, 'dice'), rng.get_state()['shuffles'])\n"
    )
    seen = set()

    for hashing in ("0", "1", "4242", "random"):
        ran = subprocess.run(
            [sys.executable, "-c", probe],
            env={**os.environ, "PYTHONHASHSEED": hashing},
            capture_output=True,
            text=True,
            check=True,
        )
        seen.add(ran.stdout)

    assert len(seen) == 1


def test_an_object_without_a_definition_id_cannot_be_shuffled() -> None:
    with pytest.raises(TypeError):
        KeyedRNG(1).shuffle_for("deck:loot", [object(), object()])


# ----------------------------------------------------------------------
# State
# ----------------------------------------------------------------------


def a_used_generator(seed: int = 77) -> KeyedRNG:
    rng = KeyedRNG(seed)

    for _ in range(200):
        rng.randint_for("dice", 1, 6)
        rng.randint_for("target", 0, 3)

    rng.shuffle_for("deck:loot", cards(*[f"c{i}" for i in range(20)]))
    rng.shuffle_for("deal:characters", cards("x", "y", "z"))

    return rng


def through_a_file(state: Any) -> Any:
    return json.loads(json.dumps(state))


def test_the_state_is_one_canonical_mapping() -> None:
    state = a_used_generator().get_state()

    assert list(state) == ["model", "streams", "shuffles"]
    assert state["model"] == "2"
    assert list(state["streams"]) == ["dice", "target"]
    assert state["shuffles"] == {"deal:characters": 1, "deck:loot": 1}
    assert list(state["shuffles"]) == sorted(state["shuffles"])
    assert keyed_state(through_a_file(state)) == state
    assert KeyedRNG(1).get_state() == {"model": "2", "streams": {}, "shuffles": {}}


def test_every_stream_and_count_comes_back_and_carries_on() -> None:
    playing = a_used_generator()

    restored = KeyedRNG(77)
    restored.set_state(through_a_file(playing.get_state()))

    assert restored.get_state() == playing.get_state()

    deck = cards(*[f"c{i}" for i in range(30)])
    one, other = list(deck), list(deck)

    playing.shuffle_for("deck:loot", one)
    restored.shuffle_for("deck:loot", other)

    assert ids(one) == ids(other)
    assert [playing.randint_for("dice", 1, 6) for _ in range(100)] == [
        restored.randint_for("dice", 1, 6) for _ in range(100)
    ]
    assert [playing.randint_for("target", 0, 9) for _ in range(50)] == [
        restored.randint_for("target", 0, 9) for _ in range(50)
    ]


def test_the_shuffle_counts_are_part_of_the_state() -> None:
    playing = a_used_generator()
    state = through_a_file(playing.get_state())
    state["shuffles"] = {}

    forgetful = KeyedRNG(77)
    forgetful.set_state(state)

    deck = cards(*[f"c{i}" for i in range(30)])
    one, other = list(deck), list(deck)

    playing.shuffle_for("deck:loot", one)
    forgetful.shuffle_for("deck:loot", other)

    assert ids(one) != ids(other)


@pytest.mark.parametrize(
    "spoil",
    [
        lambda state: state.update(model="1"),
        lambda state: state.pop("shuffles"),
        lambda state: state.update(extra=1),
        lambda state: state["streams"].update({"other": state["streams"]["dice"]}),
        lambda state: state["shuffles"].update({"deck:shop": 1}),
        lambda state: state["shuffles"].update({"deck:loot": -1}),
        lambda state: state["shuffles"].update({"deck:loot": True}),
        lambda state: state.update(streams=[]),
    ],
)
def test_a_spoiled_state_is_refused(spoil: Callable[[dict[str, Any]], Any]) -> None:
    state = through_a_file(a_used_generator().get_state())
    spoil(state)

    with pytest.raises((TypeError, ValueError, RNGError)):
        KeyedRNG(77).set_state(state)


# ----------------------------------------------------------------------
# A game on either model
# ----------------------------------------------------------------------


def definitions_by_type(library: ContentLibrary) -> dict[CardType, list[Any]]:
    grouped: dict[CardType, list[Any]] = {}

    for definition in library.definitions():
        grouped.setdefault(definition.type, []).append(definition)

    return grouped


@pytest.mark.parametrize("seed", [0, 11, -11, 123456])
def test_model_one_deals_from_one_stream_in_the_order_it_always_did(
    everything: ContentLibrary, seed: int
) -> None:
    """
    Model 1, re-derived from nothing but ``random.Random(seed)``: loot,
    treasure, monsters, rooms, characters, one stream, in that order.
    """
    state = new_game(everything, NAMES, seed=seed)
    grouped = definitions_by_type(everything)
    stream = random.Random(seed)

    expected: dict[CardType, list[str]] = {}

    for kind in (CardType.LOOT, CardType.TREASURE, CardType.MONSTER, CardType.ROOM):
        dealt = list(grouped[kind])
        stream.shuffle(dealt)
        expected[kind] = [definition.id for definition in dealt]

    characters = list(grouped[CardType.CHARACTER])
    stream.shuffle(characters)

    assert state.rng_model == "1"
    assert ids(state.loot_deck.cards) == expected[CardType.LOOT]

    for zone, kind in (
        (state.treasure_deck, CardType.TREASURE),
        (state.room_deck, CardType.ROOM),
    ):
        assert ids(zone.cards) == expected[kind][: len(zone.cards)]

    assert [player.character.id for player in state.players] == [
        definition.id for definition in characters[: len(NAMES)]
    ]


def test_a_game_is_on_model_one_unless_it_asks(everything: ContentLibrary) -> None:
    plain = Game.from_content(everything, NAMES, seed=3)
    named = Game.from_content(everything, NAMES, seed=3, rng_model="1")

    assert plain.state.rng_model == "1"
    assert type(plain.runtime.rng) is RNG
    assert state_digest_v2(plain.state) == state_digest_v2(named.state)

    keyed = Game.from_content(everything, NAMES, seed=3, rng_model="2")

    assert keyed.state.rng_model == "2"
    assert type(keyed.runtime.rng) is KeyedRNG


def test_a_game_cannot_ask_for_a_model_there_is_not(everything: ContentLibrary) -> None:
    with pytest.raises(SetupError):
        Game.from_content(everything, NAMES, seed=3, rng_model="3")


def test_on_model_two_a_card_taken_out_moves_nothing_else_in_the_deal(
    everything: ContentLibrary,
) -> None:
    gone = definitions_by_type(everything)[CardType.LOOT][0].id

    for seed in (0, 5, -5, 99):
        whole = new_game(everything, NAMES, seed=seed, rng_model="2")
        less = new_game(everything.without([gone]), NAMES, seed=seed, rng_model="2")

        assert [one for one in ids(whole.loot_deck.cards) if one != gone] == ids(
            less.loot_deck.cards
        )

        for name in ("treasure_deck", "monster_deck", "room_deck", "treasure_shop", "room_area"):
            assert ids(getattr(whole, name).cards) == ids(getattr(less, name).cards), name

        assert [p.character.id for p in whole.players] == [p.character.id for p in less.players]


def test_on_model_one_the_same_card_taken_out_reshuffles_its_whole_deck(
    everything: ContentLibrary,
) -> None:
    """What model 2 is for: on model 1 the deck the card came out of is another deck."""
    gone = definitions_by_type(everything)[CardType.LOOT][0].id

    whole = new_game(everything, NAMES, seed=5)
    less = new_game(everything.without([gone]), NAMES, seed=5)

    assert [one for one in ids(whole.loot_deck.cards) if one != gone] != ids(less.loot_deck.cards)


def played(game: Game, agent: ScriptedAgent, commands: int) -> list[str]:
    seen: list[str] = []

    for _ in range(commands):
        if game.is_over:
            break

        chosen = agent.choose(game, seats=(_whose_move(game),))
        assert chosen is not None
        assert game.submit(chosen[0]).accepted
        seen.append(state_digest_v2(game.state))

    return seen


def a_saved_game(
    everything: ContentLibrary, model: str, seed: int = 4
) -> tuple[Game, ScriptedAgent, dict[str, Any]]:
    game = Game.from_content(everything, NAMES, seed=seed, rng_model=model)
    game.start()
    agent = ScriptedAgent(seed)

    played(game, agent, 40)

    for _ in range(200):
        try:
            return game, agent, json.loads(json.dumps(game.save()))
        except SaveError:
            played(game, agent, 1)

    raise AssertionError("the game never reached a position that can be saved")


def test_a_model_two_game_saves_in_format_three_and_carries_on_exactly(
    everything: ContentLibrary,
) -> None:
    game, agent, saved = a_saved_game(everything, "2")

    assert saved["format"] == KEYED_SAVE_FORMAT == "3"
    assert saved["rng_model"] == "2"
    assert saved["rng"]["model"] == "2"

    back = Game.load(saved, everything)

    assert back.state.rng_model == "2"
    assert type(back.runtime.rng) is KeyedRNG
    assert back.runtime.rng.get_state() == game.runtime.rng.get_state()
    assert state_digest(back.state) == state_digest(game.state)
    assert state_digest_v2(back.state) == state_digest_v2(game.state)

    again = copy.deepcopy(agent)

    assert played(game, agent, 120) == played(back, again, 120)
    assert back.runtime.rng.get_state() == game.runtime.rng.get_state()


def test_a_model_one_game_still_saves_in_format_two_and_says_nothing_new(
    everything: ContentLibrary,
) -> None:
    game, agent, saved = a_saved_game(everything, "1")

    assert saved["format"] == SAVE_FORMAT_VERSION == "2"
    assert "rng_model" not in saved
    assert isinstance(saved["rng"], list)

    back = Game.load(saved, everything)

    assert back.state.rng_model == "1"
    assert type(back.runtime.rng) is RNG
    again = copy.deepcopy(agent)

    assert played(game, agent, 60) == played(back, again, 60)


def test_a_save_that_misstates_its_model_is_refused(everything: ContentLibrary) -> None:
    _, _, keyed = a_saved_game(everything, "2")
    _, _, legacy = a_saved_game(everything, "1")

    unsaid = dict(keyed)
    unsaid.pop("rng_model")

    claimed = dict(legacy, rng_model="2")

    mixed = dict(keyed, rng=legacy["rng"])

    spoiled = json.loads(json.dumps(keyed))
    spoiled["rng"]["shuffles"]["deck:shop"] = 1

    for data, said in (
        (unsaid, "does not say"),
        (claimed, "has no 'rng_model'"),
        (mixed, "cannot be restored"),
        (spoiled, "cannot be restored"),
    ):
        with pytest.raises(SaveError, match=said):
            Game.load(data, everything)


def kept(everything: ContentLibrary, model: str, seed: int = 6, commands: int = 90) -> Journal:
    game = Game.from_content(everything, NAMES[:3], seed=seed, rng_model=model)
    game.start()

    keeper = JournalKeeper(game)
    agent = ScriptedAgent(seed)

    for _ in range(commands):
        if game.is_over:
            break

        chosen = agent.choose(game, seats=(_whose_move(game),))
        assert chosen is not None
        keeper.submit(chosen[0], label=chosen[1])

    return keeper.journal


def test_a_model_two_journal_is_format_four_and_replays(everything: ContentLibrary) -> None:
    journal = kept(everything, "2")
    written = journal.to_dict()

    assert written["format"] == KEYED_JOURNAL_FORMAT == "4"
    assert written["rng_model"] == "2"

    back = Journal.from_dict(json.loads(json.dumps(written)))

    assert back.rng_model == "2"

    playback = replay_journal(back, everything)

    assert playback.faithful, str(playback.divergence)
    assert playback.replayed == len(journal)


def test_a_model_two_journal_does_not_replay_on_model_one(everything: ContentLibrary) -> None:
    written = kept(everything, "2").to_dict()
    written["format"] = "3"
    written.pop("rng_model")

    playback = replay_journal(Journal.from_dict(written), everything)

    assert not playback.faithful


def test_a_model_one_journal_is_the_journal_it_always_was(everything: ContentLibrary) -> None:
    journal = kept(everything, "1")
    written = journal.to_dict()

    assert written["format"] == "3"
    assert "rng_model" not in written
    assert Journal.from_dict(written).rng_model == "1"
    assert replay_journal(journal, everything).faithful


def test_a_journal_that_misstates_its_model_is_refused(everything: ContentLibrary) -> None:
    keyed = kept(everything, "2", commands=10).to_dict()
    legacy = kept(everything, "1", commands=10).to_dict()

    unsaid = dict(keyed)
    unsaid.pop("rng_model")

    with pytest.raises(JournalFormatError, match="does not say so"):
        Journal.from_dict(unsaid)

    with pytest.raises(JournalFormatError, match="has no rng_model"):
        Journal.from_dict(dict(legacy, rng_model="2"))

    with pytest.raises(JournalFormatError, match="does not say so"):
        Journal.from_dict(dict(keyed, rng_model="1"))


def recorded(everything: ContentLibrary, model: str, commands: int = 30) -> Recording:
    game = Game.from_content(everything, NAMES[:2], seed=5, rng_model=model)
    recorder = Recorder(game.runtime)
    assert recorder.submit(Command(type=CommandType.START_GAME, player=0)).accepted

    agent = ScriptedAgent(5)

    while len(recorder) < commands and not game.is_over:
        chosen = agent.choose(game, seats=(_whose_move(game),))
        assert chosen is not None
        recorder.submit(chosen[0])

    return recorder.recording()


def dealt_on(everything: ContentLibrary, model: str) -> Callable[[], Any]:
    return lambda: Game.from_content(everything, NAMES[:2], seed=5, rng_model=model).state


def test_a_model_two_recording_is_format_three_and_plays_back(everything: ContentLibrary) -> None:
    recording = recorded(everything, "2")

    assert recording.format_version == KEYED_REPLAY_FORMAT == "3"
    assert recording.rng_model == "2"

    back = Recording.from_dict(json.loads(json.dumps(recording.to_dict())))

    assert back.to_dict() == recording.to_dict()
    assert back.rng_model == "2"
    back.verify()

    player = ReplayPlayer(back, dealt_on(everything, "2"), cards=everything.registry())
    player.play()

    assert player.finished


def test_a_model_two_recording_is_not_played_on_a_model_one_deal(
    everything: ContentLibrary,
) -> None:
    recording = recorded(everything, "2", commands=5)

    with pytest.raises(ReplayFormatError, match="model 2"):
        ReplayPlayer(recording, dealt_on(everything, "1"), cards=everything.registry())


def test_a_model_one_recording_is_the_file_it_always_was(everything: ContentLibrary) -> None:
    recording = recorded(everything, "1")
    written = recording.to_dict()

    assert written["format_version"] == "2"
    assert "rng_model" not in written

    covered = json.dumps(
        {
            "seed": recording.seed,
            "format_version": recording.format_version,
            "content_version": recording.content_version,
            "commands": [command.to_dict() for command in recording.commands],
        },
        sort_keys=True,
        separators=(",", ":"),
    )

    assert recording.checksum == hashlib.sha256(covered.encode("utf-8")).hexdigest()[:32]

    player = ReplayPlayer(recording, dealt_on(everything, "1"), cards=everything.registry())
    player.play()

    assert player.finished


def test_the_model_is_checksummed_on_a_model_two_recording(everything: ContentLibrary) -> None:
    written = recorded(everything, "2", commands=5).to_dict()
    written["rng_model"] = "1"
    written["format_version"] = "2"

    with pytest.raises(Exception, match="checksum"):
        Recording.from_dict(written).verify()


def test_a_recording_that_misstates_its_model_is_refused(everything: ContentLibrary) -> None:
    keyed = recorded(everything, "2", commands=5)
    legacy = recorded(everything, "1", commands=5)

    for wrong in (
        Recording(seed=keyed.seed, commands=keyed.commands, format_version="3"),
        Recording(seed=legacy.seed, commands=legacy.commands, rng_model="2"),
        Recording(seed=legacy.seed, commands=legacy.commands, format_version="3", rng_model="7"),
    ):
        with pytest.raises(ReplayFormatError):
            wrong.check_compatibility()


# ----------------------------------------------------------------------
# The fingerprint
# ----------------------------------------------------------------------


def test_the_model_is_not_a_field_of_the_full_fingerprint(everything: ContentLibrary) -> None:
    game = Game.from_content(everything, NAMES, seed=8)
    game.start()

    before = (state_digest(game.state), state_digest_v2(game.state))
    game.state.rng_model = "2"

    assert (state_digest(game.state), state_digest_v2(game.state)) == before


def test_a_model_two_position_has_a_fingerprint_of_its_own(everything: ContentLibrary) -> None:
    one = Game.from_content(everything, NAMES, seed=8, rng_model="2")
    other = Game.from_content(everything, NAMES, seed=8, rng_model="2")

    for game in (one, other):
        game.start()

    assert isinstance(one.state.rng_state, dict)
    assert state_digest(one.state) == state_digest(other.state)
    assert state_digest_v2(one.state) == state_digest_v2(other.state)

    legacy = Game.from_content(everything, NAMES, seed=8)
    legacy.start()

    assert state_digest_v2(one.state) != state_digest_v2(legacy.state)
