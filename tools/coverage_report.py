#!/usr/bin/env python3
"""
Write OFFICIAL_CARD_COVERAGE.md from the content itself.

The document answers two questions that are easy to confuse: whether a card is
in the repository, and whether the engine knows what it does. Generating it
from the content means the answer cannot drift from the truth — a card gains a
tick when it gains behaviour, and not before.

Usage::

    python tools/coverage_report.py --content content --output docs/OFFICIAL_CARD_COVERAGE.md
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

from fsme.cards import CardDefinition, CardType
from fsme.content import ContentLoader
from fsme.runtime.vocabulary import engine_vocabulary

IMPLEMENTED = "🟩"
NOT_YET = "⬜"

TYPE_SECTIONS = (
    (CardType.CHARACTER, "Characters"),
    (CardType.STARTING_ITEM, "Starting Items"),
    (CardType.TREASURE, "Treasure"),
    (CardType.LOOT, "Loot"),
    (CardType.MONSTER, "Monsters"),
    (CardType.EVENT, "Events"),
    (CardType.CURSE, "Curses"),
    (CardType.ROOM, "Rooms"),
    (CardType.BONUS_SOUL, "Bonus Souls"),
)


def is_implemented(card: CardDefinition) -> bool:
    """
    A card is implemented when the engine knows what it does.
    """
    return bool(card.abilities or card.statics)


def summary_table(sets: dict[str, list[CardDefinition]]) -> list[str]:
    lines = [
        "| Набор | Карт | Реализовано | Осталось |",
        "|---|---:|---:|---:|",
    ]

    for name in sorted(sets, key=lambda key: -len(sets[key])):
        cards = sets[name]
        done = sum(1 for card in cards if is_implemented(card))

        lines.append(f"| `{name}` | {len(cards)} | {done} | {len(cards) - done} |")

    total = sum(len(cards) for cards in sets.values())
    done = sum(
        1 for cards in sets.values() for card in cards if is_implemented(card)
    )

    lines.append(f"| **всего** | **{total}** | **{done}** | **{total - done}** |")

    return lines


def type_table(cards: list[CardDefinition]) -> list[str]:
    counts: Counter[str] = Counter()
    done: Counter[str] = Counter()

    for card in cards:
        counts[str(card.type)] += 1

        if is_implemented(card):
            done[str(card.type)] += 1

    lines = ["| Тип | Карт | Реализовано |", "|---|---:|---:|"]

    for card_type, total in counts.most_common():
        lines.append(f"| {card_type} | {total} | {done[card_type]} |")

    return lines


def card_rows(cards: list[CardDefinition]) -> list[str]:
    lines = ["| Card | Status | Notes |", "|------|--------|-------|"]

    for card in sorted(cards, key=lambda card: card.name.casefold()):
        status = IMPLEMENTED if is_implemented(card) else NOT_YET
        note = ""

        if card.metadata.get("copies", 1) > 1:
            note = f"×{card.metadata['copies']}"

        lines.append(f"| {card.name} | {status} | {note} |")

    return lines


def build(content: Path, focus: str) -> str:
    library = ContentLoader(engine_vocabulary()).load_root(content)

    sets = {
        expansion.id: list(expansion.definitions)
        for expansion in library
        if expansion.manifest.official
    }

    focused = sets.get(focus, [])
    by_type: dict[CardType, list[CardDefinition]] = defaultdict(list)

    for card in focused:
        by_type[card.type].append(card)

    total = sum(len(cards) for cards in sets.values())
    done = sum(
        1 for cards in sets.values() for card in cards if is_implemented(card)
    )

    lines = [
        "# Official Card Coverage",
        "",
        "Этот документ генерируется из содержимого `content/`.",
        "Не редактируйте его руками: `python tools/coverage_report.py`.",
        "",
        "Он отвечает на два разных вопроса, и их важно не путать:",
        "",
        "1. **Лежит ли карта в репозитории.**",
        "2. **Знает ли движок, что она делает.**",
        "",
        "Карта получает 🟩 только тогда, когда у неё есть поведение — способности",
        "или статики. Напечатанные числа, текст и количество копий импортированы у",
        "всех карт, но сами по себе они ничего не делают.",
        "",
        "---",
        "",
        "# Итог",
        "",
        f"Импортировано официальных карт: **{total}**. "
        f"Реализовано: **{done}**. Осталось: **{total - done}**.",
        "",
        *summary_table(sets),
        "",
        "---",
        "",
        f"# {focus}",
        "",
        *type_table(focused),
        "",
    ]

    for card_type, title in TYPE_SECTIONS:
        cards = by_type.get(card_type)

        if not cards:
            continue

        lines.extend(["", f"## {title}", "", *card_rows(cards)])

    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", default=Path("content"), type=Path)
    parser.add_argument(
        "--output", default=Path("docs/OFFICIAL_CARD_COVERAGE.md"), type=Path
    )
    parser.add_argument("--focus", default="base_game")

    args = parser.parse_args()

    args.output.write_text(build(args.content, args.focus), encoding="utf-8")

    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
