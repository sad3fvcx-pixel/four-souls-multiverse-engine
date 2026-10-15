#!/usr/bin/env python3
"""
Turn a Four Souls card database into FSME content.

What this tool does and does not do is worth being exact about.

It converts everything mechanical: names, types, printed statistics, rewards,
how many copies of a card the deck holds, which item a character starts with,
and the original card text kept as metadata. All of that is read off the
database and can be checked against it.

It does not write abilities. A card's rules text is English prose, and turning
prose into the Effect DSL is a judgement about what a card means — not a
transformation of what it says. Guessing would produce a set that looks
complete and plays wrong, so abilities come from ``_abilities.json`` beside the
generated cards, written by hand and merged in here. Re-running the import
never destroys them.

Usage::

    python tools/import_cards.py --database cards.json --content content
    python tools/import_cards.py --refresh --content content

The second form needs no database. It re-applies ``_abilities.json`` to the
content already in the tree, which is what you want after writing a card's
behaviour: the printed data is already there and does not change.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1"

BASE_GAME_SET = "Base Game"

DECK_TYPES = {
    "Characters": "character",
    "Starting Items": "starting_item",
    "Loot Deck": "loot",
    "Treasure Deck": "treasure",
    "Room Deck": "room",
    "Bonus Souls": "bonus_soul",
}

MONSTER_SUBCATEGORY_TYPES = {
    "Curses": "curse",
    "Good Events": "event",
    "Bad Events": "event",
}

SUBCATEGORY_TAGS = {
    "Bosses": ("boss",),
    "Epic Boss": ("boss", "epic"),
    "Basic Enemies": ("basic",),
    "Cursed Enemies": ("cursed",),
    "Holy / Charmed Enemies": ("holy",),
    "Active Items": ("active",),
    "Passive Items": ("passive",),
    "Paid Items": ("paid",),
    "One Use Items": ("one_use",),
    "Soul Item": ("soul_item",),
    "Trinkets": ("trinket",),
}

HP = re.compile(r"HP:\s*(\d+)")
ATTACK = re.compile(r"AT:\s*(\d+)")
ROLL = re.compile(r"DC:\s*(\d+)\+?")
SOULS = re.compile(r"\(\+?(\d+)\s*souls?\)", re.IGNORECASE)
REWARD_LINE = re.compile(r"Rewards?:(.*?)(?:\n\n|$)", re.DOTALL)
CENTS = re.compile(r"(\d+)¢")
LOOT = re.compile(r"Loot\s*(\d+)", re.IGNORECASE)
TREASURE = re.compile(r"\+(\d+)\s*treasure", re.IGNORECASE)
STARTING_ITEM = re.compile(r"Starting item:\s*\n?(.+?)(?:\n-|$)", re.IGNORECASE | re.DOTALL)

NAME_SEPARATOR = re.compile(r"\s*//\s*")
"""
Cards printed with two names, such as an item and the character it belongs to.
"""

NAME_CORRECTIONS = {
    "berzerk": "berserk",
}
"""
Spelling differences inside the source database.

One character card names its starting item "Berzerk" while the item itself is
printed "Berserk". Correcting it here, by name and visibly, is honest; matching
names approximately is not — an engine that guesses which card was meant will
eventually guess wrong and say nothing.
"""

ETERNAL_MARK = "-Eternal-"
TRINKET_MARK = "-Trinket-"
ACTIVATE_MARK = "↷"
PAID_MARK = "$"


def tidy_name(value: str) -> str:
    """
    Put a card's name on one line.
    """
    parts = [part.strip() for part in NAME_SEPARATOR.split(value.strip()) if part.strip()]

    return " // ".join(" ".join(part.split()) for part in parts)


def name_keys(value: str) -> list[str]:
    """
    Every name a card can be referred to by.
    """
    keys: list[str] = []

    for part in NAME_SEPARATOR.split(value.strip()):
        cleaned = " ".join(part.split()).strip(" !.").casefold()

        if cleaned:
            keys.append(NAME_CORRECTIONS.get(cleaned, cleaned))

    return keys


def slugify(value: str) -> str:
    """
    Turn a set name into a directory and identifier fragment.
    """
    normalised = unicodedata.normalize("NFKD", value)
    ascii_only = normalised.encode("ascii", "ignore").decode("ascii")

    return re.sub(r"[^a-z0-9]+", "_", ascii_only.lower()).strip("_")


@dataclass
class ImportReport:
    """
    What the conversion did, and what it could not read.
    """

    cards: int = 0
    copies: int = 0
    variants: int = 0
    implemented: int = 0

    by_type: Counter[str] = field(default_factory=Counter)
    by_set: Counter[str] = field(default_factory=Counter)

    unparsed: list[str] = field(default_factory=list)
    unresolved_items: list[str] = field(default_factory=list)

    def note(self, message: str) -> None:
        self.unparsed.append(message)


def card_type_of(row: dict[str, Any]) -> str:
    """
    Decide what kind of card a database row describes.

    The monster deck holds more than monsters: events and curses are shuffled
    into it, and they are not creatures with hit points.
    """
    deck = row["deck"]

    if deck in DECK_TYPES:
        return DECK_TYPES[deck]

    subcategory = row.get("subcategory") or ""

    return MONSTER_SUBCATEGORY_TYPES.get(subcategory, "monster")


def tags_of(row: dict[str, Any], text: str) -> list[str]:
    """
    Collect the tags a card's printing makes plain.
    """
    tags: set[str] = set(SUBCATEGORY_TAGS.get(row.get("subcategory") or "", ()))

    if ETERNAL_MARK in text:
        tags.add("eternal")

    if TRINKET_MARK in text:
        tags.add("trinket")

    if ACTIVATE_MARK in text:
        tags.add("activated")

    if re.search(r"(^|\n)\s*\$", text):
        tags.add("paid")

    return sorted(tags)


def statistics_of(
    row: dict[str, Any],
    card_type: str,
    text: str,
    report: ImportReport,
) -> dict[str, Any]:
    """
    Read the printed numbers off a card.

    Only unambiguous values are taken. A monster whose reward is "Roll- Gain
    x¢" has a reward the engine cannot express as a number, and inventing one
    would be worse than leaving it out, so it is recorded as unparsed instead.
    """
    stats: dict[str, Any] = {}

    if card_type in ("monster", "character"):
        health = HP.search(text)
        attack = ATTACK.search(text)

        if health:
            stats["health"] = int(health.group(1))

        if attack:
            stats["attack"] = int(attack.group(1))

    if card_type == "monster":
        roll = ROLL.search(text)

        if roll:
            stats["roll"] = int(roll.group(1))
        elif "DC:" in text:
            report.note(f"{row['id']}: unreadable difficulty in {text.splitlines()[0]!r}")

        souls = SOULS.search(text)

        if souls:
            stats["souls"] = int(souls.group(1))

        rewards = _rewards_of(row, text, report)

        if rewards:
            stats["rewards"] = rewards

    return stats


def _rewards_of(
    row: dict[str, Any],
    text: str,
    report: ImportReport,
) -> dict[str, int]:
    line = REWARD_LINE.search(text)

    if line is None:
        return {}

    body = line.group(1)
    rewards: dict[str, int] = {}

    cents = CENTS.search(body)
    loot = LOOT.search(body)
    treasure = TREASURE.search(body)

    if cents:
        rewards["cents"] = int(cents.group(1))

    if loot:
        rewards["loot"] = int(loot.group(1))

    if treasure:
        rewards["treasure"] = int(treasure.group(1))

    if not rewards and body.strip() and not SOULS.fullmatch(body.strip()):
        stripped = SOULS.sub("", body).strip()

        if stripped:
            report.note(f"{row['id']}: reward not a number: {stripped[:40]!r}")

    return rewards


def build_card(
    row: dict[str, Any],
    *,
    expansion: str,
    card_id: str,
    copies: int,
    report: ImportReport,
) -> dict[str, Any]:
    """
    Build one card definition from one database row.
    """
    text = row["body_text_en"]
    card_type = card_type_of(row)

    card: dict[str, Any] = {
        "id": card_id,
        "name": tidy_name(row["name_en"]),
        "type": card_type,
        "expansion": expansion,
        "schema_version": SCHEMA_VERSION,
        "abilities": [],
    }

    card.update(statistics_of(row, card_type, text, report))

    tags = tags_of(row, text)

    if tags:
        card["tags"] = tags

    metadata: dict[str, Any] = {
        "text": text,
        "set": row["set"],
        "deck": row["deck"],
        "copies": copies,
        "source_id": row["id"],
    }

    for key, target in (
        ("subcategory", "subcategory"),
        ("version", "version"),
        ("artist", "artist"),
        ("notes", "notes"),
        ("name_ru", "name_ru"),
        ("body_text_ru", "text_ru"),
    ):
        value = row.get(key)

        if value:
            metadata[target] = value

    if row.get("effect_3p_plus"):
        metadata["effect_3p_plus"] = True

    card["metadata"] = metadata

    return card


def resolve_starting_items(
    cards: list[dict[str, Any]],
    rows: dict[str, dict[str, Any]],
    report: ImportReport,
) -> None:
    """
    Point each character at the card it starts with.

    The database names the starting item in prose. Matching it to a card is a
    lookup, not a guess: a name that matches nothing is reported rather than
    quietly dropped.

    The lookup spans every set. A character printed in one set routinely starts
    with an item printed in another, and an alternate-art character starts with
    the same item the original does.
    """
    items: dict[str, str] = {}

    for card in cards:
        if card["type"] == "starting_item":
            for key in name_keys(card["name"]):
                items.setdefault(key, card["id"])

    for card in cards:
        if card["type"] != "character":
            continue

        text = rows[card["id"]]["body_text_en"]
        match = STARTING_ITEM.search(text)

        if match is None:
            continue

        name = match.group(1).strip().splitlines()[0].strip()
        target = next(
            (items[key] for key in name_keys(name) if key in items), None
        )

        if target is None:
            report.unresolved_items.append(f"{card['id']}: no card named {name!r}")
            card["metadata"]["starting_item_name"] = name
            continue

        card["metadata"]["starting_item"] = target


def group_rows(rows: list[dict[str, Any]], report: ImportReport) -> list[tuple[str, dict, int]]:
    """
    Collapse the database into one entry per distinct card.

    A database identifier is reused two different ways. Fifteen rows of "A
    Penny!" are fifteen physical copies of one card, and become one definition
    with a count. Three rows of "Pills!" under one identifier are three
    different cards that happen to share a name, and become three definitions
    with distinct identifiers — otherwise two of them would be lost.
    """
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        by_id[row["id"]].append(row)

    entries: list[tuple[str, dict, int]] = []

    for identifier in sorted(by_id):
        variants: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for row in by_id[identifier]:
            variants[row["body_text_en"]].append(row)

        for index, text in enumerate(sorted(variants)):
            rows_of_variant = variants[text]
            card_id = identifier if index == 0 else f"{identifier}-v{index + 1}"

            if index:
                report.variants += 1

            entries.append((card_id, rows_of_variant[0], len(rows_of_variant)))
            report.copies += len(rows_of_variant) - 1

    return entries


def load_abilities(directory: Path) -> dict[str, dict[str, Any]]:
    """
    Read the hand-written behaviour that belongs to a set.
    """
    path = directory / "_abilities.json"

    if not path.is_file():
        return {}

    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise SystemExit(f"{path}: expected an object mapping card id to abilities")

    return data


def apply_abilities(
    card: dict[str, Any],
    abilities: dict[str, dict[str, Any]],
    report: ImportReport,
) -> None:
    """
    Merge hand-written behaviour into a generated card.
    """
    written = abilities.get(card["id"])

    if not written:
        return

    for key in ("abilities", "statics", "cost"):
        if key in written:
            card[key] = written[key]

    if "tags" in written:
        # A family a card belongs to — Guppy items, for one — that the database
        # does not record but other cards ask about by name.
        card["tags"] = sorted(set(card.get("tags", [])) | set(written["tags"]))

    if written.get("vanilla"):
        # Somebody read the card and found no rules on it: a monster with hit
        # points and a Bible quote has already been fully imported. Saying so
        # is a claim a person makes, not something the importer may guess, so
        # it is written down beside the abilities.
        card.setdefault("metadata", {})["vanilla"] = True

    if card.get("abilities") or card.get("statics"):
        report.implemented += 1


def write_set(
    directory: Path,
    *,
    expansion: str,
    name: str,
    cards: list[dict[str, Any]],
) -> None:
    """
    Write one set's manifest and cards.
    """
    directory.mkdir(parents=True, exist_ok=True)

    manifest = {
        "id": expansion,
        "name": name,
        "version": "1.0.0",
        "schema_version": SCHEMA_VERSION,
        "official": True,
        "description": f"{name}: {len(cards)} cards imported from the card database.",
    }

    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for card in cards:
        by_type[card["type"]].append(card)

    cards_directory = directory / "cards"
    cards_directory.mkdir(exist_ok=True)

    for existing in cards_directory.glob("*.json"):
        existing.unlink()

    for card_type in sorted(by_type):
        payload = {"cards": sorted(by_type[card_type], key=lambda card: card["id"])}

        (cards_directory / f"{card_type}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )


def set_directories(content: Path) -> list[Path]:
    """
    Every set already written into the content tree.
    """
    directories = [content / "base_game"]
    directories.extend(sorted((content / "expansions").glob("*")))

    return [directory for directory in directories if (directory / "cards").is_dir()]


def refresh(content: Path, report: ImportReport) -> None:
    """
    Re-apply hand-written behaviour to content that is already imported.

    The database is not needed for this and is not consulted: printed numbers,
    text and copies were settled when the card was imported and do not change
    because somebody wrote an ability. What does change is the overlay, and a
    card whose entry has been withdrawn from it goes back to having no
    behaviour — which is why abilities are cleared before they are merged.

    One thing refresh cannot undo is a tag: overlay tags are added to the ones
    the database gave a card, and nothing here knows which is which. Removing a
    tag means re-importing from the database.
    """
    for directory in set_directories(content):
        written = load_abilities(directory)

        for path in sorted((directory / "cards").glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            cards = payload.get("cards", [])

            for card in cards:
                card["abilities"] = []
                card.pop("statics", None)
                card.pop("cost", None)
                card.get("metadata", {}).pop("vanilla", None)

                apply_abilities(card, written, report)

                report.cards += 1
                report.by_type[card["type"]] += 1

            path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=None)
    parser.add_argument("--content", default=Path("content"), type=Path)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="re-apply _abilities.json to content already imported",
    )

    args = parser.parse_args()

    if args.refresh or args.database is None:
        report = ImportReport()

        refresh(args.content, report)

        print(
            json.dumps(
                {"cards": report.cards, "implemented": report.implemented},
                indent=2,
                ensure_ascii=False,
            )
        )

        return

    rows = json.loads(args.database.read_text(encoding="utf-8"))

    if not isinstance(rows, list):
        raise SystemExit("expected the flat database: a list of card rows")

    report = ImportReport()
    entries = group_rows(rows, report)

    by_set: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_rows: dict[str, dict[str, Any]] = {}

    for card_id, row, copies in entries:
        expansion = slugify(row["set"])
        card = build_card(
            row,
            expansion=expansion,
            card_id=card_id,
            copies=copies,
            report=report,
        )

        by_set[row["set"]].append(card)
        source_rows[card_id] = row

        report.cards += 1
        report.by_type[card["type"]] += 1
        report.by_set[row["set"]] += 1

    every_card = [card for cards in by_set.values() for card in cards]

    resolve_starting_items(every_card, source_rows, report)

    for set_name, cards in by_set.items():
        expansion = slugify(set_name)
        directory = (
            args.content / "base_game"
            if set_name == BASE_GAME_SET
            else args.content / "expansions" / expansion
        )

        written = load_abilities(directory)

        for card in cards:
            apply_abilities(card, written, report)

        write_set(directory, expansion=expansion, name=set_name, cards=cards)

    summary = {
        "cards": report.cards,
        "extra_copies": report.copies,
        "variants_split": report.variants,
        "implemented": report.implemented,
        "by_type": dict(report.by_type.most_common()),
        "by_set": dict(report.by_set.most_common()),
        "unparsed": report.unparsed,
        "unresolved_starting_items": report.unresolved_items,
    }

    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if args.report:
        args.report.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
