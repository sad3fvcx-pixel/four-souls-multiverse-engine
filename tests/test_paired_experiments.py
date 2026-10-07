"""
A card test is two games that are one game until the card does something.

On RNG model 2 the same seed deals the same game with a card in the content and
without it, down to the order of every other card in every deck, and the two go
on being the same game until the card under test is drawn, shown, chosen from
or moved. This file holds the card test to that, holds every step of the way
there to carrying the model it was asked for, and holds model 1 — still what
everything else is played on — to being exactly what it was.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import fsme.lab.simulation as simulation
from fsme.api import load_content
from fsme.cli.main import main
from fsme.content import ContentLibrary
from fsme.game import Game
from fsme.journal import Journal, JournalKeeper
from fsme.lab.analysis import Tally, compare, read_out, risks
from fsme.lab.desk import Workbench
from fsme.lab.simulation import (
    PAIRED_RNG_MODEL,
    Finished,
    ScriptedAgent,
    play_one,
    run,
    run_on_many_cores,
)
from fsme.lab.simulation.runner import NAMES, _whose_move

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"

UNDER_TEST = (
    "loot_deck-bombs-base_game-bomb",
    "treasure_deck-active_items-base_game-guppy_s_paw",
    "monster_deck-bosses-base_game-famine",
)
SEEDS = (0, 1, 2, 3)
COMMANDS = 400
DECKS = ("loot_deck", "treasure_deck", "monster_deck", "room_deck")
PILES = DECKS + ("loot_discard", "treasure_discard", "monster_discard", "room_discard")
INSTANCE = re.compile(r"[a-z_]+:\d+")

RESHUFFLED = "reshuffles every game"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


# ----------------------------------------------------------------------
# Comparing two games card by card
# ----------------------------------------------------------------------


def named(card: Any) -> str:
    # A soul token is not a card and has no definition; its number is the same
    # bookkeeping an instance id is, so it is named by what it is.
    return str(getattr(card, "id", type(card).__name__))


def ids(zone: Any) -> tuple[str, ...]:
    return tuple(named(card) for card in zone.cards)


def position(game: Game, gone: str) -> tuple[Any, ...]:
    """
    Everything a game is, by card definition and with one card left out.

    By definition because instance ids are numbered as the deck is made, and a
    deck with one card fewer numbers every card after it differently: that is
    bookkeeping, not a difference between the games.
    """
    state = game.state

    def without(cards: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(card for card in cards if card != gone)

    return (
        tuple(
            (
                player.hp,
                player.max_hp,
                player.pennies,
                player.alive,
                named(player.character) if player.character is not None else None,
                without(ids(player.hand)),
                without(ids(player.treasures)),
                without(ids(player.souls)),
                without(ids(player.curses)),
            )
            for player in state.players
        ),
        (state.turn.turn_number, state.turn.active_player, str(state.turn.phase)),
        tuple(without(tuple(named(card) for card in slot.cards)) for slot in state.monster_area),
        without(ids(state.treasure_shop)),
        without(ids(state.room_area)),
        without(ids(state.bonus_souls)),
        tuple(without(ids(getattr(state, pile))) for pile in PILES),
        (state.game_over, state.winner),
    )


def happened(keeper: JournalKeeper) -> tuple[Any, ...]:
    entry = keeper.journal.entries[-1]

    return (
        entry.command,
        entry.player,
        INSTANCE.sub("#", repr(sorted(dict(entry.payload).items()))),
        tuple(
            (
                event.type,
                event.source_id,
                INSTANCE.sub("#", repr(sorted(dict(event.payload).items()))),
            )
            for event in entry.events
        ),
    )


class Watch:
    """
    Whether the card under test could have made a difference yet.

    Erring early is allowed and erring late is not: everything before the first
    time this says yes is compared, so a watch that said yes too soon only
    compares less. It says yes when the card is anywhere but its own deck, is
    one of the options of a question, is named by an event, or has had the
    cards under it in its deck change — which is the card being moved, a card
    being put beneath it, or its deck being shuffled.
    """

    def __init__(self, game: Game, card: str) -> None:
        self.card = card
        self.name = game.runtime.cards.get(card).name
        self.deck = next(
            (deck for deck in DECKS if card in ids(getattr(game.state, deck))), None
        )
        self.under = self._under(game)

    def _under(self, game: Game) -> int | None:
        if self.deck is None:
            return None

        cards = ids(getattr(game.state, self.deck))

        return cards.index(self.card) if self.card in cards else None

    def asked(self, game: Game) -> bool:
        waiting = game.state.pending_decision

        return waiting is not None and any(
            getattr(option, "id", None) == self.card for option in waiting.options
        )

    def touched(self, game: Game, keeper: JournalKeeper) -> bool:
        if self.deck is None or self._under(game) is None:
            return True

        if self._under(game) != self.under:
            return True

        entries = keeper.journal.entries

        for event in entries[-1].events if entries else ():
            if event.source_id == self.card or repr(self.name) in repr(dict(event.payload)):
                return True

        return False


def dealt(library: ContentLibrary, seed: int, model: str) -> tuple[Game, JournalKeeper]:
    game = Game.from_content(library, NAMES, seed=seed, rng_model=model)
    game.start()

    return game, JournalKeeper(game)


def paired_until_touched(
    everything: ContentLibrary, seed: int, card: str
) -> tuple[int, bool]:
    """
    Play the game with the card and without it, side by side, and compare them
    after every command until the card could have mattered.

    Returns how many commands were compared, and whether the card ever could.
    """
    whole, whole_keeper = dealt(everything, seed, PAIRED_RNG_MODEL)
    less, less_keeper = dealt(everything.without([card]), seed, PAIRED_RNG_MODEL)

    watch = Watch(whole, card)

    if watch.deck is None or watch.touched(whole, whole_keeper):
        return 0, True

    assert position(whole, card) == position(less, card), "the deal already differs"

    whole_agent, less_agent = ScriptedAgent(seed), ScriptedAgent(seed)

    for index in range(COMMANDS):
        if whole.is_over or less.is_over:
            assert whole.is_over and less.is_over, index
            return index, False

        if watch.asked(whole):
            return index, True

        one = whole_agent.choose(whole, seats=(_whose_move(whole),))
        other = less_agent.choose(less, seats=(_whose_move(less),))

        assert one is not None and other is not None
        assert (one[0].type, one[0].player, dict(one[0].payload)) == (
            other[0].type,
            other[0].player,
            dict(other[0].payload),
        ), f"command {index} was chosen differently before the card did anything"

        whole_keeper.submit(one[0], label=one[1])
        less_keeper.submit(other[0], label=other[1])

        if watch.touched(whole, whole_keeper):
            return index, True

        assert happened(whole_keeper) == happened(less_keeper), (
            f"command {index} came out differently before the card did anything"
        )
        assert position(whole, card) == position(less, card), (
            f"the games parted after command {index} before the card did anything"
        )

    return COMMANDS, False


@pytest.mark.parametrize("card", UNDER_TEST)
def test_on_model_two_a_card_changes_nothing_until_it_does_something(
    everything: ContentLibrary, card: str
) -> None:
    compared = [paired_until_touched(everything, seed, card) for seed in SEEDS]

    assert sum(count for count, _ in compared) > 0, "nothing was compared at all"


def test_a_card_that_never_mattered_left_the_whole_game_alone(
    everything: ContentLibrary,
) -> None:
    """
    At least one pair where the card was never touched, compared to the end.
    """
    untouched = [
        (seed, card)
        for card in UNDER_TEST
        for seed in SEEDS
        if not paired_until_touched(everything, seed, card)[1]
    ]

    assert untouched, "every card was touched in every game; pick another card"


@pytest.mark.parametrize("card", UNDER_TEST)
def test_on_model_one_taking_the_card_out_deals_its_deck_again(
    everything: ContentLibrary, card: str
) -> None:
    """
    Why model 2 exists. On model 1 the deck the card came out of is another
    deck — every pair, before anybody has moved — while on model 2 it is the
    same deck with one card fewer.
    """
    compared = 0

    for seed in SEEDS:
        for model, same in (("1", False), (PAIRED_RNG_MODEL, True)):
            whole, _ = dealt(everything, seed, model)
            less, _ = dealt(everything.without([card]), seed, model)

            # A card dealt straight to a hand or the board is not in a deck to
            # compare; that seed says nothing either way.
            deck = next(
                (deck for deck in DECKS if card in ids(getattr(whole.state, deck))), None
            )

            if deck is None:
                continue

            kept = tuple(one for one in ids(getattr(whole.state, deck)) if one != card)

            assert (kept == ids(getattr(less.state, deck))) is same, (seed, model)
            compared += 1

    assert compared, "the card was never in a deck to compare"


# ----------------------------------------------------------------------
# The model is carried, and model 1 stays what it was
# ----------------------------------------------------------------------


def test_the_paired_model_is_model_two() -> None:
    assert PAIRED_RNG_MODEL == "2"


def test_a_game_is_played_on_model_two_unless_a_run_asks(everything: ContentLibrary) -> None:
    plain, plain_game = play_one(everything, 3, 2, steps=120)
    named_two, named_game = play_one(everything, 3, 2, steps=120, rng_model="2")

    assert plain_game.state.rng_model == named_game.state.rng_model == "2"
    assert plain.to_dict() == named_two.to_dict()

    _, legacy_game = play_one(everything, 3, 2, steps=120, rng_model="1")

    assert legacy_game.state.rng_model == "1"

    one = [outcome.journal.to_dict() for outcome in run(everything, 2, 2, steps=80)]
    other = [
        outcome.journal.to_dict() for outcome in run(everything, 2, 2, steps=80, rng_model="2")
    ]

    assert one == other
    assert all(journal["format"] == "4" and journal["rng_model"] == "2" for journal in one)

    legacy = [outcome.journal for outcome in run(everything, 2, 2, steps=80, rng_model="1")]

    assert all(journal.rng_model == "1" for journal in legacy)
    assert all(journal.to_dict()["format"] == "3" for journal in legacy)


def played_on_many_cores(tmp_path: Path, **asked: Any) -> tuple[list[Finished], list[Any]]:
    tmp_path.mkdir(parents=True, exist_ok=True)

    done = sorted(
        run_on_many_cores(
            CONTENT_ROOT, 2, 2, jobs=1, steps=200, journals_into=tmp_path, **asked
        ),
        key=lambda finished: finished.seed,
    )
    written = [
        json.loads(path.read_text("utf-8")) for path in sorted(tmp_path.glob("game-*.json"))
    ]

    return done, written


def test_a_run_on_many_cores_carries_the_model_into_every_worker(tmp_path: Path) -> None:
    done, written = played_on_many_cores(tmp_path / "keyed", rng_model="2")

    assert [finished.rng_model for finished in done] == ["2", "2"]
    assert len(written) == 2
    assert all(journal["format"] == "4" and journal["rng_model"] == "2" for journal in written)
    assert all(Journal.from_dict(journal).rng_model == "2" for journal in written)


def test_a_run_on_many_cores_is_model_two_unless_it_asks(tmp_path: Path) -> None:
    plain, plain_written = played_on_many_cores(tmp_path / "plain")
    named_two, named_written = played_on_many_cores(tmp_path / "named", rng_model="2")

    assert [finished.rng_model for finished in plain] == ["2", "2"]
    assert all(journal["format"] == "4" for journal in plain_written)
    assert plain_written == named_written
    assert [finished.tally.to_dict() for finished in plain] == [
        finished.tally.to_dict() for finished in named_two
    ]

    legacy, legacy_written = played_on_many_cores(tmp_path / "legacy", rng_model="1")

    assert [finished.rng_model for finished in legacy] == ["1", "1"]
    assert all(
        journal["format"] == "3" and "rng_model" not in journal for journal in legacy_written
    )


# ----------------------------------------------------------------------
# The card test
# ----------------------------------------------------------------------


def forgetful(*_: Any, **__: Any) -> Iterator[Finished]:
    """A pool that lost the model on the way and played model 1."""
    yield Finished(
        seed=0, finished=True, winner=0, turns=1, commands=1, tally=Tally(), rng_model="1"
    )


def test_a_card_test_refuses_a_game_from_another_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(simulation, "run_on_many_cores", forgetful)

    with pytest.raises(RuntimeError, match="RNG model 1, not model 2"):
        main(["test-card", UNDER_TEST[0], "--games", "1"])


def test_the_desk_card_test_refuses_a_game_from_another_model(
    everything: ContentLibrary, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(simulation, "run_on_many_cores", forgetful)

    bench = Workbench(everything, CONTENT_ROOT, tmp_path / "work")
    job = finished(bench, bench.test_card(UNDER_TEST[0], games=1, players=2, jobs=1).id)

    assert job.state == "failed"
    assert "RNG model 1, not model 2" in str(job.error)


def test_a_card_test_is_played_on_model_two_and_says_so(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["test-card", UNDER_TEST[0], "--games", "2", "--json"]) == 0

    told = json.loads(capsys.readouterr().out)

    assert told["rng_model"] == "2"
    assert RESHUFFLED not in json.dumps(told)

    assert main(["test-card", UNDER_TEST[0], "--games", "2"]) == 0

    said = capsys.readouterr().out

    assert "played on RNG model 2" in said
    assert RESHUFFLED not in said
    assert "the rest of the difference is the deck" not in said


def finished(bench: Workbench, number: int) -> Any:
    import time

    until = time.monotonic() + 120

    while time.monotonic() < until:
        job = bench.job(number)

        if job is not None and job.state in ("done", "failed"):
            return job

        time.sleep(0.02)

    raise AssertionError(f"job {number} never finished")


def test_the_desk_card_test_is_played_on_model_two(
    everything: ContentLibrary, tmp_path: Path
) -> None:
    bench = Workbench(everything, CONTENT_ROOT, tmp_path / "work")
    job = finished(bench, bench.test_card(UNDER_TEST[0], games=2, players=2, jobs=1).id)

    assert job.state == "done", job.error
    assert "played on RNG model 2" in job.text
    assert RESHUFFLED not in job.text


def test_a_comparison_has_to_be_told_its_model() -> None:
    """
    What the runs were played on is known to whoever played them, and to
    nobody else — least of all the default a new game happens to be dealt on.
    """
    with pytest.raises(TypeError):
        compare("a card", Tally(), Tally(), appeared=0)  # type: ignore[call-arg]


def test_a_comparison_on_model_one_still_says_what_it_said() -> None:
    scarce = compare("a card", Tally(), Tally(), appeared=0, rng_model="1")

    assert scarce.rng_model == "1"
    assert scarce.to_dict()["rng_model"] == "1"
    assert "played on RNG model" not in read_out(scarce)

    one = Tally()
    one.games = 20

    rarely = compare("a card", one, one, appeared=1, rng_model="1")

    assert RESHUFFLED in read_out(rarely)
    assert rarely.verdict.endswith("the rest of the difference is the deck")

    keyed = compare("a card", one, one, appeared=1, rng_model="2")

    assert RESHUFFLED not in read_out(keyed)
    assert "the deck" not in keyed.verdict
    assert [difference.to_dict() for difference in keyed.differences] == [
        difference.to_dict() for difference in rarely.differences
    ], "the model changes the words, never the numbers"


# ----------------------------------------------------------------------
# Weighing the moves of a model 2 game
# ----------------------------------------------------------------------


def kept(everything: ContentLibrary, model: str) -> Journal:
    game, keeper = dealt(everything, 6, model)
    agent = ScriptedAgent(6)

    for _ in range(60):
        if game.is_over:
            break

        chosen = agent.choose(game, seats=(_whose_move(game),))
        assert chosen is not None
        keeper.submit(chosen[0], label=chosen[1])

    return keeper.journal


def test_a_model_two_journal_is_weighed_on_model_two(everything: ContentLibrary) -> None:
    journal = Journal.from_dict(json.loads(json.dumps(kept(everything, "2").to_dict())))

    assert journal.rng_model == "2"
    assert risks(journal, everything).faithful


def test_a_model_one_journal_is_weighed_as_it_always_was(everything: ContentLibrary) -> None:
    journal = kept(everything, "1")

    told = risks(journal, everything)

    assert told.faithful
    assert told.to_dict() == risks(Journal.from_dict(journal.to_dict()), everything).to_dict()
