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
from fsme.content.errors import InvalidContentError
from fsme.journal import JournalFormatError

DEFAULT_NAMES = ("Ann", "Bo", "Cy", "Di")

VERSION = "0.1.1"


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

    Four places, in the order that puts the copy somebody is *working on* ahead
    of the copy they installed: the checkout they are standing in, the working
    directory, the cards inside the installed package, and the cards a frozen
    build unpacked beside itself. A card edited in a checkout must take effect
    without anybody remembering to pass a flag, or the authoring path has a
    trap in it.
    """
    if given:
        where = Path(given).expanduser().resolve()

        if not where.is_dir():
            raise SystemExit(
                f"no card content at {where}\n"
                f"  --content wants the directory holding the card sets — the"
                f" one with base_game/ in it."
            )

        return where

    here = Path(__file__).resolve()

    candidates = [
        here.parents[3] / "content",
        Path.cwd() / "content",
        here.parents[1] / "carddata",
    ]

    bundled = getattr(sys, "_MEIPASS", "")

    if bundled:
        # A frozen build carries the cards inside itself and unpacks them
        # beside the package, so that is the first place to look.
        candidates.insert(0, Path(bundled) / "content")

    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()

    raise SystemExit(
        "cannot find the cards.\n"
        "\n"
        "  fsme needs a directory of card sets to deal from, and this build\n"
        "  did not come with one. That usually means it was installed from a\n"
        "  source tree without the content/ directory.\n"
        "\n"
        "  Point it at one:\n"
        "      fsme cards --content /path/to/content\n"
        "\n"
        "  The directory wanted is the one holding base_game/ — `content/` in\n"
        "  a checkout of the project."
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

    server = _bound(lambda: build(session, host=args.host, port=args.port), args)
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

    server = _bound(
        lambda: build(session, bench, host=args.host, port=args.port), args
    )
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


def _bound(build: Any, args: argparse.Namespace) -> Any:
    """
    Open the socket, or say plainly why it could not be opened.

    Almost always: the port is taken, usually by an FSME left running in
    another window. That is an ordinary thing to do and does not deserve a
    stack trace ending in ``socketserver``.
    """
    try:
        return build()
    except OSError as refused:
        raise SystemExit(
            f"cannot listen on {args.host}:{args.port} — {refused.strerror or refused}\n"
            f"\n"
            f"  Something is already using that port; most likely another copy\n"
            f"  of fsme is still running. Either stop it, or pick another port:\n"
            f"      fsme {args.command} --port {args.port + 1}"
        ) from None


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


DEMO_SEED = 7
DEMO_PLAYERS = 3

DEMO_CARD = "loot_deck-cards_miscellaneous-four_souls-gold_key"
DEMO_GAMES = 40
DEMO_STUDY = 60

DEMO_JOBS = 4


def demo(args: argparse.Namespace) -> int:
    """
    Show somebody what this is, in about a minute, without any flags.

    The problem this solves is not that FSME lacks features. It is that all of
    them are behind a command with options, so a person who has just installed
    it has no way to find out whether it is worth their afternoon. This walks
    the path once — play a game, prove the record of it holds, read the report,
    then measure a card — narrating each step as it goes so the wait is legible.

    Every step is a command they can run themselves, and the command is printed
    above its output. Nothing here is a special mode: this is the ordinary
    engine and the ordinary reports.
    """
    from fsme.journal import replay_journal
    from fsme.journal import summarise as summarise_replay
    from fsme.lab.analysis import review, reviewed
    from fsme.lab.simulation import play_one

    root = content_root(args.content)
    loaded = load_content(root)

    def step(number: int, what: str, command: str) -> None:
        print(f"\n{'─' * 78}\n{number}. {what}\n   $ {command}\n", flush=True)

    started = time.perf_counter()

    print("FSME — a rules simulator for The Binding of Isaac: Four Souls.")
    print("This is what it does. Every step below is a command you can run.")

    step(1, "Play a game.", f"fsme play --seed {DEMO_SEED} --players {DEMO_PLAYERS}")

    journal, game = play_one(
        loaded, DEMO_SEED, DEMO_PLAYERS, thinking_seats=(0,)
    )

    state = game.state
    winner = state.players[state.winner].name if state.winner is not None else None

    print(
        f"   {winner or 'Nobody'} won on turn {state.turn.turn_number}"
        f" after {len(journal)} moves."
    )
    print("   The whole game was written down as it was played.")

    step(2, "Check the record still holds.", "fsme replay party.json")

    told = summarise_replay(replay_journal(journal, loaded), journal)

    print(
        f"   {told['replayed']} commands replayed, and the game came out the"
        f" same every step."
    )
    print("   That is what makes everything below evidence rather than a claim.")

    step(3, "Ask what happened, and where it was decided.", "fsme report party.json")

    print(reviewed(review(journal, loaded)))

    if args.quick:
        print("\n   (skipping the runs: --quick)")
    else:
        step(
            4,
            f"Play {DEMO_STUDY} more games and ask what they say.",
            f"fsme study --games {DEMO_STUDY} --players {DEMO_PLAYERS}",
        )
        print("   A few seconds…", flush=True)

        print(_a_study(root, loaded, args))

        step(
            5,
            f"Measure a card: {DEMO_GAMES} games with it, {DEMO_GAMES} without.",
            f"fsme test-card {DEMO_CARD} --games {DEMO_GAMES}",
        )
        print("   This takes about half a minute…", flush=True)

        told_about_card, _ = _one_card_test(
            argparse.Namespace(
                content=args.content,
                games=DEMO_GAMES,
                players=2,
                jobs=max(1, args.jobs),
                seed=0,
            ),
            DEMO_CARD,
            loaded.registry().get(DEMO_CARD).name,
        )

        from fsme.lab.analysis import read_out

        print(read_out(told_about_card))

        print(
            "   Removing a card reshuffles every game, so the report says what"
            " it\n   can and refuses to say what it cannot."
        )

    print(f"\n{'─' * 78}")
    print(f"That took {time.perf_counter() - started:.0f} seconds.")
    print("")
    print("Where to go from here:")
    print("  fsme desk --open     all of this on one page in a browser")
    print("  fsme study --games 200 --jobs 4      what a run says about the game")
    print("  fsme cards           what card content is loaded")
    print("  docs/DEMONSTRATION.md    the same tour, with commentary")

    return 0


def _a_study(root: Path, loaded: ContentLibrary, args: argparse.Namespace) -> str:
    """
    A small run, reported the way ``fsme study`` reports one.

    The same functions the command calls, so the tour cannot show something the
    command would not.
    """
    from fsme.lab.analysis import study as ask
    from fsme.lab.analysis import written
    from fsme.lab.simulation import run_on_many_cores

    names = {
        definition.id: definition.name for definition in loaded.definitions()
    }

    summaries = [
        done.summary
        for done in run_on_many_cores(
            root,
            DEMO_STUDY,
            DEMO_PLAYERS,
            jobs=max(1, args.jobs),
            offers=True,
            thinking_seats=(0,),
        )
        if done.summary is not None and not done.broke
    ]

    return written(ask(summaries, names=names), top=4)


COMMAND_GROUPS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "Start here",
        (
            ("demo", "the whole thing in a minute, no flags needed"),
            ("desk", "all of it on one page in a browser"),
            ("cards", "what card content is loaded"),
        ),
    ),
    (
        "Play",
        (
            ("play", "play a game through with nobody watching"),
            ("serve", "play one in a browser, move by move"),
        ),
    ),
    (
        "Read one game",
        (
            ("report", "everything the lab can say about one game"),
            ("explain", "why it went the way it did"),
            ("show", "the journal, read out loud"),
            ("replay", "play a journal back and check it still holds"),
        ),
    ),
    (
        "Measure many",
        (
            ("study", "play a run and ask what it says"),
            ("test-card", "the same seeds with a card and without it"),
            ("simulate", "play a run and count what happened"),
        ),
    ),
)
"""
The commands, in the order somebody meeting them should read them.

argparse lists subcommands in the order they were added and gives no way to
group them, which turns eleven commands into a wall with no way in. This is the
same list arranged by what a person is trying to do, and it is checked against
the parser by a test so it cannot drift.
"""


def _epilogue() -> str:
    lines = ["", "commands:"]

    for title, rows in COMMAND_GROUPS:
        lines.append(f"\n  {title}")

        for name, what in rows:
            lines.append(f"    {name:<12} {what}")

    lines += [
        "",
        "Every command takes --content to point at a different card directory.",
        "Run `fsme <command> --help` for what one of them accepts.",
    ]

    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fsme",
        description=(
            "Four Souls Multiverse Engine — a deterministic rules simulator.\n"
            "New here? Run `fsme demo`."
        ),
        epilog=_epilogue(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"fsme {VERSION}")

    commands = parser.add_subparsers(dest="command", metavar="<command>")

    def shared(sub: argparse.ArgumentParser) -> None:
        sub.add_argument("--content", help="where the card content lives")
        sub.add_argument("--seed", type=int, default=0, help="deal this game")
        sub.add_argument("--players", type=int, default=2, help="how many seats")

    web = commands.add_parser("serve")
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

    quick = commands.add_parser("play")
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

    reading = commands.add_parser("show")
    reading.add_argument("file", help="the journal to read")
    reading.add_argument(
        "--full", action="store_true", help="keep the engine's housekeeping too"
    )
    reading.set_defaults(run=show)

    again = commands.add_parser("replay")
    shared(again)
    again.add_argument("file", help="the journal to replay")
    again.add_argument("--json", action="store_true")
    again.set_defaults(run=replay)

    many = commands.add_parser("simulate")
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

    trial = commands.add_parser("test-card")
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

    asking = commands.add_parser("study")
    shared(asking)
    asking.add_argument("--games", type=int, default=100)
    asking.add_argument("--top", type=int, default=10)
    asking.add_argument("--jobs", type=int, default=1)
    asking.add_argument("--bot-seats", default="")
    asking.add_argument("--json", action="store_true")
    asking.set_defaults(run=study)

    telling = commands.add_parser("report")
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

    why = commands.add_parser("explain")
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

    door = commands.add_parser("desk")
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

    listing = commands.add_parser("cards")
    shared(listing)
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(run=cards)

    tour = commands.add_parser("demo")
    shared(tour)
    tour.add_argument("--jobs", type=int, default=4)
    tour.add_argument(
        "--quick", action="store_true", help="skip the card test at the end"
    )
    tour.set_defaults(run=demo)

    return parser


def _a_near_miss(parser: argparse.ArgumentParser, given: list[str]) -> None:
    """
    Catch a mistyped command before argparse lists all twelve of them.

    ``fsme repot`` is a typo, not a person browsing, and answering it with the
    whole vocabulary makes them find the answer themselves. Anything that is
    not close to a command falls through to argparse, whose listing is the
    right answer for somebody guessing.
    """
    from difflib import get_close_matches

    wanted = next((word for word in given if not word.startswith("-")), "")

    if not wanted:
        return

    known = _every_command(parser)

    if not known or wanted in known:
        return

    close = get_close_matches(wanted, sorted(known), n=1, cutoff=0.6)

    if not close:
        return

    raise SystemExit(
        f"fsme has no command {wanted!r} — did you mean `fsme {close[0]}`?\n"
        f"\n"
        f"  `fsme --help` lists them all, grouped by what they are for."
    )


def _every_command(parser: argparse.ArgumentParser) -> set[str]:
    for action in parser._subparsers._group_actions if parser._subparsers else ():  # noqa: SLF001
        if action.choices:
            return set(action.choices)

    return set()


def _speak_utf8() -> None:
    """
    Make sure the console can carry the characters the reports are written in.

    Windows gives a Python process a cp1252 console by default, and cp1252
    cannot encode a box-drawing rule. So ``fsme demo`` — the first thing anybody
    is told to run — died on its first line with a ``UnicodeEncodeError`` from
    inside ``print``, on Windows only. Nothing on this side of the machine
    could have noticed; CI did.

    Reconfiguring the stream is the whole fix: the bytes written become UTF-8,
    which every modern Windows terminal reads. Whether a particular font has a
    glyph for ``─`` is the terminal's business and not a crash. The fallbacks
    matter more than the happy path — a report that cannot be printed is worth
    less than a report printed with question marks in it.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)

        if reconfigure is None:
            # Not a real stream: something has replaced it, and replacing it
            # back would be ruder than leaving it alone.
            continue

        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError, AttributeError):
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError, AttributeError):
                pass


def main(argv: Sequence[str] | None = None) -> int:
    _speak_utf8()

    given = list(sys.argv[1:] if argv is None else argv)

    if not given:
        # Somebody double-clicked the executable. They did not come to read a
        # usage message: open the front door and a browser looking at it.
        given = ["desk", "--open"]

    parser = build_parser()

    _a_near_miss(parser, given)

    args = parser.parse_args(given)

    run: Any = args.run

    try:
        return int(run(args))
    except FileNotFoundError as missing:
        print(f"\nno such file: {missing.filename}\n", file=sys.stderr)
        print(
            "  A journal is written by `fsme play --journal <file>`, or by the\n"
            "  desk into its work directory. `fsme demo` makes one without\n"
            "  being asked.",
            file=sys.stderr,
        )

        return 2
    except JournalFormatError as complaint:
        print(f"\n{complaint}\n", file=sys.stderr)
        print(
            "  That file is not a journal this engine can read. Journals come\n"
            "  from `fsme play --journal <file>`; a save file or a bare JSON\n"
            "  document is not one.",
            file=sys.stderr,
        )

        return 2
    except InvalidContentError as complaint:
        # A person writing a card is the likeliest reader of this, and a
        # traceback tells them about the loader when they wanted to be told
        # about their card. The report already names the file, the card and
        # the ability; printing it alone is the whole fix.
        print(f"\n{complaint}\n", file=sys.stderr)
        print(
            "Nothing was loaded. Fix the cards above and run it again;"
            " `fsme cards`\nis the quickest way to check.",
            file=sys.stderr,
        )

        return 2
    except KeyboardInterrupt:
        print("", flush=True)

        return 130


if __name__ == "__main__":
    raise SystemExit(main())
