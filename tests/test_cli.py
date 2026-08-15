"""
The command line.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from fsme.cli.main import content_root, main

# ``fsme.cli`` re-exports ``main`` the function, which shadows ``main`` the
# module on the package, so the module is taken from the import table instead.
entry_point = sys.modules["fsme.cli.main"]

CONTENT_ROOT = Path(__file__).resolve().parents[1] / "content"


def test_the_content_is_found_beside_the_source() -> None:
    assert content_root(None) == CONTENT_ROOT.resolve()


def test_a_named_content_directory_is_used_as_given(tmp_path: Path) -> None:
    assert content_root(str(tmp_path)) == tmp_path.resolve()


def test_the_cards_are_counted(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["cards"]) == 0

    printed = capsys.readouterr().out

    assert "total" in printed
    assert "base_game" in printed


def test_a_game_is_played_through(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["play", "--seed", "3", "--players", "2"]) == 0

    assert "won" in capsys.readouterr().out


def test_the_version_is_printed(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--version"])

    assert raised.value.code == 0
    assert "fsme" in capsys.readouterr().out


def test_a_double_clicked_build_opens_the_game(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Somebody who ran the executable with no arguments wants to play, not to
    read a usage message.
    """
    asked: dict[str, object] = {}

    def remember(args: object) -> int:
        asked["command"] = getattr(args, "command", None)
        asked["open"] = getattr(args, "open", None)

        return 0

    monkeypatch.setattr(entry_point, "serve", remember)

    assert main([]) == 0
    assert asked == {"command": "serve", "open": True}


def test_a_named_command_is_still_obeyed(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["cards"]) == 0
    assert "total" in capsys.readouterr().out


def test_a_played_game_can_be_written_down_and_read_back(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    The whole loop from the outside: play, write, read, replay.
    """
    journal = tmp_path / "party.json"

    assert main(["play", "--seed", "3", "--journal", str(journal), "--offers"]) == 0
    assert journal.is_file()

    capsys.readouterr()

    assert main(["show", str(journal)]) == 0

    told = capsys.readouterr().out

    assert "FSME journal" in told
    assert "could have:" in told

    assert main(["replay", str(journal)]) == 0
    assert "came out the same" in capsys.readouterr().out


def test_a_run_can_be_played_on_several_cores(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["simulate", "--games", "4", "--jobs", "2", "--top", "2"]) == 0

    told = capsys.readouterr().out

    assert "4 games" in told
    assert "random" in told, "the report says who was playing"


def test_a_card_can_be_tested_against_its_own_absence(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "test-card",
                "treasure_deck-active_items-base_game-guppy_s_paw",
                "--games",
                "4",
                "--jobs",
                "2",
            ]
        )
        == 0
    )

    told = capsys.readouterr().out

    assert "Card test" in told
    assert "4 games with it, 4 without" in told


def test_a_card_nobody_has_heard_of_is_refused(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["test-card", "not.a.card", "--games", "2"]) == 2
    assert "no card called" in capsys.readouterr().out


def test_a_run_can_be_studied(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["study", "--games", "6", "--players", "3", "--jobs", "3"]) == 0

    told = capsys.readouterr().out

    assert "FSME study" in told
    assert "What went with winning" in told
    assert "Games worth a look" in told


def test_one_game_can_be_explained(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["explain", "--seed", "3", "--players", "3"]) == 0

    told = capsys.readouterr().out

    assert "Game 3" in told
    assert "souls" in told


def test_a_journal_on_disk_can_be_explained(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    journal = tmp_path / "party.json"

    assert main(["play", "--seed", "5", "--journal", str(journal)]) == 0

    capsys.readouterr()

    assert main(["explain", str(journal)]) == 0
    assert "Game 5" in capsys.readouterr().out


def test_a_report_is_one_command_and_the_whole_picture(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["report", "--seed", "5", "--players", "2"]) == 0

    told = capsys.readouterr().out

    assert "FSME GAME REPORT" in told
    assert "Key moments" in told
    assert "What did the work" in told


def test_a_report_can_skip_the_replay(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["report", "--seed", "5", "--players", "2", "--quick"]) == 0

    told = capsys.readouterr().out

    assert "FSME GAME REPORT" in told
    assert "The decisions" not in told
