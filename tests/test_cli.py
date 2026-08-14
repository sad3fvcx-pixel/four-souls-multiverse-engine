"""
The command line.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fsme.cli.main import content_root, main

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
