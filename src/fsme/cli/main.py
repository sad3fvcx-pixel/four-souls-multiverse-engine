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
import webbrowser
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fsme.api import Session, load_content
from fsme.content import ContentLibrary

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
    """
    from fsme.api.moves import legal_moves

    session = Session(
        library(args),
        players=args.players,
        seed=args.seed,
        interactive_priority=False,
    )

    game = session.game
    rng = random.Random(args.seed)

    for step in range(args.steps):
        if game.is_over:
            winner = game.state.players[game.state.winner or 0]

            print(
                f"{winner.name} won on turn {game.state.turn.turn_number} "
                f"after {step} moves"
            )

            return 0

        decision = game.runtime.awaiting_decision

        if decision is not None:
            count = len(decision.options)
            lowest = max(0, min(decision.minimum, count))
            highest = max(lowest, min(decision.maximum, count))

            session.submit(
                {
                    "type": "choose_target",
                    "player": decision.player,
                    "payload": {
                        "choices": rng.sample(
                            range(count), rng.randint(lowest, highest)
                        )
                        if count
                        else []
                    },
                }
            )

            continue

        moves = legal_moves(game)

        if not moves:
            print(f"nothing could be done after {step} moves")

            return 1

        session.submit(rng.choice(moves))

    print(f"still going after {args.steps} moves")

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

    commands = parser.add_subparsers(dest="command", required=True)

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
    quick.set_defaults(run=play)

    listing = commands.add_parser("cards", help="what the content holds")
    shared(listing)
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(run=cards)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    run: Any = args.run

    return int(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
