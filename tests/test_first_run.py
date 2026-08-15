"""
The path somebody walks the first time they run this.

Everything here was a real failure found by installing the project into an
empty environment and typing what a newcomer would type. They are collected in
one file because they share a subject — not the engine, but whether a stranger
can get anywhere with it — and because each of them is the kind of break that
no other test would notice: the engine works perfectly and the person cannot
reach it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from fsme.cli import main as entry_point
from fsme.cli.main import (
    COMMAND_GROUPS,
    build_parser,
    content_root,
    demo,
)

ROOT = Path(__file__).resolve().parents[1]


# ----------------------------------------------------------------------
# Finding the cards
# ----------------------------------------------------------------------


def test_a_checkout_finds_its_own_cards_without_being_told() -> None:
    assert content_root(None) == (ROOT / "content").resolve()


def test_the_packaged_cards_are_a_place_the_engine_looks() -> None:
    """
    A wheel carries the cards at ``fsme/carddata``.

    Without this an installed ``fsme`` is a command that can only print its own
    version — which is exactly what a clean ``pip install`` produced until the
    build was taught to copy the content in. The path is asserted here because
    the copying happens in ``setup.py``, far from the code that reads it, and
    the two agreeing is the whole of the arrangement.
    """
    import fsme

    inside = Path(fsme.__file__).resolve().parent / "carddata"

    # What the build writes and what the command reads have to be the same
    # place, and they are decided in two files that do not import each other.
    assert '("fsme", "carddata")' in (ROOT / "setup.py").read_text("utf-8")
    assert 'here.parents[1] / "carddata"' in (
        ROOT / "src" / "fsme" / "cli" / "main.py"
    ).read_text("utf-8")

    assert inside.name == "carddata"


def test_a_content_path_that_is_not_there_says_so_plainly(
    tmp_path: Path,
) -> None:
    with pytest.raises(SystemExit) as raised:
        content_root(str(tmp_path / "nowhere"))

    said = str(raised.value)

    assert "no card content" in said
    assert "base_game" in said, "the message should say what to point at"


# ----------------------------------------------------------------------
# Finding the commands
# ----------------------------------------------------------------------


def test_every_command_is_in_the_grouped_help() -> None:
    """
    Eleven commands listed in the order they were written is a wall.

    The grouping is written by hand, so it can drift from the parser; this is
    what stops it. A command absent from the help is a command nobody runs.
    """
    parser = build_parser()

    actions = [
        action
        for action in parser._subparsers._group_actions  # noqa: SLF001
        if action.choices
    ]

    real = set(actions[0].choices)
    listed = {name for _, rows in COMMAND_GROUPS for name, _ in rows}

    assert listed == real, (
        f"help and parser disagree: "
        f"only in help {listed - real}, only in parser {real - listed}"
    )


def test_the_help_says_where_to_start() -> None:
    told = build_parser().format_help()

    assert "fsme demo" in told
    assert "Start here" in told


def test_the_demo_needs_no_arguments() -> None:
    args = build_parser().parse_args(["demo"])

    assert args.run is demo
    assert args.content is None


# ----------------------------------------------------------------------
# Being told what went wrong
# ----------------------------------------------------------------------


def test_bad_content_is_reported_rather_than_raised(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    A person writing a card should be told about their card.

    Before this, a typo in a content file printed twenty lines of traceback
    ending in the loader — which is a fact about the engine, and they wanted a
    fact about their card.
    """
    where = tmp_path / "content" / "broken"
    where.mkdir(parents=True)

    (where / "manifest.json").write_text(
        '{"id": "broken", "name": "Broken", "version": "1.0.0",'
        ' "schema_version": "1"}',
        encoding="utf-8",
    )
    (where / "cards.json").write_text(
        '[{"id": "broken-x", "name": "X", "type": "loot", "expansion": "broken",'
        ' "abilities": [{"trigger": "on_play", "effects":'
        ' [{"effect": "gain_coinz", "amount": 1}]}]}]',
        encoding="utf-8",
    )

    outcome = entry_point(["cards", "--content", str(tmp_path / "content")])

    assert outcome == 2

    complaint = capsys.readouterr().err

    assert "Traceback" not in complaint
    assert "broken-x" in complaint
    assert "gain_coinz" in complaint
    assert "did you mean 'gain_coins'" in complaint


def test_a_near_miss_is_offered_and_a_wild_guess_is_not() -> None:
    from fsme.cards.validator import did_you_mean

    known = ["gain_coins", "draw_loot", "deal_damage"]

    assert "gain_coins" in did_you_mean("gain_coinz", known)
    assert "draw_loot" in did_you_mean("draw_loots", known)

    # A wrong suggestion is worse than none: it sends somebody to read about an
    # effect that was never going to help them.
    assert did_you_mean("summon_dragon", known) == ""


# ----------------------------------------------------------------------
# Finding a set
# ----------------------------------------------------------------------


def test_a_set_is_found_wherever_it_sits_in_a_content_root(
    tmp_path: Path,
) -> None:
    """
    A directory with a manifest is a set, whatever it is called.

    Somebody assembling a small content directory of their own used to get
    their set silently ignored unless they happened to name the parent
    directory one of four things.
    """
    from fsme.content import ContentLoader

    root = tmp_path / "mine"

    for name in ("straight_here", "nested/deeper"):
        where = root / name
        where.mkdir(parents=True)

        given = where.name

        (where / "manifest.json").write_text(
            f'{{"id": "{given}", "name": "{given}", "version": "1.0.0",'
            f' "schema_version": "1"}}',
            encoding="utf-8",
        )
        (where / "cards.json").write_text(
            f'[{{"id": "{given}-card", "name": "A Card", "type": "loot",'
            f' "expansion": "{given}", "abilities": []}}]',
            encoding="utf-8",
        )

    found = ContentLoader().load_root(root)

    ids = {definition.id for definition in found.definitions()}

    assert ids == {"straight_here-card", "deeper-card"}


# ----------------------------------------------------------------------
# The demonstration itself
# ----------------------------------------------------------------------


def test_the_demo_walks_the_whole_path(
    capsys: pytest.CaptureFixture[str],
) -> None:
    outcome = demo(
        argparse.Namespace(content=None, jobs=2, quick=True)
    )

    assert outcome == 0

    told = capsys.readouterr().out

    # Every step names the command it is running, so the tour teaches the
    # commands rather than replacing them.
    for expected in (
        "fsme play",
        "fsme replay",
        "fsme report",
        "FSME GAME REPORT",
        "Where to go from here",
        "fsme desk",
    ):
        assert expected in told, expected


# ----------------------------------------------------------------------
# What a stranger finds in the repository
# ----------------------------------------------------------------------


def test_the_build_recipe_is_actually_in_the_repository() -> None:
    """
    ``.gitignore`` had ``*.spec`` in it, and PyInstaller specs end in ``.spec``.

    So the one file that says how to build the executable was never committed:
    a clone could not build it, and the workflow step that does would have
    failed on a fresh checkout. Nothing else would have noticed, because the
    file was present on the machine it was written on.
    """
    import subprocess

    spec = ROOT / "packaging" / "fsme.spec"

    assert spec.is_file()

    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(spec.relative_to(ROOT))],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert tracked.returncode == 0, "packaging/fsme.spec is not tracked by git"


def test_the_examples_are_there_to_be_read_without_installing() -> None:
    examples = ROOT / "examples"

    expected = {
        "README.md",
        "one-game-report.txt",
        "a-study.txt",
        "a-card-test.txt",
        "the-record-holds.txt",
        "a-problem-found.txt",
    }

    assert expected <= {path.name for path in examples.iterdir()}

    # Each one says what command made it, so a reader can check any figure.
    for name in expected - {"README.md"}:
        assert "$ fsme" in (examples / name).read_text("utf-8"), name


def test_the_tour_shows_all_five_things_it_promises() -> None:
    """
    Play, result, why, the moments, and analysis over many games.

    Checked on the pieces rather than by running the whole tour, which takes
    twenty seconds and half a dozen processes.
    """
    from fsme.cli.main import DEMO_GAMES, DEMO_STUDY

    report = (ROOT / "examples" / "one-game-report.txt").read_text("utf-8")

    for expected in ("Winner", "Key moments", "Why", "The decisions"):
        assert expected in report, expected

    study = (ROOT / "examples" / "a-study.txt").read_text("utf-8")

    assert "What went with winning" in study

    assert DEMO_STUDY > 1, "the tour plays more than one game"
    assert DEMO_GAMES > 1, "the tour tests a card over more than one game"
