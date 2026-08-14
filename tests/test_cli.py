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
