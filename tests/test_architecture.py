"""
The one line in the project that is not allowed to move.

FSME is a core that plays the game and a lab that studies it, and the whole
value of the split is that the dependency runs one way. If a rules module ever
imports an analysis module, then a report is part of the rules, a measurement
can change what it measures, and nothing in the engine can be trusted to be
about Four Souls rather than about somebody's experiment.

That is easy to state and easy to violate by accident — one convenient import
in a hurry. So it is read off the source rather than promised in a document.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "src" / "fsme"

LAB = "lab"

FRONT_DOOR = {"cli"}
"""
The packages allowed to see both sides.

A command-line tool exists precisely to put the two together, and a front door
that could not reach the rooms would not be a door. It is listed rather than
excused, and it is one package long.
"""


def _packages() -> Iterator[tuple[str, Path]]:
    """
    Every module in the project, with the top-level package it belongs to.
    """
    for path in sorted(SOURCE.rglob("*.py")):
        parts = path.relative_to(SOURCE).parts

        yield parts[0].removesuffix(".py"), path


def _imports(path: Path) -> Iterator[str]:
    """
    Every ``fsme.`` module named by an import in one file.
    """
    tree = ast.parse(path.read_text("utf-8"), filename=str(path))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            yield node.module


def test_the_core_has_never_heard_of_the_lab() -> None:
    reaching: list[str] = []

    for package, path in _packages():
        if package in (LAB, *FRONT_DOOR):
            continue

        for imported in _imports(path):
            if imported == "fsme.lab" or imported.startswith("fsme.lab."):
                reaching.append(f"{path.relative_to(SOURCE)} imports {imported}")

    assert not reaching, (
        "the core reached into the lab, which would make a report part of the "
        "rules:\n  " + "\n  ".join(reaching)
    )


def test_the_lab_is_where_the_tools_are() -> None:
    inside = {path.name for path in (SOURCE / LAB).iterdir() if path.is_dir()}

    assert {"analysis", "bot", "simulation"} <= inside


def test_the_core_still_holds_the_game() -> None:
    # Named so that moving one of these into the lab fails loudly rather than
    # quietly: these are the packages a saved game and a replay depend on.
    core = {path.name for path in SOURCE.iterdir() if path.is_dir()}

    assert {
        "cards",
        "commands",
        "content",
        "effects",
        "events",
        "game",
        "journal",
        "rules",
        "runtime",
        "stack",
        "state",
    } <= core


def test_only_the_front_door_sees_both_sides() -> None:
    both: set[str] = set()

    for package, path in _packages():
        if package == LAB:
            continue

        for imported in _imports(path):
            if imported.startswith("fsme.lab"):
                both.add(package)

    assert both <= FRONT_DOOR
