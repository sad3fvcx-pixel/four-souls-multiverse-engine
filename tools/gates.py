#!/usr/bin/env python3

"""
The two gates that watch what the engine produces, kept where anybody can run them.

**writeback** opens every shipped card in the Constructor, writes it back, and
reads the result again. Every card has to come back as the same card, every card
with rules has to pass the checker, and the whole written corpus — one JSON
document, keys sorted — has to be byte for byte the one recorded.

**replay** plays a fixed range of seeds with every seat thinking, reduces each
game to one small record, and hashes the lot. A change anywhere in the engine
that changes any game changes the hash.

What the hashes should be is in ``tools/gate_references.json``, beside the
parameters that give them their meaning. A hash that stops matching says only
that something changed. Which cards or seeds, and how, is ``diagnose``'s job:
it runs the same computation over another commit, unpacked somewhere temporary,
and compares the two. It never touches this checkout and never uses the network.

Usage::

    python tools/gates.py check                          # both gates
    python tools/gates.py check --gate replay
    python tools/gates.py diagnose --against HEAD~1      # what changed, and where
    python tools/gates.py compute --root DIR --gate writeback --out FILE

Exit codes: 0 the gate holds (or nothing differs), 1 it does not (or something
does), 2 the question could not be asked — bad arguments, a ref not available
here, or code from somewhere other than the root it was meant to come from.

Every computation runs in a fresh interpreter, with the root's own ``src`` in
front of everything else on the path, and refuses to go on if the engine it
imported lives anywhere else. Both sides of a comparison are worked out by this
file's code; only the engine and the cards differ.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parents[1]
REFERENCES = HERE / "tools" / "gate_references.json"
GATES = ("writeback", "replay")
SUMMARY = "GATE-SUMMARY "
SHOWN = 20


class Unaskable(Exception):
    """The question could not be asked. Exit code 2."""


def md5(data: bytes) -> str:
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


# ----------------------------------------------------------------------
# compute: one gate, one root, run in an interpreter of its own
# ----------------------------------------------------------------------

_ROOT = Path()
_PLAYERS = 0
_STEPS = 0
_RNG_MODEL = "1"
_library: Any = None

LEGACY_RNG_MODEL = "1"
"""
The RNG model the replay gate plays when its reference does not name one.

The reference was taken on model 1, and every journal, recording and save made
before model 2 existed plays back on model 1 — so the gate keeps asking the
engine for model 1 by name, whatever a new game is dealt on by default. An
engine from before there was a choice plays model 1 anyway, and is asked
without the argument it would not know.
"""


def _use(root: Path) -> None:
    """
    Put this root's engine first, and make sure it is the one imported.

    The installed package, an editable install of another checkout or a
    ``PYTHONPATH`` would all be found otherwise, and a comparison of a commit
    with itself proves nothing.
    """
    src = str(root / "src")

    if not sys.path or sys.path[0] != src:
        sys.path.insert(0, src)

    import fsme

    found = Path(fsme.__file__).resolve()

    if not found.is_relative_to(root.resolve()):
        raise Unaskable(f"imported fsme from {found}, not from {root}")


def _enter(root: str, players: int, steps: int, rng_model: str = LEGACY_RNG_MODEL) -> None:
    """Each replay worker: the same root and the same game, under fork or spawn."""
    global _ROOT, _PLAYERS, _STEPS, _RNG_MODEL

    _ROOT, _PLAYERS, _STEPS, _RNG_MODEL = Path(root), players, steps, rng_model
    _use(_ROOT)


def _shipped_cards(root: Path) -> list[tuple[str, Path, dict[str, Any]]]:
    """Every shipped card as the loader sees it: (set_id, path, raw dict)."""
    from fsme.content.loader import ContentLoader

    out = []

    for d in ContentLoader()._expansion_directories(root / "content"):
        set_id = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["id"]

        for p in sorted(d.rglob("*.json")):
            if p.name == "manifest.json" or p.name.startswith("_"):
                continue

            data = json.loads(p.read_text(encoding="utf-8"))
            cards = data["cards"] if isinstance(data, dict) and "cards" in data else (
                data if isinstance(data, list) else [data])

            for card in cards:
                out.append((set_id, p, card))

    return out


def _has_rules(card: dict[str, Any]) -> bool:
    return bool(card.get("abilities") or card.get("statics"))


def _writeback(root: Path) -> tuple[bytes, dict[str, Any]]:
    from fsme.lab.desk.author import build_card, check_card, read_card

    total = readable = stable = ruled = clean = 0
    bad: list[Any] = []
    written = {}

    for set_id, _path, card in _shipped_cards(root):
        total += 1

        try:
            before = read_card(card, set_id=set_id)
            readable += 1
        except Exception as e:
            bad.append((card.get("id"), "unreadable", str(e)))
            continue

        try:
            made = build_card(before)
            written[card["id"]] = made

            if read_card(made, set_id=set_id) == before:
                stable += 1
            else:
                bad.append((card.get("id"), "unstable", ""))
        except Exception as e:
            bad.append((card.get("id"), "rewrite", str(e)))
            continue

        if _has_rules(card):
            ruled += 1
            said = check_card(made)

            if said == []:
                clean += 1
            else:
                bad.append((card.get("id"), "dirty", said))

    data = json.dumps(written, sort_keys=True, indent=1).encode("utf-8")
    summary = {
        "total": total,
        "readable": readable,
        "stable": stable,
        "ruled": ruled,
        "clean": clean,
        "bad": [list(map(str, one)) for one in bad],
    }

    return data, summary


def _library_once() -> Any:
    global _library

    if _library is None:
        from fsme.api import load_content

        _library = load_content(_ROOT / "content")

    return _library


def _one_game(seed: int) -> dict[str, Any]:
    from fsme.lab.simulation.runner import play_one

    rec: dict[str, Any] = {"seed": seed, "broke": ""}

    try:
        if "rng_model" in inspect.signature(play_one).parameters:
            model: dict[str, Any] = {"rng_model": _RNG_MODEL}
        elif _RNG_MODEL == LEGACY_RNG_MODEL:
            model = {}
        else:
            raise Unaskable(f"this engine plays only RNG model {LEGACY_RNG_MODEL}")

        journal, game = play_one(_library_once(), seed, _PLAYERS, steps=_STEPS,
                                 thinking_seats=tuple(range(_PLAYERS)), **model)
        counted: Counter[str] = Counter()

        for entry in journal.entries:
            for event in entry.events:
                counted[str(getattr(event, "type", ""))] += 1

        rec.update(
            over=bool(game.is_over),
            moves=len(journal.entries),
            events=sum(counted.values()),
            counted=dict(sorted(counted.items())),
            digest=journal.entries[-1].digest if journal.entries else "",
            hp=[int(p.hp) for p in game.state.players],
            active=int(game.state.turn.active_player),
        )
    except Exception as exc:
        rec["broke"] = f"{type(exc).__name__}: {exc}"[:300]

    return rec


def _replay(root: Path, reference: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    first, last = (int(one) for one in reference["seeds"])
    players, steps = int(reference["players"]), int(reference["steps"])
    model = str(reference.get("rng_model", LEGACY_RNG_MODEL))

    with ProcessPoolExecutor(
        max_workers=os.cpu_count(),
        initializer=_enter,
        initargs=(str(root), players, steps, model),
    ) as pool:
        rows = list(pool.map(_one_game, range(first, last + 1), chunksize=8))

    data = "\n".join(json.dumps(r, sort_keys=True) for r in rows).encode("utf-8")
    summary = {
        "games": len(rows),
        "broke": sum(1 for r in rows if r["broke"]),
        "over": sum(1 for r in rows if r.get("over")),
    }

    return data, summary


def compute(root: Path, gate: str, out: Path, references: Path) -> int:
    try:
        reference = _references(references)[gate]
        _use(root)

        if gate == "writeback":
            data, summary = _writeback(root)
        else:
            data, summary = _replay(root, reference)
    except Unaskable as unaskable:
        print(f"compute: {unaskable}", file=sys.stderr)
        return 2

    out.write_bytes(data)
    summary["md5"] = md5(data)
    print(SUMMARY + json.dumps(summary, sort_keys=True))

    return 0


# ----------------------------------------------------------------------
# Running compute in another interpreter
# ----------------------------------------------------------------------


def _computed(
    root: Path, gate: str, out: Path, references: Path
) -> tuple[bytes, dict[str, Any]]:
    """
    One gate over one root, in a fresh interpreter that writes no bytecode.

    Fresh so that nothing imported from one root is still there when the
    other is asked; without bytecode so that working the current checkout out
    leaves nothing in it.
    """
    ran = subprocess.run(
        [
            sys.executable, "-B", str(Path(__file__).resolve()), "compute",
            "--root", str(root), "--gate", gate, "--out", str(out),
            "--reference", str(references),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    said = [line for line in ran.stdout.splitlines() if line.startswith(SUMMARY)]

    if ran.returncode != 0 or not said:
        raise Unaskable(
            f"{gate} could not be computed for {root}:\n{ran.stderr.strip()}"
        )

    return out.read_bytes(), json.loads(said[-1][len(SUMMARY):])


def _references(path: Path) -> dict[str, Any]:
    try:
        references = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Unaskable(f"cannot read references {path}: {error}") from error

    for gate, needs in (
        ("writeback", ("md5",)),
        ("replay", ("md5", "seeds", "players", "steps", "python")),
    ):
        missing = [key for key in needs if key not in references.get(gate, {})]

        if missing:
            raise Unaskable(f"{path}: '{gate}' says nothing of {', '.join(missing)}")

    return dict(references)


# ----------------------------------------------------------------------
# check
# ----------------------------------------------------------------------


def _writeback_holds(summary: dict[str, Any]) -> bool:
    return (
        summary["readable"] == summary["total"]
        and summary["stable"] == summary["total"]
        and summary["clean"] == summary["ruled"]
        and not summary["bad"]
    )


def check(gates: tuple[str, ...], references_path: Path) -> int:
    references = _references(references_path)
    wrong = False

    with tempfile.TemporaryDirectory() as scratch:
        for gate in gates:
            reference = references[gate]

            if gate == "replay":
                running = f"{sys.version_info.major}.{sys.version_info.minor}"

                if running != str(reference["python"]):
                    raise Unaskable(
                        f"replay is recorded under Python {reference['python']},"
                        f" and this is {running}"
                    )

            _, summary = _computed(
                HERE, gate, Path(scratch) / gate, references_path
            )
            matches = summary["md5"] == reference["md5"]

            print(f"{gate}: md5 {summary['md5']} (reference {reference['md5']})")

            if gate == "writeback":
                holds = _writeback_holds(summary)
                print(
                    f"  cards {summary['readable']}/{summary['total']} read,"
                    f" {summary['stable']}/{summary['total']} stable;"
                    f" rules {summary['clean']}/{summary['ruled']} clean;"
                    f" bad {len(summary['bad'])}"
                )

                for one in summary["bad"][:SHOWN]:
                    print(f"    {one}")
            else:
                holds = True
                print(
                    f"  games {summary['games']}, broke {summary['broke']},"
                    f" over {summary['over']}"
                )

            verdict = matches and holds
            wrong = wrong or not verdict
            print(f"  {'holds' if verdict else 'DOES NOT HOLD'}")

    return 1 if wrong else 0


# ----------------------------------------------------------------------
# diagnose
# ----------------------------------------------------------------------


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(HERE), *args], capture_output=True, text=True, check=False
    )


def _untouched() -> tuple[str, str]:
    """What has to be the same after a diagnosis as before it."""
    return (
        _git("status", "--porcelain", "--untracked-files=all", "--ignored").stdout,
        _git("stash", "list").stdout,
    )


def _resolve(ref: str) -> str:
    if not ref or ref.startswith("-"):
        raise Unaskable(f"'{ref}' is not a ref")

    found = _git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")

    if found.returncode != 0 or not found.stdout.strip():
        raise Unaskable(
            f"'{ref}' is not a commit available in this repository; nothing is"
            " fetched here, so fetch it first if it exists elsewhere"
        )

    return found.stdout.strip()


def _unpack(commit: str, into: Path) -> None:
    """The commit's files, from git's own objects, into a directory of their own."""
    archive = subprocess.Popen(
        ["git", "-C", str(HERE), "archive", "--format=tar", commit],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert archive.stdout is not None

    with tarfile.open(fileobj=archive.stdout, mode="r|") as tar:
        tar.extractall(into, filter="data")

    _, error = archive.communicate()

    if archive.returncode != 0:
        raise Unaskable(f"git archive {commit} failed: {error.decode().strip()}")


def _differences(was: Any, now: Any, path: str = "") -> list[str]:
    """Where two written cards part, key by key."""
    if isinstance(was, dict) and isinstance(now, dict):
        found = []

        for key in sorted(set(was) | set(now), key=str):
            here = f"{path}.{key}" if path else str(key)

            if key not in was:
                found.append(f"{here}: added {json.dumps(now[key], sort_keys=True)}")
            elif key not in now:
                found.append(f"{here}: removed {json.dumps(was[key], sort_keys=True)}")
            else:
                found.extend(_differences(was[key], now[key], here))

        return found

    if isinstance(was, list) and isinstance(now, list) and len(was) == len(now):
        found = []

        for index, (one, other) in enumerate(zip(was, now, strict=True)):
            found.extend(_differences(one, other, f"{path}[{index}]"))

        return found

    if was == now:
        return []

    return [
        f"{path or '.'}: {json.dumps(was, sort_keys=True)}"
        f" -> {json.dumps(now, sort_keys=True)}"
    ]


def _shown(items: list[Any], full: bool) -> list[Any]:
    return items if full else items[:SHOWN]


def _compare_writeback(was: bytes, now: bytes, full: bool) -> bool:
    a, b = json.loads(was), json.loads(now)
    added = sorted(set(b) - set(a))
    removed = sorted(set(a) - set(b))
    changed = sorted(key for key in set(a) & set(b) if a[key] != b[key])

    print(f"  cards: {len(a)} vs {len(b)}")
    print(f"  added: {len(added)} {_shown(added, full)}")
    print(f"  removed: {len(removed)} {_shown(removed, full)}")
    print(f"  changed: {len(changed)} {_shown(changed, full)}")

    for key in _shown(changed, full):
        print(f"  {key}:")

        for line in _shown(_differences(a[key], b[key]), full):
            print(f"    {line}")

    if not full and (len(changed) > SHOWN or any(
        len(_differences(a[key], b[key])) > SHOWN for key in changed[:SHOWN]
    )):
        print(f"  (only the first {SHOWN} shown; --full for everything)")

    return bool(added or removed or changed)


def _compare_replay(was: bytes, now: bytes, full: bool) -> bool:
    def load(data: bytes) -> dict[Any, dict[str, Any]]:
        out = {}

        for line in data.decode("utf-8").splitlines():
            if not line.strip():
                continue

            rec = json.loads(line)
            out[rec["seed"]] = rec

        return out

    a, b = load(was), load(now)
    shared = sorted(set(a) & set(b))
    diff = [s for s in shared if a[s] != b[s]]

    print(f"  seeds: {len(a)} vs {len(b)}  same set: {set(a) == set(b)}")
    print(f"  identical: {len(shared) - len(diff)} / {len(shared)}")
    print(f"  differing seeds: {_shown(diff, full)}")
    print(f"  broke in second: {[s for s in b if b[s].get('broke')]}")
    print(f"  not over in second: {[s for s in b if not b[s].get('over')]}")

    for s in _shown(diff, full):
        for k in sorted(set(a[s]) | set(b[s])):
            if a[s].get(k) != b[s].get(k) and k != "counted":
                print(f"    seed {s} {k}: {a[s].get(k)} -> {b[s].get(k)}")

    if not full and len(diff) > SHOWN:
        print(f"  (only the first {SHOWN} seeds shown; --full for everything)")

    return bool(diff) or set(a) != set(b)


COMPARE: dict[str, Callable[[bytes, bytes, bool], bool]] = {
    "writeback": _compare_writeback,
    "replay": _compare_replay,
}


def diagnose(ref: str, gates: tuple[str, ...], full: bool) -> int:
    commit = _resolve(ref)
    before = _untouched()
    differs = False

    print(f"against: {ref} = {commit}")
    print(f"tree: {'dirty' if _git('status', '--porcelain').stdout.strip() else 'clean'}")

    with tempfile.TemporaryDirectory() as scratch:
        theirs = Path(scratch) / "root"
        theirs.mkdir()
        _unpack(commit, theirs)

        for gate in gates:
            was, was_said = _computed(
                theirs, gate, Path(scratch) / f"{gate}.was", REFERENCES
            )
            now, now_said = _computed(
                HERE, gate, Path(scratch) / f"{gate}.now", REFERENCES
            )

            print(f"{gate}: md5 {was_said['md5']} (ref) vs {now_said['md5']} (tree)")

            if gate == "writeback":
                for side, said in (("ref", was_said), ("tree", now_said)):
                    print(
                        f"  {side}: cards {said['stable']}/{said['total']} stable,"
                        f" rules {said['clean']}/{said['ruled']} clean,"
                        f" bad {len(said['bad'])}"
                    )

            differs = COMPARE[gate](was, now, full) or differs

    if _untouched() != before:
        raise Unaskable("the working tree or the stash changed while diagnosing")

    print("differs" if differs else "identical")

    return 1 if differs else 0


# ----------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    checking = commands.add_parser("check", help="this checkout against the references")
    checking.add_argument("--gate", choices=(*GATES, "all"), default="all")
    checking.add_argument("--reference", type=Path, default=REFERENCES)

    diagnosing = commands.add_parser("diagnose", help="this tree against a commit")
    diagnosing.add_argument("--against", required=True)
    diagnosing.add_argument("--gate", choices=(*GATES, "all"), default="all")
    diagnosing.add_argument("--full", action="store_true")

    computing = commands.add_parser("compute", help="one gate over one root")
    computing.add_argument("--root", type=Path, required=True)
    computing.add_argument("--gate", choices=GATES, required=True)
    computing.add_argument("--out", type=Path, required=True)
    computing.add_argument("--reference", type=Path, default=REFERENCES)

    args = parser.parse_args(argv)

    try:
        if args.command == "compute":
            return compute(args.root.resolve(), args.gate, args.out, args.reference)

        gates = GATES if args.gate == "all" else (args.gate,)

        if args.command == "check":
            return check(gates, args.reference)

        return diagnose(args.against, gates, args.full)
    except Unaskable as unaskable:
        print(f"{args.command}: {unaskable}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
