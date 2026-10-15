#!/usr/bin/env python3

"""
Write `docs/REFERENCE.md` out of the engine.

The four registry documents are written by hand and explain what each name is
for, which is worth having and cannot be generated. What drifted is the part
that was only ever a copy: **which names exist, and what each one takes.** An
audit found 40 of 70 effects, 18 of 46 targets, 16 of 44 conditions and 15 of
66 triggers missing from the documents meant to list them, and the drift was
one-way — nothing was described that the engine lacks. Nobody had written a
wrong description; they had written a list, and lists go stale.

So the list is read off the engine instead, and the prose stays where it is.
This file is wholly generated: nothing here should ever be edited by hand, and
a test fails when it is out of date.

Run it with `python tools/make_reference.py`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fsme.content.vocabulary import (  # noqa: E402
    BY_ENGINE,
    BY_PLAYER_OF,
    UNCHECKED,
)
from fsme.runtime.vocabulary import engine_vocabulary  # noqa: E402

OUTPUT = ROOT / "docs" / "REFERENCE.md"

REGISTRIES = {
    "effects": "EFFECT_REGISTRY.md",
    "conditions": "CONDITION_REGISTRY.md",
    "targets": "TARGET_REGISTRY.md",
    "triggers": "TRIGGER_REGISTRY.md",
}


def described_in(document: str) -> set[str]:
    """
    The names a registry document has a section for.

    A section heading, not a mention: a name that appears only inside somebody
    else's example is not documented.
    """
    text = (ROOT / "docs" / document).read_text("utf-8")

    return set(re.findall(r"^##\s+([a-z][a-z0-9_]*)\s*$", text, re.MULTILINE))


def wants(shape, name: str) -> str:
    """
    One line describing what a parameter takes.
    """
    parameter = shape.params[name]

    if parameter.kind == UNCHECKED:
        return "only a game can judge"

    if parameter.values:
        if len(parameter.values) > 8:
            # A domain of sixty-six names is not a table cell. The count says
            # there is a closed list and the registry says what is in it.
            return f"one of {len(parameter.values)} {name} names"

        return " or ".join(f"`{value}`" for value in parameter.values)

    if parameter.least is not None:
        return f"{parameter.kind} ≥ {parameter.least}"

    return str(parameter.kind)


def _refers(parameter) -> str:
    """
    How a parameter that names something else reads in a table.

    Two facts, not one: *what* is named, and *how a card writes it*. They come
    apart — an effect naming a player writes the one dynamic head that answers
    with a seat, and a target naming the same player writes a bare name — and a
    table that gave only the first would send somebody to write the wrong one.
    """
    kind = parameter.refers_to

    if parameter.written_as == BY_ENGINE:
        return "the engine supplies it"

    if parameter.written_as == BY_PLAYER_OF:
        return f"`{{\"{BY_PLAYER_OF}\": name}}`, a group of players the ability bound"

    if kind == "values":
        return "names something this ability stored"

    if kind == "any":
        return "names a group the ability bound"

    return f"names a group of {kind} the ability bound"


def table(shapes, names, *, kind: str) -> list[str]:
    """
    One row per name, with what it takes — and, for a target, what it hands
    back, since that is what decides where its name may be used again.
    """
    hands_back = kind == "targets"

    lines = (
        ["| name | hands back | takes |", "| --- | --- | --- |"]
        if hands_back
        else ["| name | takes |", "| --- | --- |"]
    )

    for name in sorted(names):
        shape = shapes.get(name)
        gives = f" {getattr(shape, 'yields', '') or '—'} |" if hands_back else ""

        if shape is None or not shape.params:
            lines.append(f"| `{name}` |{gives} — |")

            continue

        written = ", ".join(
            f"`{key}` "
            + (
                _refers(shape.params[key])
                if shape.params[key].refers_to
                else wants(shape, key)
            )
            + ("*" if shape.params[key].required else "")
            for key in sorted(shape.params)
        )

        lines.append(f"| `{name}` |{gives} {written} |")

    return lines


def coverage(live: set[str], document: str) -> str:
    """
    How much of one vocabulary the hand-written registry explains.
    """
    described = described_in(document) & live
    missing = len(live) - len(described)

    if not missing:
        return f"All {len(live)} have a section in `{document}`."

    return (
        f"{len(described)} of {len(live)} have a section in `{document}`; "
        f"**{missing} are listed here and nowhere else.**"
    )


def main() -> int:
    vocabulary = engine_vocabulary()

    parts: list[str] = [
        "# Reference",
        "",
        "**Generated by `tools/make_reference.py`. Do not edit.**",
        "",
        "Every name this engine answers to, and what each one takes. The four",
        "registry documents explain what the names are *for*; this one is the",
        "list, and it is read off the engine so that it cannot drift from it.",
        "",
        "A `*` marks a parameter that must be given. \"only a game can judge\"",
        "means the pipeline deliberately does not check that value — and not",
        "that anything is accepted: the guard inside the engine stays where it",
        "is. A parameter that *names* something says so instead, along with how",
        "a card writes the name, because the two are not the same sentence for",
        "an effect and for a target.",
        "",
    ]

    sections = (
        ("Effects", vocabulary.effects, vocabulary.shapes, "effects"),
        ("Conditions", vocabulary.conditions, vocabulary.condition_shapes, "conditions"),
        ("Targets", vocabulary.targets, vocabulary.target_shapes, "targets"),
        ("Triggers", vocabulary.triggers, {}, "triggers"),
    )

    for title, names, shapes, key in sections:
        parts += [
            f"## {title}",
            "",
            coverage(set(names), REGISTRIES[key]),
            "",
        ]
        parts += table(shapes, names, kind=key)
        parts += [""]

    OUTPUT.write_text("\n".join(parts) + "\n", encoding="utf-8")

    print(f"wrote {OUTPUT.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
