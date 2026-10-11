"""
A card somebody wrote is in the games that test it.

The card under test is looked up in everything FSME loads — the cards it ships
and the author's own sets — and the games that measure it have to be dealt from
the same place. They were not: the run read only the shipped cards, so a card
from `my sets` was found, never dealt, and both runs were the same games. The
verdict was that taking the card out changed nothing, which was true of games
it was never in.

Every test here builds its content under `tmp_path` and points `FSME_HOME` at
it, so no real workspace is read and nothing is written to `content/`.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

import pytest

import fsme.lab.desk as desk_module
from fsme.api import load_content
from fsme.cli.main import content_roots, main
from fsme.lab.desk import Workbench
from fsme.lab.simulation import pool, run_on_many_cores

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"

SET = "trial_set"
CARD = f"{SET}-lucky_penny"

GAMES = 4
"""
Enough games for the card to be played in some of them.

Nothing here is random: the seeds are fixed, the content is fixed and the
card test is played on model 2, so the same games are dealt every time.
"""

PLAYED_IN = re.compile(r"it was played in (\d+) games with it")


@pytest.fixture(scope="module")
def shipped(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """
    A small copy of the shipped cards: the base game and nothing else.
    """
    where = tmp_path_factory.mktemp("shipped")
    shutil.copytree(CONTENT_ROOT / "base_game", where / "base_game")

    return where


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    A workspace of this test's own, holding one set with one card in it.
    """
    where = tmp_path / "FSME"
    monkeypatch.setenv("FSME_HOME", str(where))

    written = where / "my sets" / SET
    written.mkdir(parents=True)

    (written / "manifest.json").write_text(
        json.dumps(
            {"id": SET, "name": "Trial Set", "version": "1.0.0", "schema_version": "1"}
        ),
        encoding="utf-8",
    )
    (written / "cards.json").write_text(
        json.dumps(
            [
                {
                    "id": CARD,
                    "name": "Lucky Penny",
                    "type": "loot",
                    "expansion": SET,
                    "schema_version": "1",
                    "metadata": {"text": "Gain 3¢."},
                    "abilities": [
                        {
                            "trigger": "on_play",
                            "effects": [{"effect": "gain_coins", "amount": 3}],
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    return where


@pytest.fixture
def worker(monkeypatch: pytest.MonkeyPatch) -> Any:
    """
    The pool module, with whatever a test loads into it put back afterwards.
    """
    for name in ("_library", "_roots", "_drop", "_scenario", "_rng_model"):
        monkeypatch.setattr(pool, name, getattr(pool, name))

    return pool


def dealt(module: Any) -> set[str]:
    return {definition.id for definition in module._library.definitions()}


def finished(bench: Workbench, number: int) -> Any:
    until = time.monotonic() + 300

    while time.monotonic() < until:
        job = bench.job(number)

        if job is not None and job.state in ("done", "failed"):
            return job

        time.sleep(0.05)

    raise AssertionError(f"job {number} never finished")


# ----------------------------------------------------------------------
# What a worker loads
# ----------------------------------------------------------------------


def test_a_worker_given_both_places_has_the_authors_card(
    shipped: Path, home: Path, worker: Any
) -> None:
    worker._prepare((str(shipped), str(home / "my sets")), ())

    assert CARD in dealt(worker)
    assert "loot_deck-bombs-base_game-bomb" in dealt(worker)


def test_a_worker_told_to_leave_the_card_out_leaves_it_out(
    shipped: Path, home: Path, worker: Any
) -> None:
    worker._prepare((str(shipped), str(home / "my sets")), (CARD,))

    assert CARD not in dealt(worker)
    assert "loot_deck-bombs-base_game-bomb" in dealt(worker)


def test_a_worker_given_one_place_loads_what_it_always_did(
    shipped: Path, home: Path, worker: Any
) -> None:
    worker._prepare((str(shipped),), ())

    assert dealt(worker) == {
        definition.id for definition in load_content(shipped).definitions()
    }
    assert CARD not in dealt(worker)


# ----------------------------------------------------------------------
# The card test, both ways in
# ----------------------------------------------------------------------


def test_the_command_deals_the_authors_card_into_its_games(
    shipped: Path, home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    asked = [
        "test-card",
        CARD,
        "--content",
        str(shipped),
        "--games",
        str(GAMES),
        "--jobs",
        "1",
        "--json",
    ]

    assert main(asked) == 0

    told = json.loads(capsys.readouterr().out)

    assert told["games"] == GAMES
    assert told["appeared"] > 0, "the card was never played: the runs did not deal it"


def test_the_desk_deals_the_authors_card_into_its_games(
    shipped: Path, home: Path, tmp_path: Path
) -> None:
    roots = content_roots(str(shipped))

    bench = Workbench(load_content(roots), shipped, tmp_path / "work", roots=roots)
    job = finished(bench, bench.test_card(CARD, games=GAMES, players=2, jobs=1).id)

    assert job.state == "done", job.error

    played = PLAYED_IN.search(job.text)

    assert played is not None, job.text
    assert int(played.group(1)) > 0, "the card was never played: the runs did not deal it"


def test_the_desk_is_given_the_places_the_card_was_found_in(
    shipped: Path, home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built: dict[str, Any] = {}

    class Stopped:
        def serve_forever(self) -> None:
            raise KeyboardInterrupt

        def server_close(self) -> None:
            pass

    def build(session: Any, bench: Workbench, **given: Any) -> Stopped:
        built["bench"] = bench
        built["library"] = given["library"]

        return Stopped()

    monkeypatch.setattr(desk_module, "desk", build)

    asked = [
        "desk",
        "--content",
        str(shipped),
        "--port",
        "0",
        "--work",
        str(tmp_path / "work"),
    ]

    assert main(asked) == 0

    bench = built["bench"]

    assert bench.roots == tuple(content_roots(str(shipped)))
    assert home / "my sets" in bench.roots
    assert bench.root == shipped.resolve(), "root is still where the shipped cards are"
    assert CARD in {definition.id for definition in built["library"].definitions()}


def test_a_bench_given_no_roots_plays_from_its_one_root(tmp_path: Path) -> None:
    bench = Workbench(load_content(CONTENT_ROOT), CONTENT_ROOT, tmp_path / "work")

    assert bench.roots == (CONTENT_ROOT,)


# ----------------------------------------------------------------------
# Nothing else moves
# ----------------------------------------------------------------------


def outcomes(given: Any) -> list[tuple[Any, ...]]:
    return sorted(
        (done.seed, done.finished, done.winner, done.turns, done.commands, done.rng_model)
        for done in given
    )


def test_an_empty_or_missing_second_place_changes_no_game(
    shipped: Path, tmp_path: Path
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    alone = outcomes(run_on_many_cores(shipped, 2, 2, jobs=1))

    assert len(alone) == 2
    assert outcomes(run_on_many_cores([shipped, empty], 2, 2, jobs=1)) == alone
    assert outcomes(run_on_many_cores([shipped, tmp_path / "absent"], 2, 2, jobs=1)) == alone
