"""
What the engine says when a game refuses to settle.

Stopping a loop is old behaviour and is tested with the replacements. What is
tested here is the *message*: two cards triggering each other for ever look
exactly like a slow game from the outside, and which of those it is decides
whether the next step is a rules question or a performance one. An error that
only said "gave up" left whoever found it nothing to look at.

The content case is real and reproducible, and is here as evidence rather than
as a fixture: Placebo copies the ability of an item, Rainbow Tapeworm becomes a
copy of an item, and together they copy each other without end. The rules say
nothing about infinite loops, so the engine does not invent a way out of one —
it names what was happening and stops. That gap is recorded in
`docs/PROJECT_PLAN.md` §11.5.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fsme.api import load_content
from fsme.content import ContentLibrary
from fsme.lab.simulation import play_one
from fsme.runtime import StabilityError
from fsme.runtime.runtime import _name_of, _what_was_looping

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"

LOOPING_SEEDS = (8, 58)

GUPPYS_PAW = "treasure_deck-active_items-base_game-guppy_s_paw"


@pytest.fixture(scope="module")
def without_a_card() -> ContentLibrary:
    # The deal that reaches the loop: taking any card out reshuffles every
    # game, and these two seeds are the ones that land on it.
    return load_content(CONTENT_ROOT).without({GUPPYS_PAW})


@pytest.mark.parametrize("seed", LOOPING_SEEDS)
def test_a_game_that_will_not_settle_names_what_kept_happening(
    without_a_card: ContentLibrary, seed: int
) -> None:
    with pytest.raises(StabilityError) as raised:
        play_one(without_a_card, seed, 2)

    said = str(raised.value)

    assert "did not stabilise" in said
    assert "Still arriving when it gave up" in said

    # The two cards that are actually copying each other, by name.
    assert "Placebo" in said
    assert "Rainbow Tapeworm" in said


def test_a_run_that_settled_is_charged_nothing_for_the_witness(
    without_a_card: ContentLibrary,
) -> None:
    # Only the tail of the step budget is recorded, so an ordinary game never
    # builds the list at all.
    journal, game = play_one(without_a_card, 3, 2)

    assert len(journal) > 0
    assert game.state.game_over


def test_nothing_is_said_when_nothing_repeated() -> None:
    assert _what_was_looping([]) == ""

    # A game can hit the limit by being long rather than by looping, and
    # inventing a culprit for it would be worse than saying nothing.
    assert _what_was_looping(["a", "b", "c", "d"]) == ""


def test_what_repeated_is_said_with_its_count() -> None:
    said = _what_was_looping(["push(A)"] * 5 + ["pull(B)"] * 4)

    assert "push(A) ×5" in said
    assert "pull(B) ×4" in said


def test_an_event_is_named_by_its_source_when_it_has_one() -> None:
    class Card:
        name = "Placebo"

    class Event:
        type = "stack_push"
        source = Card()

    class Anonymous:
        type = "turn_start"
        source = None

    assert _name_of(Event()) == "stack_push(Placebo)"
    assert _name_of(Anonymous()) == "turn_start"
