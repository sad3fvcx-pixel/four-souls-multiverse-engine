"""
Saving a game and loading it back.

SAVE_SYSTEM.md asks for a save that is lossless: loading one must produce a
game that continues exactly as the saved one would have. That is a claim about
the future, not about the file, so it is tested as one — a saved game and the
game it was saved from are played on side by side, and they must stay the same
game.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import pytest
from test_soak import play, step

from fsme.commands import Command, CommandType
from fsme.content import ContentLibrary, ContentLoader
from fsme.game import Game
from fsme.replay import state_digest
from fsme.runtime.vocabulary import engine_vocabulary
from fsme.serialization import SAVE_FORMAT_VERSION, SaveError, load_game, save_game

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return ContentLoader(engine_vocabulary()).load_root(CONTENT_ROOT)


def written(game: Game) -> dict[str, Any]:
    """
    Save a game and read it back through JSON, as a file would.
    """
    return dict(json.loads(json.dumps(game.save(engine_version="test"))))


def test_a_fresh_game_survives_a_round_trip(everything: ContentLibrary) -> None:
    game = Game.from_content(everything, ["Ann", "Bo"], seed=3)

    assert game.start().accepted

    back = Game.load(written(game), everything)

    assert state_digest(back.state) == state_digest(game.state)


@pytest.mark.parametrize("seed", (5, 11, 23))
def test_a_game_in_progress_survives_a_round_trip(
    everything: ContentLibrary, seed: int
) -> None:
    game = play(everything, seed, 3, steps=80)

    back = Game.load(written(game), everything)

    assert state_digest(back.state) == state_digest(game.state)


@pytest.mark.parametrize("seed", (5, 11))
def test_a_loaded_game_plays_on_the_same(
    everything: ContentLibrary, seed: int
) -> None:
    """
    The claim a save actually makes: what happens next is the same.
    """
    game = play(everything, seed, 3, steps=80)
    back = Game.load(written(game), everything)

    here, there = random.Random(seed + 1), random.Random(seed + 1)

    for _ in range(80):
        step(game, here)
        step(back, there)

    assert state_digest(back.state) == state_digest(game.state)


def test_the_cards_come_back_as_themselves(everything: ContentLibrary) -> None:
    game = play(everything, 5, 3, steps=60)
    back = Game.load(written(game), everything)

    for before, after in zip(game.state.players, back.state.players, strict=True):
        assert [card.instance_id for card in before.hand.cards] == [
            card.instance_id for card in after.hand.cards
        ]
        assert [card.id for card in before.treasures.cards] == [
            card.id for card in after.treasures.cards
        ]

    # One object per identifier, and the loaded game points at its own cards.
    seen: dict[str, Any] = {}

    for zone in (
        back.state.loot_deck,
        back.state.treasure_deck,
        back.state.active_monsters,
        *(player.hand for player in back.state.players),
        *(player.treasures for player in back.state.players),
    ):
        for card in zone.cards:
            assert card.instance_id not in seen, "one card, two objects"
            seen[card.instance_id] = card

    # Equal by value, and never the same object: a loaded game shares nothing
    # with the one it was saved from.
    for card in back.state.active_monsters.cards:
        assert all(card is not other for other in game.state.active_monsters.cards)


def test_what_a_card_did_to_another_card_is_kept(everything: ContentLibrary) -> None:
    """
    Counters, copies, tapping and the rest are the card's history, not its face.
    """
    game = Game.from_content(everything, ["Ann", "Bo"], seed=3)

    assert game.start().accepted

    item = game.state.player(0).treasures.cards[0]

    item.tapped = True
    item.counters["gold"] = 2
    item.eternal = True
    item.silenced_while = "poo"
    item.recharge_skipped = True
    item.copy_of = game.runtime.cards.get("treasure_deck-passive_items-base_game-breakfast")
    item.copy_expires = "end_of_turn"

    back = Game.load(written(game), everything)

    restored = back.state.player(0).treasures.cards[0]

    assert restored.tapped
    assert restored.counters == {"gold": 2}
    assert restored.eternal
    assert restored.silenced_while == "poo"
    assert restored.recharge_skipped
    assert restored.copy_of is not None
    assert restored.copy_of.id == item.copy_of.id
    assert restored.copy_expires == "end_of_turn"


def test_what_the_game_owes_is_kept(everything: ContentLibrary) -> None:
    """
    Promises, watchers, shields, obligations and bonuses all outlive a save.
    """
    game = Game.from_content(everything, ["Ann", "Bo"], seed=3)

    assert game.start().accepted

    context = game.runtime.context

    context._set_actor(0)
    context.apply("prevent_next_damage", [game.state.player(0)], amount=1, label="hat")
    context.apply(
        "promise",
        [],
        event="before_loot_draw",
        changes={"count": {"factor": 2}},
    )
    context.apply(
        "watch_for",
        [],
        event="after_roll",
        effects=[{"draw_loot": 1}],
    )
    context.apply("add_modifier", [game.state.player(0)], stat="attack", amount=1)
    context.apply("require_attack", [], times=1)
    game.runtime.run()

    back = Game.load(written(game), everything)

    assert len(back.state.shields) == 1
    assert back.state.shields[0].label == "hat"

    assert len(back.state.promises) == 1
    assert back.state.promises[0].changes == {"count": {"factor": 2}}

    assert len(back.state.watchers) == 1
    assert back.state.watchers[0].event == "after_roll"

    assert [(m.stat, m.amount) for m in back.state.modifiers] == [("attack", 1)]
    assert len(back.state.turn.obligations) == 1


def test_a_game_waiting_inside_an_ability_will_not_be_saved(
    everything: ContentLibrary,
) -> None:
    """
    An ability halfway through is the interpreter's working, not the game's.

    It is rebuilt from the card every time an ability resolves and is written
    down nowhere, so a save taken now could not promise to continue the same
    way. The engine says so instead of pretending.
    """
    game = Game.from_content(everything, ["Ann", "Bo", "Cy"], seed=3)

    assert game.start().accepted

    while game.runtime.awaiting_decision is None:
        # Bomb! asks who to throw it at, which suspends the ability.
        card = game.runtime.cards.get("loot_deck-bombs-base_game-bomb")

        from fsme.cards import CardInstance

        bomb = CardInstance(
            definition=card,
            instance_id=game.state.ids.allocate("loot"),
            controller=0,
            owner=0,
        )

        game.state.player(0).hand.add_top(bomb)
        game.state.player(0).additional_loot_plays += 1

        index = list(game.state.player(0).hand.cards).index(bomb)

        assert game.submit(
            Command(type=CommandType.PLAY_LOOT, player=0, payload={"index": index})
        ).accepted

    with pytest.raises(SaveError, match="waiting inside an ability"):
        game.save()


def test_a_save_from_another_format_is_refused(everything: ContentLibrary) -> None:
    game = Game.from_content(everything, ["Ann", "Bo"], seed=3)

    assert game.start().accepted

    data = written(game)
    data["format"] = "not-this-one"

    with pytest.raises(SaveError, match="format"):
        Game.load(data, everything)


def test_a_save_naming_a_card_the_content_lacks_is_refused(
    everything: ContentLibrary,
) -> None:
    game = Game.from_content(everything, ["Ann", "Bo"], seed=3)

    assert game.start().accepted

    data = written(game)
    data["zones"]["loot_deck"]["cards"][0]["id"] = "nothing.like.this"

    with pytest.raises(SaveError, match="does not have"):
        Game.load(data, everything)


def test_the_format_is_written_down(everything: ContentLibrary) -> None:
    game = Game.from_content(everything, ["Ann", "Bo"], seed=3)

    assert game.start().accepted

    data = written(game)

    assert data["format"] == SAVE_FORMAT_VERSION
    assert data["engine"] == "test"
    assert data["seed"] == 3


def test_the_plain_functions_work_without_the_facade(
    everything: ContentLibrary,
) -> None:
    """
    A save is data and a load is a function; the session object is a
    convenience, not the interface.
    """
    game = play(everything, 7, 2, steps=40)

    data = save_game(
        game.state, engine_version="bare", rng_state=game.runtime.rng.get_state()
    )
    state = load_game(json.loads(json.dumps(data)), everything.registry())

    assert state_digest(state) == state_digest(game.state)
