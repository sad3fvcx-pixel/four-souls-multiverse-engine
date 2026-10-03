#!/usr/bin/env python3

"""
Everything about this build is in ``pyproject.toml`` except one thing.

The cards are the game. An installed ``fsme`` without them is a command that
can only print its own version, so the card data has to travel inside the
wheel — and the card data lives at ``content/`` in the repository, outside
``src/``, where setuptools' package-data cannot see it.

Moving it under ``src/fsme/`` would fix the build and spoil the thing it is
for: ``content/`` at the top of the checkout is where somebody writing a card
looks, and burying it three directories inside the source would make the
authoring path worse to make the packaging path easier.

So the build copies it in. ``content/`` stays where an author expects it, and
the wheel gets ``fsme/carddata/`` — the same files, found at run time by
``fsme.cli.main.content_root`` when nothing nearer turns up.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).resolve().parent

CARDS = ROOT / "content"

INSIDE = ("fsme", "carddata")
"""Where the cards land inside the package."""

KEEP = ("*.json", "*.md")
"""
What is copied.

Card data and the notes beside it. Nothing else is in there, and naming what
travels means a stray file in a working directory never ends up in a release.
"""


class BuildWithCards(build_py):
    """
    The ordinary build, plus the cards.
    """

    def run(self) -> None:
        super().run()

        if not CARDS.is_dir():
            # A build from an sdist that did not carry the cards. Saying so is
            # better than producing a wheel that looks fine and cannot deal.
            self.warn(f"no card content at {CARDS}; the build will have no cards")

            return

        where = Path(self.build_lib).joinpath(*INSIDE)

        if where.exists():
            shutil.rmtree(where)

        shutil.copytree(
            CARDS,
            where,
            ignore=shutil.ignore_patterns("__pycache__", ".*"),
        )

        kept = sum(1 for pattern in KEEP for _ in where.rglob(pattern))

        for path in where.rglob("*"):
            if path.is_file() and not any(
                path.match(pattern) for pattern in KEEP
            ):
                path.unlink()

        self.announce(f"copied {kept} card files into {'/'.join(INSIDE)}", level=2)


setup(
    cmdclass={"build_py": BuildWithCards},
    package_data={"fsme": ["carddata/**/*.json", "carddata/**/*.md"]},
)
