#!/usr/bin/env python3

"""
Build the demonstration, from the engine rather than from memory.

``docs/DEMONSTRATION.md`` is meant to convince somebody that FSME understands
the game rather than merely runs it, which means every number in it has to be
one the engine actually produced. So the document is generated: this script
plays the games, runs the commands and pastes their real output, and anybody
doubting a figure can run the same command and get the same figure.

Everything here is fixed by seed, so re-running it produces the same document
until the engine changes — at which point the diff is the news.

Usage::

    python tools/make_demonstration.py                  # the quick version
    python tools/make_demonstration.py --games 500      # the one worth showing
"""

from __future__ import annotations

import argparse
import io
import subprocess
import sys
import time
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SEED = 7
PLAYERS = 3

WHERE = ROOT / "docs" / "DEMONSTRATION.md"
GAME = ROOT / "demo" / "party.json"

EXAMPLES = ROOT / "examples"
"""
Where the same output is kept one file at a time.

The demonstration reads as a tour and is long. Somebody deciding in thirty
seconds whether this is worth installing wants to open one file and see one
thing, so every block of the tour is also written out on its own.
"""

BROKEN_SEED = 8
BROKEN_WITHOUT = "treasure_deck-active_items-base_game-guppy_s_paw"
"""
A deal that reaches a pair of cards which copy each other without end.

Taking any card out reshuffles every game, and this seed with this card
removed lands on Placebo and Rainbow Tapeworm copying one another. It is kept
as an example on purpose: a tool that only ships its successes is not showing
you what it does when something is wrong.

It is an example of the defect, not a definition of it. Dealing the three cents
the rules call for changed every shuffle in the project and one of the two
seeds that used to loop now settles. If this one settles too, the loop has not
been fixed — the deal has moved, and a short search finds another.
"""


def run(argv: list[str]) -> str:
    """
    Run one fsme command in this process and keep what it printed.
    """
    from fsme.cli import main

    caught = io.StringIO()

    with redirect_stdout(caught):
        main(argv)

    return caught.getvalue().rstrip()


def fenced(text: str) -> str:
    return f"```\n{text}\n```"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=120)
    parser.add_argument("--test-games", type=int, default=200)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument(
        "--card",
        default="loot_deck-cards_miscellaneous-four_souls-gold_key",
        help="the card the demonstration puts under test",
    )

    args = parser.parse_args(argv)

    sys.path.insert(0, str(ROOT / "src"))

    GAME.parent.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()

    print("playing the demonstration game…", flush=True)

    played = run(
        [
            "play",
            "--seed",
            str(SEED),
            "--players",
            str(PLAYERS),
            "--bot-seats",
            "0",
            "--journal",
            str(GAME),
            "--offers",
        ]
    )

    print("replaying it…", flush=True)
    replayed = run(["replay", str(GAME)])

    print("reporting on it…", flush=True)
    reported = run(["report", str(GAME)])

    print(f"studying {args.games} games…", flush=True)
    studied = run(
        [
            "study",
            "--games",
            str(args.games),
            "--players",
            str(PLAYERS),
            "--jobs",
            str(args.jobs),
            "--bot-seats",
            "0",
        ]
    )

    print(f"testing a card over {args.test_games} games each way…", flush=True)
    tested = run(
        [
            "test-card",
            args.card,
            "--games",
            str(args.test_games),
            "--jobs",
            str(args.jobs),
        ]
    )

    spent = time.perf_counter() - started

    WHERE.write_text(
        _document(
            played=played,
            replayed=replayed,
            reported=reported,
            studied=studied,
            tested=tested,
            games=args.games,
            test_games=args.test_games,
            card=args.card,
            version=_version(),
        ),
        encoding="utf-8",
    )

    print(f"wrote {WHERE.relative_to(ROOT)} in {spent:.0f}s")

    print("writing the examples…", flush=True)

    written = _examples(
        reported=reported,
        studied=studied,
        tested=tested,
        replayed=replayed,
        games=args.games,
        test_games=args.test_games,
        card=args.card,
    )

    for path in written:
        print(f"  {path.relative_to(ROOT)}")

    return 0


def _found_a_problem() -> str:
    """
    Run the deal that does not settle, and keep what the engine said about it.
    """
    from fsme.api import load_content
    from fsme.lab.simulation import play_one

    library = load_content(ROOT / "content").without({BROKEN_WITHOUT})

    try:
        play_one(library, BROKEN_SEED, 2)
    except Exception as complaint:
        return f"{type(complaint).__name__}: {complaint}"

    return "this deal settles now; the example needs a new one"


def _examples(
    *,
    reported: str,
    studied: str,
    tested: str,
    replayed: str,
    games: int,
    test_games: int,
    card: str,
) -> list[Path]:
    """
    Write each block out on its own, with the command that made it on top.
    """
    EXAMPLES.mkdir(parents=True, exist_ok=True)

    problem = _found_a_problem()

    files = {
        "one-game-report.txt": (
            "fsme report demo/party.json",
            "Everything the lab can say about a single game.",
            reported,
        ),
        "a-study.txt": (
            f"fsme study --games {games} --players {PLAYERS} --bot-seats 0",
            f"What {games} games say about the game itself.",
            studied,
        ),
        "a-card-test.txt": (
            f"fsme test-card {card} --games {test_games}",
            "The same seeds with one card in the deck and without it.",
            tested,
        ),
        "the-record-holds.txt": (
            "fsme replay demo/party.json",
            "The game played back through the engine, position by position.",
            replayed,
        ),
        "a-problem-found.txt": (
            f"fsme play --seed {BROKEN_SEED} --players 2"
            f"  # with {BROKEN_WITHOUT} removed",
            (
                "A deal the engine refuses to finish, and what it says about"
                " it.\n"
                "Placebo copies an item's ability; Rainbow Tapeworm becomes a"
                " copy of an item;\n"
                "together they copy each other without end. The rules say"
                " nothing about\n"
                "infinite loops, so no rule was invented: the engine names what"
                " kept\n"
                "happening and stops. Recorded as a gap in"
                " docs/PROJECT_PLAN.md 11.5."
            ),
            problem,
        ),
    }

    written: list[Path] = []

    for name, (command, what, body) in files.items():
        path = EXAMPLES / name

        path.write_text(
            f"{what}\n\n$ {command}\n\n{body}\n", encoding="utf-8"
        )

        written.append(path)

    index = EXAMPLES / "README.md"

    index.write_text(_index(files), encoding="utf-8")
    written.append(index)

    return written


def _index(files: dict[str, tuple[str, str, str]]) -> str:
    rows = "\n".join(
        f"| [`{name}`]({name}) | {what.splitlines()[0]} |"
        for name, (_, what, _) in files.items()
    )

    return f"""# Examples

Real output, generated by `tools/make_demonstration.py` from the game in
`demo/party.json` and from runs of the ordinary commands. Nothing here is
written by hand, so anything in these files can be reproduced by running the
command printed at the top of it.

| File | What it shows |
|---|---|
{rows}

`cards/sample_expansion.json` is a card set in the shape the engine reads —
see the *Writing a card* section of the README.

To see the same thing happen live rather than reading it:

```bash
fsme demo
```
"""


def _version() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def _document(
    *,
    played: str,
    replayed: str,
    reported: str,
    studied: str,
    tested: str,
    games: int,
    test_games: int,
    card: str,
    version: str,
) -> str:
    return f"""# FSME — a demonstration

Every block below is output from the engine, pasted unedited. The document is
generated by `tools/make_demonstration.py`, so any figure in it can be checked
by running the command above the block. Built from commit `{version}`.

The point is not that FSME plays Four Souls. It is that it can be *asked
questions* about a game it played and answer them from its own record.

---

## One game, played and written down

```bash
fsme play --seed {SEED} --players {PLAYERS} --bot-seats 0 --journal demo/party.json --offers
```

{fenced(played)}

A journal is not a save file. It holds, for every accepted command: the
position it was made from, everything else the engine would have accepted at
that moment, the command itself, every event it caused, and a fingerprint of
the position afterwards.

## It still holds

```bash
fsme replay demo/party.json
```

{fenced(replayed)}

The journal is played back through the ordinary engine and every position is
compared against its recorded fingerprint. This is what makes the rest of the
document evidence rather than assertion: the game in `demo/party.json` is
reproducible, and if the engine ever changes under it, the replay names the
first command whose outcome no longer matches instead of quietly reporting a
different game.

## The whole report

```bash
fsme report demo/party.json
```

{fenced(reported)}

Read what that report is doing, section by section.

**Key moments** are measured, not chosen. Every entry in the journal carries
the events it caused; a move's weight is what its own events did to the
winner's lead over the table. Most moves weigh nothing — passing, ending a
phase — and the handful that weigh something are the game. Where a swing came
after a die, the die is named and so is the chance it had, because a big swing
somebody rolled for is not a big swing somebody played for.

**Why they won** is a comparison and says so. It lists what differed, not what
helped: in this game the winner died *more often* than the table, and the
report prints that rather than tidying it away, because it has no way to know
which direction of a count is the good one.

**The decisions** are the game replayed with a bot weighing every move on
offer. The gap between what was played and what the bot would have played is a
disagreement with a stated opinion — the bot looks one move ahead and does not
know what most cards say — but two of the numbers in it are not opinion at all:
the chance an attack roll lands, and whether a miss would be lethal, are
arithmetic from the printed difficulty and the attacker's hit points.

**What did the work** credits each event to whatever the engine named as its
source, signed towards the winner, so a monster that hurt them scores below
zero.

---

## What {games} games say

```bash
fsme study --games {games} --players {PLAYERS} --jobs 4 --bot-seats 0
```

{fenced(studied)}

Three things in that output are worth pointing at.

The **splits** are winners against everybody else, and the wording is "went
with winning" rather than "caused winning" — a player who killed four monsters
won partly because of it and killed the fourth partly because they were already
winning, and no number of games separates those two.

The **pairs** table is offered as a list of hypotheses. With hundreds of cards
there are tens of thousands of pairs, so the top of any such table is striking
by arithmetic alone.

And **worth testing next** is the study admitting its own limits: it ends by
naming cards and printing the command that would settle them. That rule had to
be rewritten before it shipped — the first version compared each card's users
against the whole table and marked eighteen cards out of sixty games, because a
player who is winning takes more turns, uses more cards, and turns up
disproportionately among the users of *everything*. Cards are now compared
against seats that got through a similar number of cards, and the threshold
moves out with the number of cards examined.

---

## Putting a card under test

```bash
fsme test-card {card} --games {test_games} --jobs 4
```

{fenced(tested)}

This is the only tool here that can tell an effect from a correlation, and it
does it the only way available: play the same seeds with the card in the
content and again without it, and compare the two populations.

The interval beside each number is measured from the games that were played,
not assumed from their average. That distinction is not academic: an earlier
version assumed the spread, got intervals about seven times too narrow, and
duly announced effects that a larger run reversed. A wide interval that says
nothing is worth more than a narrow one that says the wrong thing.

Its limits are printed with its answer rather than left for the reader to
discover. Taking a card out of the deck reshuffles every game that deck deals,
so the two runs differ everywhere and not only where the card is — which is why
a card that reached the table in fewer than one game in ten gets nothing marked
at all, and why the verdict for such a card is "too scarce to say" rather than
"no effect". "No effect this run could see" and "no effect" are different
sentences, and the report never prints the second one.

---

## Running any of this yourself

```bash
pip install -e .

fsme desk --open      # all of it, on one page in a browser
fsme report demo/party.json
```

Everything the page runs is the same function the command runs, printing the
same text, because two sources of truth would make the first disagreement
between them unanswerable.
"""


if __name__ == "__main__":
    raise SystemExit(main())
