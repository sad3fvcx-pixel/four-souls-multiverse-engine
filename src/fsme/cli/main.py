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
import sys
import time
import webbrowser
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fsme.api import Session, load_content
from fsme.content import ContentLibrary

DEFAULT_NAMES = ("Ann", "Bo", "Cy", "Di")

VERSION = "0.1.0"


def seats_of(given: str) -> tuple[int, ...]:
    """
    Read a comma-separated list of seats.
    """
    if not given.strip():
        return ()

    return tuple(
        int(part) for part in given.replace(" ", "").split(",") if part.isdigit()
    )


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


def front(args: argparse.Namespace) -> int:
    """
    Open the front door: everything the engine and the lab do, on one page.

    The value of this project has been behind commands with flags, which is
    fine for whoever wrote them and no use to anybody else. This is the same
    functions with buttons in front of them — the page prints exactly what the
    matching command prints, so there is one answer and not two.
    """
    from fsme.lab.desk import Workbench
    from fsme.lab.desk import desk as build

    root = content_root(args.content)
    loaded = load_content(root)

    bench = Workbench(loaded, root, Path(args.work).expanduser().resolve())

    session = Session(
        loaded,
        players=args.players,
        seed=args.seed,
        interactive_priority=not args.no_priority,
    )

    server = build(session, bench, host=args.host, port=args.port)
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

    This is here because a person setting the engine up wants to know it runs,
    and a game played end to end says so more convincingly than a version
    number. It is the same game a simulation plays, one of it.

    With ``--journal`` the whole game is written down as it goes: what was
    offered, what was chosen, why — if a bot was choosing — and everything that
    followed.
    """
    from fsme.lab.simulation import play_one

    thinking = seats_of(args.bot_seats)

    journal, game = play_one(
        library(args),
        args.seed,
        args.players,
        steps=args.steps,
        offers=bool(args.journal and args.offers),
        thinking_seats=thinking,
    )

    state = game.state

    if state.game_over and state.winner is not None:
        print(
            f"{state.players[state.winner].name} won on turn "
            f"{state.turn.turn_number} after {len(journal)} moves"
        )

        outcome = 0
    else:
        print(f"unfinished after {len(journal)} moves")

        outcome = 1

    if args.journal:
        written = journal.save(args.journal)

        print(f"journal written to {written} ({len(journal)} commands)")

    return outcome


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


def report(args: argparse.Namespace) -> int:
    """
    Read one game every way the lab knows how, and write it out once.

    The command the others were building towards: a journal in, a report out,
    no flags needed to get the whole picture.
    """
    from fsme.journal import Journal
    from fsme.lab.analysis import review, reviewed

    loaded = library(args)

    if args.file:
        journal = Journal.load(args.file)
    else:
        from fsme.lab.simulation import play_one

        journal, _ = play_one(
            loaded,
            args.seed,
            args.players,
            thinking_seats=seats_of(args.bot_seats),
        )

    told = review(
        journal,
        loaded,
        moments=args.moments,
        decisions=0 if args.quick else args.decisions,
    )

    if args.json:
        print(json.dumps(told.to_dict(), indent=2))

        return 0

    print(reviewed(told))

    return 0


def study(args: argparse.Namespace) -> int:
    """
    Play a run and ask it the questions a pile of games can answer.
    """
    from fsme.lab.analysis import study as ask
    from fsme.lab.analysis import written
    from fsme.lab.simulation import run_on_many_cores

    loaded = library(args)
    names = {
        definition.id: definition.name for definition in loaded.definitions()
    }

    summaries = []
    broken = []

    started = time.perf_counter()

    for done in run_on_many_cores(
        content_root(args.content),
        args.games,
        args.players,
        jobs=max(1, args.jobs),
        first_seed=args.seed,
        offers=True,
        thinking_seats=seats_of(args.bot_seats),
    ):
        if done.broke:
            broken.append((done.seed, done.broke))

            continue

        if done.summary is not None:
            summaries.append(done.summary)

    told = ask(summaries, names=names)

    spent = time.perf_counter() - started

    if args.json:
        print(json.dumps(told.to_dict(), indent=2))

        return 0

    print(written(told, top=args.top))

    for seed, why in broken[:5]:
        print(f"  seed {seed} fell over — {why}")

    print(f"{args.games} games in {spent:.1f}s")

    return 0


def explain(args: argparse.Namespace) -> int:
    """
    Say why one game went the way it did, and where it was decided.
    """
    from fsme.journal import Journal
    from fsme.lab.analysis import explain as tell
    from fsme.lab.analysis import risks as weigh
    from fsme.lab.analysis import summarise, turning_points

    loaded = library(args)

    if args.file:
        journal = Journal.load(args.file)
    else:
        from fsme.lab.simulation import play_one

        journal, _ = play_one(
            loaded,
            args.seed,
            args.players,
            thinking_seats=seats_of(args.bot_seats),
        )

    turning = (
        None if args.moments <= 0 else turning_points(journal, top=args.moments)
    )

    # The replay costs a whole game, so it is asked for rather than assumed.
    dangers = (
        weigh(
            journal,
            loaded,
            top=args.decisions,
            seat=None if args.seat is None else int(args.seat),
        )
        if args.decisions > 0
        else None
    )

    print(tell(summarise(journal), turning=turning, dangers=dangers))

    return 0


def simulate(args: argparse.Namespace) -> int:
    """
    Play a run of games and say what happened across all of them.
    """
    from fsme.lab.analysis import Tally, report
    from fsme.lab.simulation import run as play_them

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

    thinking = seats_of(args.bot_seats)

    if args.jobs > 1:
        from fsme.lab.simulation import run_on_many_cores

        for done in run_on_many_cores(
            content_root(args.content),
            args.games,
            args.players,
            jobs=args.jobs,
            first_seed=args.seed,
            offers=args.offers,
            journals_into=into,
            thinking_seats=thinking,
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
            thinking_seats=thinking,
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
    if thinking:
        print(
            f"Seats {', '.join(str(seat) for seat in thinking)} played by the "
            f"bot; the rest chose at random among legal moves."
        )
    else:
        print(
            "Played by a table that chooses at random among legal moves. These "
            "are numbers about the game under random play, not about how it "
            "plays."
        )

    if into is not None:
        print(f"journals written to {into}")

    return 0


def test_card(args: argparse.Namespace) -> int:
    """
    Play the same seeds with a card in the game and without it, and compare.

    With ``--from-study`` the subjects come from a study's own list of cards
    worth testing, which closes the loop the two commands were written for: a
    run says a card looks odd, and the test says whether it is.
    """
    from fsme.lab.analysis import read_out

    loaded = library(args)

    subjects = list(_subjects(args))

    if not subjects:
        print("nothing to test — name a card, or pass --from-study a study")

        return 2

    tested: list[Any] = []

    for card in subjects:
        try:
            named = loaded.registry().get(card)
        except Exception:
            print(f"no card called {card!r} — try `fsme cards` to see the sets")

            return 2

        told, broken = _one_card_test(args, card, named.name)

        tested.append(told)

        if args.json:
            continue

        print(read_out(told))

        for label, failures in broken.items():
            for failure in failures[:5]:
                print(f"  fell over {label} it — {failure}")

    if args.json:
        written = [told.to_dict() for told in tested]

        print(json.dumps(written if len(written) > 1 else written[0], indent=2))

        return 0

    if len(tested) > 1:
        # The point of a queue of tests is the list at the end of it.
        print("=" * 78)
        print("Verdicts")
        print("=" * 78)
        print("")

        for told in tested:
            print(f"  {told.subject}")
            print(f"    {told.verdict}")

        print("")

    return 0


def _subjects(args: argparse.Namespace) -> Sequence[str]:
    """
    The cards to put under test: the one named, or a study's suspects.
    """
    if args.card:
        return [str(args.card)]

    if not args.from_study:
        return []

    read = json.loads(Path(args.from_study).expanduser().read_text("utf-8"))

    suspects = read.get("suspects") or []

    return [str(suspect["card"]) for suspect in suspects[: max(1, args.top)]]


def _one_card_test(
    args: argparse.Namespace, card: str, name: str
) -> tuple[Any, dict[str, list[str]]]:
    """
    Play both runs for one card and compare them.
    """
    from fsme.lab.analysis import Tally, compare
    from fsme.lab.simulation import run_on_many_cores

    root = content_root(args.content)

    runs: dict[str, Tally] = {}
    broken: dict[str, list[str]] = {"with": [], "without": []}
    appeared = 0

    for label, drop in (("with", ()), ("without", (card,))):
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
            seen = tally.cards.get(card)
            appeared = seen.games if seen else 0

    return (
        compare(
            f"{name} ({card})",
            runs["with"],
            runs["without"],
            appeared=appeared,
            errors_with=len(broken["with"]),
            errors_without=len(broken["without"]),
        ),
        broken,
    )


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
        "--bot-seats",
        default="",
        help="seats played by the bot, comma separated; the rest play at random",
    )
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
    many.add_argument(
        "--bot-seats",
        default="",
        help="seats played by the bot, comma separated; the rest play at random",
    )
    many.set_defaults(run=simulate)

    trial = commands.add_parser(
        "test-card", help="play the game with a card and without it"
    )
    shared(trial)
    trial.add_argument(
        "card", nargs="?", help="the identifier of the card under test"
    )
    trial.add_argument(
        "--from-study",
        help="a `study --json` file; test the cards it says are worth testing",
    )
    trial.add_argument(
        "--top", type=int, default=3, help="how many of them to test"
    )
    trial.add_argument("--games", type=int, default=100, help="games in each run")
    trial.add_argument("--jobs", type=int, default=1)
    trial.add_argument("--json", action="store_true")
    trial.set_defaults(run=test_card)

    asking = commands.add_parser(
        "study", help="play a run and ask what it says about the game"
    )
    shared(asking)
    asking.add_argument("--games", type=int, default=100)
    asking.add_argument("--top", type=int, default=10)
    asking.add_argument("--jobs", type=int, default=1)
    asking.add_argument("--bot-seats", default="")
    asking.add_argument("--json", action="store_true")
    asking.set_defaults(run=study)

    telling = commands.add_parser(
        "report", help="one game, read every way the lab knows how"
    )
    shared(telling)
    telling.add_argument(
        "file", nargs="?", help="a journal; without one, play a game"
    )
    telling.add_argument("--bot-seats", default="")
    telling.add_argument("--moments", type=int, default=3)
    telling.add_argument("--decisions", type=int, default=3)
    telling.add_argument(
        "--quick",
        action="store_true",
        help="skip the replay, and with it the decisions",
    )
    telling.add_argument("--json", action="store_true")
    telling.set_defaults(run=report)

    why = commands.add_parser("explain", help="why one game went the way it did")
    shared(why)
    why.add_argument("file", nargs="?", help="a journal; without one, play a game")
    why.add_argument("--bot-seats", default="")
    why.add_argument(
        "--moments",
        type=int,
        default=3,
        help="how many turning points to name; 0 for none",
    )
    why.add_argument(
        "--decisions",
        type=int,
        default=3,
        help="how many decisions to weigh against the bot; 0 to skip the replay",
    )
    why.add_argument(
        "--seat", type=int, help="weigh only this seat's decisions"
    )
    why.set_defaults(run=explain)

    door = commands.add_parser(
        "desk", help="everything FSME does, on one page in a browser"
    )
    shared(door)
    door.add_argument("--host", default="127.0.0.1")
    door.add_argument("--port", type=int, default=8000)
    door.add_argument("--open", action="store_true", help="open a browser too")
    door.add_argument(
        "--no-priority",
        action="store_true",
        help="resolve priority windows without asking",
    )
    door.add_argument(
        "--work",
        default="fsme-work",
        help="where games played from the page are kept",
    )
    door.set_defaults(run=front)

    listing = commands.add_parser("cards", help="what the content holds")
    shared(listing)
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(run=cards)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    given = list(sys.argv[1:] if argv is None else argv)

    if not given:
        # Somebody double-clicked the executable. They did not come to read a
        # usage message: open the front door and a browser looking at it.
        given = ["desk", "--open"]

    parser = build_parser()
    args = parser.parse_args(given)

    run: Any = args.run

    return int(run(args))


if __name__ == "__main__":
    raise SystemExit(main())
