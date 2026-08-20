# src/fsme/scenario/library.py

"""
A folder of experiments.

Deliberately almost nothing. A library here is a directory of scenario files
and a way to ask for one by name — not a manager, not an index, not a place
that knows what happened when a scenario was run. Results belong to journals,
and a library that also held them would be two things badly.

**One file per scenario, and the scenario carries its own name.** The other
shape — a directory per scenario with a `metadata.json` beside it — was
considered and refused: it splits one record into two files that have to agree,
and the scenario format already carries everything the second one would hold.
A file that describes an experiment should be the whole description of it.

**What identifies a scenario is two different things, because two different
questions get asked.** `id` names the experiment somebody is maintaining, and
survives being edited: renaming a study does not make it a different study. The
digest identifies the configuration, and changes the moment the game it sets up
changes. A library is indexed by the first; a journal records both. Neither
substitutes for the other, and a filename is neither — it is a place, not a
name, and moving a file must not rename the thing inside it.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ScenarioError
from .file import load
from .scenario import Scenario, digest_of

SCENARIO_SUFFIX = ".json"


@dataclass(frozen=True, slots=True)
class Entry:
    """
    One scenario in a library, and where it was found.
    """

    scenario: Scenario
    path: Path

    @property
    def id(self) -> str:
        """
        What this scenario is called, falling back to its file name.

        A scenario without an id is still usable from a library — somebody
        wrote one file and did not think about names — and the file it was
        found in is the least surprising thing to call it. A scenario that
        names itself is never renamed by where it happens to sit.
        """
        return self.scenario.id or self.path.stem

    @property
    def digest(self) -> str:
        return digest_of(self.scenario)

    def __str__(self) -> str:
        name = self.scenario.name or self.id

        return f"{self.id}  {name}"


@dataclass(frozen=True, slots=True)
class Library:
    """
    Every scenario in one directory.
    """

    entries: dict[str, Entry] = field(default_factory=dict)
    root: Path | None = None

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self) -> Iterator[Entry]:
        for key in sorted(self.entries):
            yield self.entries[key]

    def __contains__(self, scenario_id: object) -> bool:
        return scenario_id in self.entries

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.entries))

    def get(self, scenario_id: str) -> Scenario:
        """
        The scenario called this, or a refusal saying what is here instead.
        """
        entry = self.entries.get(scenario_id)

        if entry is None:
            known = ", ".join(self.ids()) or "nothing"

            raise ScenarioError(
                f"no scenario called '{scenario_id}'; this library holds {known}"
            )

        return entry.scenario

    def entry(self, scenario_id: str) -> Entry:
        self.get(scenario_id)

        return self.entries[scenario_id]


def open_library(root: Path | str) -> Library:
    """
    Read every scenario in a directory.

    The whole directory at once, and every problem reported together, because
    a library with one unreadable file in it is a library somebody is about to
    fix — and finding out one file at a time is the slow way to do that.

    Not recursive. A folder of experiments is a folder, and walking into
    subdirectories would quietly pick up whatever else was under there.
    """
    where = Path(root)

    if not where.is_dir():
        raise ScenarioError(f"{where} is not a directory of scenarios")

    entries: dict[str, Entry] = {}
    problems: list[str] = []

    for path in sorted(where.glob(f"*{SCENARIO_SUFFIX}")):
        try:
            scenario = load(path)
        except ScenarioError as error:
            problems.append(str(error))

            continue

        entry = Entry(scenario=scenario, path=path)

        if entry.id in entries:
            problems.append(
                f"{path}: two scenarios are called '{entry.id}' — this one and "
                f"{entries[entry.id].path}"
            )

            continue

        entries[entry.id] = entry

    if problems:
        raise ScenarioError("\n".join(problems))

    return Library(entries=entries, root=where)
