# src/fsme/cli/main.py

"""
The ``fsme`` command.

Three things a person might want from outside a Python session: to look at a
game in a browser, to play one through to the end without watching, and to know
what the engine knows about the cards it has been given.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import webbrowser
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fsme.api import Session, load_content
from fsme.content import ContentLibrary
from fsme.game import Game

DEFAULT_NAMES = ("Ann", "Bo", "Cy", "Di")

VERSION = "0.1.0"


def content_root(given: str | None) -> Path:
    """
    Find the cards.

    A checkout keeps them beside the source; a bundled build carries them
    inside itself, and PyInstaller unpacks them next to the package. Both are
    tried before giving up, because a build that cannot find its own content is
    not a build anybody can run.
    """
    if given:
        return Path(given).expanduser().resolve()

    here = Path(__file__).resolve()

    candidates = [here.parents[3] / "content", Path.cwd() / "content"]

    bundled = getattr(sys, "_MEIPASS", "")

    if bundled:
        # A frozen build carries the cards inside itself and unpacks them
        # beside the package, so that is the first place to look.
        candidates.insert(0, Path(bundled) / "content")

    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()

    raise SystemExit(
        "cannot find the card content; pass --content with the path to it"
    )


def library(args: argparse.Namespace) -> ContentLibrary:
    return load_content(content_root(args.content))


def serve(args: argparse.Namespace) -> int:
    """
    Put one game behind a local web page.
    """
    from fsme.web import serve as build

    session = Session(
        library(args),
        players=args.players,
        seed=args.seed,
        interactive_priority=not args.no_priority,
    )

    server = build(session, host=args.host, port=args.port)
    where = f"http://{args.host}:{args.port}/"

    print(f"FSME is at {where} — Ctrl-C to stop", flush=True)

    if args.open:
        webbrowser.open(where)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("", flush=True)
    finally:
        server.server_close()

    return 0


def play(args: argparse.Namespace) -> int:
    """
    Play a game through with nobody watching, and say how it went.

    The players are not clever. This is here because a person setting the
    engine up wants to know it runs, and a game played end to end says so more
    convincingly than a version number.

    With ``--journal`` the whole game is written down as it goes: what was
    offered, what was chosen, and everything that followed.
    """
    from fsme.api.moves import legal_moves
    from fsme.commands import Command, CommandType
    from fsme.journal import JournalKeeper

    game = Game.from_content(
        library(args),
        list(DEFAULT_NAMES[: args.players]),
        seed=args.seed,
        interactive_priority=False,
    )

    game.start()

    keeper = JournalKeeper(
        game,
        offers=(
            (lambda played: [move["label"] for move in legal_moves(played)])
            if args.journal and args.offers
            else None
        ),
    )

    rng = random.Random(args.seed)
    outcome = 0

    for step in range(args.steps):
        if game.is_over:
            winner = game.state.players[game.state.winner or 0]

            print(
                f"{winner.name} won on turn {game.state.turn.turn_number} "
                f"after {step} moves"
            )

            break

        decision = game.runtime.awaiting_decision

        if decision is not None:
            count = len(decision.options)
            lowest = max(0, min(decision.minimum, count))
            highest = max(lowest, min(decision.maximum, count))

            picks = (
                rng.sample(range(count), rng.randint(lowest, highest)) if count else []
            )

            keeper.submit(
                Command(
                    type=CommandType.CHOOSE_TARGET,
                    player=decision.player,
                    payload={"choices": picks},
                ),
                label=_answer(decision, picks),
            )

            continue

        moves = legal_moves(game)

        if not moves:
            print(f"nothing could be done after {step} moves")

            outcome = 1

            break

        move = rng.choice(moves)

        keeper.submit(
            Command(
                type=CommandType(move["type"]),
                player=move["player"],
                payload=dict(move["payload"]),
            ),
            label=move["label"],
        )
    else:
        print(f"still going after {args.steps} moves")

    if args.journal:
        written = keeper.journal.save(args.journal)

        print(f"journal written to {written} ({len(keeper.journal)} commands)")

    return outcome


def _answer(decision: Any, picks: Sequence[int]) -> str:
    """
    Say an answer to a question in the words the question offered.
    """
    options = list(decision.options)

    chosen = [
        str(getattr(options[index], "name", options[index]))
        for index in picks
        if 0 <= index < len(options)
    ]

    asked = decision.prompt or str(decision.kind)

    return f"{asked} → " + (", ".join(chosen) if chosen else "nothing")


def show(args: argparse.Namespace) -> int:
    """
    Read a journal out loud.
    """
    from fsme.journal import Journal, render

    journal = Journal.load(args.file)

    print(render(journal, full=args.full))

    return 0


def replay(args: argparse.Namespace) -> int:
    """
    Play a journal back through the engine and say whether it still holds.
    """
    from fsme.journal import Journal, replay_journal, summarise

    journal = Journal.load(args.file)
    playback = replay_journal(journal, library(args))
    told = summarise(playback, journal)

    if args.json:
        print(json.dumps(told, indent=2))

        return 0 if playback.faithful else 1

    if playback.faithful:
        print(
            f"{told['replayed']} commands replayed, and the game came out the "
            f"same every step of the way"
        )

        return 0

    print(f"replayed {told['replayed']} of {told['commands']} commands, then:")
    print(f"  {told['divergence']}")

    return 1


def simulate(args: argparse.Namespace) -> int:
    """
    Play a run of games and say what happened across all of them.
    """
    from fsme.analysis import Tally, report
    from fsme.simulation import run as play_them

    into = Path(args.journals).expanduser() if args.journals else None

    tally = Tally()
    started = time.perf_counter()

    def tick(progress: Any) -> None:
        if args.json or progress.played % 25:
            return

        print(
            f"  {progress.played}/{args.games} games, "
            f"{progress.abandoned} abandoned",
            flush=True,
        )

    if args.jobs > 1:
        from fsme.simulation import run_on_many_cores

        for done in run_on_many_cores(
            content_root(args.content),
            args.games,
            args.players,
            jobs=args.jobs,
            first_seed=args.seed,
            offers=args.offers,
            journals_into=into,
        ):
            tally.merge(done.tally)
    else:
        for outcome in play_them(
            library(args),
            args.games,
            args.players,
            first_seed=args.seed,
            offers=args.offers,
            journals_into=into,
            watching=tick,
        ):
            tally.add(outcome.journal)

    spent = time.perf_counter() - started

    if args.json:
        told = tally.to_dict()
        told["seconds"] = round(spent, 3)

        print(json.dumps(told, indent=2))

        return 0

    print()
    print(report(tally, top=args.top))
    print(
        f"{args.games} games in {spent:.1f}s "
        f"({spent / max(1, args.games):.2f}s each), seeds "
        f"{args.seed}–{args.seed + args.games - 1}"
    )
    print(
        "Played by a table that chooses at random among legal moves. These are "
        "numbers about the game under random play, not about how it plays."
    )

    if into is not None:
        print(f"journals written to {into}")

    return 0


def test_card(args: argparse.Namespace) -> int:
    """
    Play the same seeds with a card in the game and without it, and compare.
    """
    from fsme.analysis import Tally, compare, read_out
    from fsme.simulation import run_on_many_cores

    root = content_root(args.content)
    loaded = library(args)

    try:
        card = loaded.registry().get(args.card)
    except Exception:
        print(f"no card called {args.card!r} — try `fsme cards` to see the sets")

        return 2

    runs: dict[str, Tally] = {}
    broken: dict[str, list[str]] = {"with": [], "without": []}
    appeared = 0

    for label, drop in (("with", ()), ("without", (args.card,))):
        tally = Tally()

        for done in run_on_many_cores(
            root,
            args.games,
            args.players,
            jobs=max(1, args.jobs),
            first_seed=args.seed,
            without=drop,
        ):
            tally.merge(done.tally)

            if done.broke:
                broken[label].append(f"seed {done.seed}: {done.broke}")

        runs[label] = tally

        if label == "with":
            seen = tally.cards.get(args.card)
            appeared = seen.games if seen else 0

    told = compare(
        f"{card.name} ({args.card})",
        runs["with"],
        runs["without"],
        appeared=appeared,
        errors_with=len(broken["with"]),
        errors_without=len(broken["without"]),
    )

    if args.json:
        print(json.dumps(told.to_dict(), indent=2))

        return 0

    print(read_out(told))

    for label, failures in broken.items():
        for failure in failures[:5]:
            print(f"  fell over {label} it — {failure}")

    return 0


def cards(args: argparse.Namespace) -> int:
    """
    Say what is in the content directory, and how much of it the engine knows.
    """
    loaded = library(args)

    counted: dict[str, dict[str, int]] = {}

    for definition in loaded.definitions():
        row = counted.setdefault(
            definition.expansion, {"cards": 0, "implemented": 0}
        )

        row["cards"] += 1

        if definition.abilities or definition.statics:
            row["implemented"] += 1

    if args.json:
        print(json.dumps(counted, indent=2))

        return 0

    total = sum(row["cards"] for row in counted.values())
    done = sum(row["implemented"] for row in counted.values())

    for name, row in sorted(counted.items(), key=lambda item: -item[1]["cards"]):
        print(f"{name:<28} {row['implemented']:>5} / {row['cards']}")

    print(f"{'total':<28} {done:>5} / {total}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fsme",
        description="Four Souls Multiverse Engine",
    )
    parser.add_argument("--version", action="version", version=f"fsme {VERSION}")

    commands = parser.add_subparsers(dest="command")

    def shared(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--content", help="where the card content lives")
        sub.add_argument("--seed", type=int, default=0, help="deal this game")
        sub.add_argument("--players", type=int, default=2, help="how many seats")

    web = commands.add_parser("serve", help="open a game in a browser")
    shared(web)
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8000)
    web.add_argument("--open", action="store_true", help="open a browser too")
    web.add_argument(
        "--no-priority",
        action="store_true",
        help="skip the priority windows, resolving everything at once",
    )
    web.set_defaults(run=serve)

    quick = commands.add_parser("play", help="play a game through with nobody watching")
    shared(quick)
    quick.add_argument("--steps", type=int, default=5000)
    quick.add_argument("--journal", help="write the whole game down to this file")
    quick.add_argument(
        "--offers",
        action="store_true",
        help="record what else could have been done at each point",
    )
    quick.set_defaults(run=play)

    reading = commands.add_parser("show", help="read a journal out loud")
    reading.add_argument("file", help="the journal to read")
    reading.add_argument(
        "--full", action="store_true", help="keep the engine's housekeeping too"
    )
    reading.set_defaults(run=show)

    again = commands.add_parser("replay", help="play a journal back through the engine")
    shared(again)
    again.add_argument("file", help="the journal to replay")
    again.add_argument("--json", action="store_true")
    again.set_defaults(run=replay)

    many = commands.add_parser("simulate", help="play a run of games and count")
    shared(many)
    many.add_argument("--games", type=int, default=100, help="how many to play")
    many.add_argument("--top", type=int, default=15, help="rows per table")
    many.add_argument("--journals", help="write every journal into this directory")
    many.add_argument(
        "--offers",
        action="store_true",
        help="record what else could have been done at each point",
    )
    many.add_argument("--json", action="store_true")
    many.add_argument(
        "--jobs", type=int, default=1, help="play on this many cores at once"
    )
    many.set_defaults(run=simulate)

    trial = commands.add_parser(
        "test-card", help="play the game with a card and without it"
    )
    shared(trial)
    trial.add_argument("card", help="the identifier of the card under test")
    trial.add_argument("--games", type=int, default=100, help="games in each run")
    trial.add_argument("--jobs", type=int, default=1)
    trial.add_argument("--json", action="store_true")
    trial.set_defaults(run=test_card)

    listing = commands.add_parser("cards", help="what the content holds")
    shared(listing)
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(run=cards)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    given = list(sys.argv[1:] if argv is None else argv)

    if not given:
        # Somebody double-clicked the executable. They did not come to read a
        # usage message: open the game and the browser looking at it.
        given = ["serve", "--open"]

    parser = build_parser()
    args = parser.parse_args(given)

    run: Any = args.run

    return int(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
