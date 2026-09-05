"""
The whole loop: a scenario, a game, a journal, and the game again.

The claim this file exists to hold is one sentence — *an experiment is
reproducible from its journal alone* — and the test that means it is the one
that deletes the scenario file before replaying. Everything else here is
support for that.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fsme.api import Session, load_content
from fsme.content import ContentLibrary
from fsme.game import Game
from fsme.journal import JOURNAL_FORMAT_VERSION, Journal, JournalFormatError, replay_journal
from fsme.journal.file import read, wrap
from fsme.lab.bot import HeuristicBot
from fsme.lab.simulation import ScriptedAgent, play_one
from fsme.lab.simulation.runner import NAMES, _whose_move
from fsme.scenario import Content, Scenario, ScenarioError, Seat, Table, digest_of
from fsme.scenario import save as save_scenario

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"

ISAAC = "characters-base_game-isaac"
CAIN = "characters-base_game-cain"


@pytest.fixture(scope="module")
def everything() -> ContentLibrary:
    return load_content(CONTENT_ROOT)


def an_experiment(**over: object) -> Scenario:
    settings: dict = {
        "name": "An experiment",
        "content": Content(expansions=("base_game",)),
        "table": Table(shop_slots=0),
        "players": (Seat(character=ISAAC), Seat(character=CAIN)),
    }
    settings.update(over)

    return Scenario(**settings)


def watched(library: ContentLibrary, seed: int, scenario: Scenario | None):
    """
    A game played the way Watch plays one, journal and all.
    """
    session = Session(library, players=2, seed=seed, scenario=scenario)
    game = session.game
    bot = HeuristicBot(seed)
    agent = ScriptedAgent(seed)

    for _ in range(6000):
        if game.is_over:
            break

        if game.runtime.awaiting_decision is not None:
            answered = agent.choose(game)

            if answered is None:
                break

            command, label = answered
        else:
            thought = bot.choose(game, seats=(_whose_move(game),))

            if thought is None:
                break

            command, label = thought[0], thought[1]

        if not session.submit(
            {
                "type": str(command.type),
                "player": command.player,
                "payload": dict(command.payload),
                "label": label,
            }
        )["accepted"]:
            break

    return session.journal, game


# ----------------------------------------------------------------------
# The loop
# ----------------------------------------------------------------------


def test_a_scenario_reaches_the_journal(everything: ContentLibrary) -> None:
    scenario = an_experiment()

    journal, _ = play_one(everything, seed=13, players=2, scenario=scenario)

    assert journal.scenario == scenario.to_dict()
    assert journal.scenario_digest == digest_of(scenario)
    assert journal.content_version == "base_game@1.0.0"
    assert journal.interactive_priority is False


def test_an_ordinary_game_records_no_scenario(everything: ContentLibrary) -> None:
    """
    A journal of a game nobody configured says so by having nothing to say.
    """
    journal, _ = play_one(everything, seed=13, players=2)

    assert journal.scenario is None
    assert journal.scenario_digest == ""

    written = journal.to_dict()

    assert "scenario" not in written
    assert "scenario_digest" not in written


def test_an_experiment_replays_from_its_journal(everything: ContentLibrary) -> None:
    scenario = an_experiment()

    journal, game = play_one(everything, seed=13, players=2, scenario=scenario)

    assert game.is_over

    playback = replay_journal(journal, everything)

    assert playback.faithful, str(playback.divergence)
    assert playback.replayed == len(journal.entries)


def test_an_experiment_replays_after_its_scenario_file_is_gone(
    everything: ContentLibrary, tmp_path: Path
) -> None:
    """
    The sentence this whole layer is for.

    The scenario is written to a file, the game is set up from what was read
    back, the journal is saved, the file is deleted — and a different file is
    written in its place, so that a replay quietly reaching for it would come
    back with the wrong answer rather than no answer.
    """
    from fsme.scenario import load as read_scenario

    where = save_scenario(an_experiment(), tmp_path / "experiment.json")
    scenario = read_scenario(where)

    journal, game = play_one(everything, seed=13, players=2, scenario=scenario)

    assert game.is_over

    kept = tmp_path / "kept.json"
    kept.write_text(json.dumps(wrap(journal)), encoding="utf-8")

    save_scenario(
        Scenario(name="a different experiment", table=Table(souls_to_win=1)),
        where,
    )

    reopened = read(kept)

    assert reopened.scenario == scenario.to_dict()

    playback = replay_journal(reopened, everything)

    assert playback.faithful, str(playback.divergence)
    assert playback.replayed == len(journal.entries)


def test_a_watched_experiment_replays_too(everything: ContentLibrary) -> None:
    """
    The other shape of journal, which records the deal as its first command.
    """
    scenario = an_experiment()

    journal, game = watched(everything, 4, scenario)

    assert game.is_over
    assert journal.entries[0].command == "start_game"
    assert journal.scenario == scenario.to_dict()
    assert journal.interactive_priority is True

    playback = replay_journal(journal, everything)

    assert playback.faithful, str(playback.divergence)


def test_replay_believes_the_journal_rather_than_guessing(
    everything: ContentLibrary,
) -> None:
    """
    A Watch journal was inferred to be interactive from the fact that it
    records a deal. Now it says so, and that is what is read.
    """
    journal, _ = watched(everything, 4, None)

    assert journal.interactive_priority is True

    journal.interactive_priority = False

    playback = replay_journal(journal, everything)

    assert not playback.faithful, "believed, not inferred"


# ----------------------------------------------------------------------
# Telling experiments apart
# ----------------------------------------------------------------------


def test_two_experiments_on_one_seed_are_two_games(
    everything: ContentLibrary,
) -> None:
    one = an_experiment(players=(Seat(character=ISAAC), Seat(character=CAIN)))
    other = an_experiment(players=(Seat(character=CAIN), Seat(character=ISAAC)))

    first, _ = play_one(everything, seed=13, players=2, scenario=one)
    second, _ = play_one(everything, seed=13, players=2, scenario=other)

    assert first.scenario_digest != second.scenario_digest
    assert first.to_dict() != second.to_dict()


def test_one_experiment_on_one_seed_is_one_game(everything: ContentLibrary) -> None:
    scenario = an_experiment()

    runs = [
        play_one(everything, seed=13, players=2, scenario=scenario)[0]
        for _ in range(3)
    ]

    for other in runs[1:]:
        assert other.to_dict() == runs[0].to_dict()


def test_the_same_experiment_written_two_ways_fingerprints_the_same() -> None:
    assert digest_of(an_experiment()) == digest_of(an_experiment())
    assert digest_of(Scenario()) == ""


# ----------------------------------------------------------------------
# The format, forwards and backwards
# ----------------------------------------------------------------------


def test_the_format_is_two() -> None:
    assert JOURNAL_FORMAT_VERSION == "2"


def test_a_journal_from_before_scenarios_still_reads(
    everything: ContentLibrary,
) -> None:
    """
    A version-1 journal has no scenario, which is true about it rather than
    missing from it. It reads, it replays, and it says so.
    """
    journal, _ = play_one(everything, seed=13, players=2)

    old = journal.to_dict()
    old["format"] = "1"
    old.pop("scenario_digest", None)
    old.pop("interactive_priority", None)

    back = Journal.from_dict(old)

    assert back.scenario is None
    assert back.scenario_digest == ""
    assert back.interactive_priority is None, "the journal does not say"

    playback = replay_journal(back, everything)

    assert playback.faithful, str(playback.divergence)


def test_a_journal_from_the_future_is_refused_by_name(
    everything: ContentLibrary,
) -> None:
    journal, _ = play_one(everything, seed=13, players=2)

    ahead = journal.to_dict()
    ahead["format"] = "3"

    with pytest.raises(JournalFormatError) as raised:
        Journal.from_dict(ahead)

    said = str(raised.value)

    assert "format 3" in said
    assert "reads 1, 2" in said


def test_a_journal_whose_scenario_was_tampered_with_is_refused(
    everything: ContentLibrary,
) -> None:
    """
    The snapshot is data somebody may have edited. It is parsed, not trusted.
    """
    journal, _ = play_one(everything, seed=13, players=2, scenario=an_experiment())

    assert journal.scenario is not None

    journal.scenario = dict(journal.scenario) | {"version": 99}

    with pytest.raises(ScenarioError) as raised:
        replay_journal(journal, everything)

    assert "recorded in this journal" in str(raised.value)


def test_a_journal_survives_a_file_with_its_scenario(
    everything: ContentLibrary, tmp_path: Path
) -> None:
    journal, _ = play_one(everything, seed=13, players=2, scenario=an_experiment())

    where = tmp_path / "kept.json"
    where.write_text(json.dumps(wrap(journal)), encoding="utf-8")

    assert read(where).to_dict() == journal.to_dict()


# ----------------------------------------------------------------------
# Nothing changed for anybody else
# ----------------------------------------------------------------------


@pytest.mark.parametrize("seed", (3, 21))
def test_a_game_with_no_scenario_still_plays_the_same_game(
    everything: ContentLibrary, seed: int
) -> None:
    """
    Journal v2 adds fields; it must not add a game.
    """
    journal, _ = play_one(everything, seed=seed, players=2)

    entries = journal.to_dict()["entries"]

    direct = Game.from_content(everything, list(NAMES[:2]), seed=seed)
    direct.start()

    assert entries, "a game happened"
    assert journal.seed == seed
    assert replay_journal(journal, everything).faithful


def test_analysis_reads_an_experiment_like_any_other_game(
    everything: ContentLibrary,
) -> None:
    from fsme.lab.analysis import summarise
    from fsme.lab.analysis.risk import risks

    journal, _ = play_one(
        everything, seed=13, players=2, thinking_seats=(0,), scenario=an_experiment()
    )

    assert summarise(journal)

    told = risks(journal, everything)

    assert told.faithful
    assert told.weighed > 0


def test_a_watched_game_can_be_weighed_now(everything: ContentLibrary) -> None:
    """
    `risks` dealt the game itself and then met the journal's own `start_game`,
    so a Watch journal produced nothing at all. It reads the journal the way
    replay does now.
    """
    from fsme.lab.analysis.risk import risks

    journal, _ = watched(everything, 4, None)
    told = risks(journal, everything)

    assert told.faithful
    assert told.weighed > 0


# ----------------------------------------------------------------------
# Across processes
# ----------------------------------------------------------------------


def test_a_scenario_crosses_a_process_boundary(tmp_path: Path) -> None:
    """
    A study hands its workers a content root and plain data, never a library
    and never an object with behaviour. The scenario goes as what it was read
    from and is parsed again on the other side.
    """
    from fsme.lab.simulation import run_on_many_cores

    scenario = an_experiment()

    finished = list(
        run_on_many_cores(
            CONTENT_ROOT,
            games=2,
            players=2,
            jobs=2,
            first_seed=13,
            scenario=scenario.to_dict(),
        )
    )

    assert len(finished) == 2

    for done in finished:
        assert not done.broke, done.broke

    alone, _ = play_one(everything_once(), seed=13, players=2, scenario=scenario)
    matching = [done for done in finished if done.seed == 13]

    assert matching[0].commands == len(alone.entries)
    assert matching[0].winner == alone.outcome.get("winner")


_LOADED: ContentLibrary | None = None


def everything_once() -> ContentLibrary:
    global _LOADED

    if _LOADED is None:
        _LOADED = load_content(CONTENT_ROOT)

    return _LOADED
