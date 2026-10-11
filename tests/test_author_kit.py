"""
The examples an author is told to copy.

An example that no longer works is worse than no example: somebody copies it,
it fails, and the first thing they learn about FSME is that its documentation
lies. So every set in `author-kit/` is loaded, validated and **played** here.
Loading is not enough — a card can pass every check in the pipeline and still
do nothing, which is exactly the class of mistake the examples exist to teach
people to avoid.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from fsme.api import load_content
from fsme.cards import CardInstance
from fsme.commands import Command, CommandType
from fsme.game import Game
from fsme.rules import bonus
from fsme.state.modifiers import ATTACK

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "author-kit"
EXAMPLES = KIT / "examples"
TEMPLATE = KIT / "templates" / "empty_expansion"


@pytest.fixture(scope="module")
def library(tmp_path_factory: pytest.TempPathFactory) -> Any:
    """
    The shipped content with the examples beside it, as an author would have.
    """
    root = tmp_path_factory.mktemp("kit") / "root"
    root.mkdir()

    for source in (ROOT / "content").iterdir():
        if source.is_dir():
            shutil.copytree(source, root / source.name)

    for source in EXAMPLES.iterdir():
        if source.is_dir():
            shutil.copytree(source, root / source.name)

    return load_content(root)


def a_game(library: Any) -> Game:
    game = Game.from_content(library, ["a", "b", "c", "d"], seed=5)
    game.start()

    return game


def into_hand(game: Game, library: Any, card_id: str, seat: int = 0) -> CardInstance:
    card = CardInstance(
        definition=library.registry().get(card_id),
        instance_id=game.state.ids.allocate("loot"),
        controller=seat,
        owner=seat,
    )
    game.state.player(seat).hand.add_top(card)

    return card


def play(game: Game, card: CardInstance, seat: int = 0) -> Any:
    index = list(game.state.player(seat).hand.cards).index(card)

    return game.submit(
        Command(type=CommandType.PLAY_LOOT, player=seat, payload={"index": index})
    )


def answer_everything(game: Game) -> None:
    """
    Take the first option of every question, until nothing is being asked.
    """
    for _ in range(20):
        decision = game.runtime.awaiting_decision

        if decision is None:
            return

        game.submit(
            Command(
                type=CommandType.CHOOSE_TARGET,
                player=decision.player,
                payload={"choices": [0]},
            )
        )


# ----------------------------------------------------------------------
# The kit is what it says it is
# ----------------------------------------------------------------------


def test_every_example_is_a_loadable_set() -> None:
    """
    Each example directory is a set in its own right, so it can be copied out
    on its own and still work.
    """
    for example in sorted(EXAMPLES.iterdir()):
        if not example.is_dir():
            continue

        assert (example / "manifest.json").is_file(), example.name

        library = load_content(example.parent)

        assert len(library.registry()) >= 1


def test_the_template_is_an_empty_set_that_loads(tmp_path: Path) -> None:
    """
    Somebody's first act is to copy this. It has to work before they touch it.
    """
    root = tmp_path / "root"
    root.mkdir()
    shutil.copytree(TEMPLATE, root / "my_set")

    library = load_content(root)

    assert len(library.registry()) == 0, "a template ships no cards"
    assert "my_set" in library.expansions


def test_the_readme_does_not_copy_the_vocabulary() -> None:
    """
    A second copy of the reference is a copy that drifts. The kit links to the
    generated one instead, and this is the test that keeps it honest.
    """
    assert not (KIT / "REFERENCE.md").exists()

    readme = (KIT / "README.md").read_text("utf-8")

    assert "docs/REFERENCE.md" in readme


def test_the_examples_load_beside_the_shipped_content(library: Any) -> None:
    assert len(library.registry()) > 1000

    for example in sorted(EXAMPLES.iterdir()):
        if example.is_dir():
            assert json.loads((example / "manifest.json").read_text())["id"] in (
                library.expansions
            )


# ----------------------------------------------------------------------
# Each example does the thing it is an example of
# ----------------------------------------------------------------------


def test_the_simple_loot_example_pays_out(library: Any) -> None:
    game = a_game(library)
    before = game.state.player(0).pennies

    assert play(game, into_hand(game, library, "example_simple_loot-loot-lucky_penny")).accepted

    answer_everything(game)

    assert game.state.player(0).pennies == before + 3


def test_the_simple_treasure_example_changes_a_number(library: Any) -> None:
    game = a_game(library)
    before = bonus(game.state, ATTACK, 0)

    game.state.player(0).treasures.add_top(
        CardInstance(
            definition=library.registry().get(
                "example_simple_treasure-treasure-heavy_boot"
            ),
            instance_id=game.state.ids.allocate("item"),
            controller=0,
            owner=0,
        )
    )

    assert bonus(game.state, ATTACK, 0) == before + 1


def test_the_conditional_example_takes_one_branch(library: Any) -> None:
    """
    Either branch is correct — what matters is that exactly one ran.
    """
    game = a_game(library)
    before = game.state.player(0).pennies

    assert play(
        game, into_hand(game, library, "example_conditional-loot-gamblers_coin")
    ).accepted

    answer_everything(game)

    after = game.state.player(0).pennies

    assert after in (before + 4, before - 1), after


def test_the_choice_example_hurts_somebody_else(library: Any) -> None:
    game = a_game(library)
    before = [game.state.player(seat).hp for seat in range(4)]

    assert play(
        game, into_hand(game, library, "example_choice-loot-shared_burden")
    ).accepted

    answer_everything(game)

    after = [game.state.player(seat).hp for seat in range(4)]

    assert after != before, "somebody took the damage"
    assert after[0] == before[0], "and it was not the player who played it"


def test_the_reference_example_moves_a_card_between_hands(library: Any) -> None:
    """
    The one that needs the reference layer: a player is chosen, and then a card
    is chosen out of *that* player's hand by *that* player.
    """
    game = a_game(library)
    before = [game.state.player(seat).hand_size for seat in range(4)]

    assert play(
        game, into_hand(game, library, "example_reference-loot-pickpocket")
    ).accepted

    answer_everything(game)

    after = [game.state.player(seat).hand_size for seat in range(4)]

    assert after[0] == before[0] + 1, "the card played, and one arrived"
    assert sum(after) == sum(before), "a card moved rather than appeared"
