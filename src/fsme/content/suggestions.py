# src/fsme/content/suggestions.py

"""
The words an author has already used, gathered so a form can offer them back.

Three of the things a card writes have no closed set and never will: what a
counter is called, which families a card belongs to, and what cards are called.
The engine refuses none of them — a counter is a key in a bare dictionary, and
the next set invents the next word — so there is nothing for ``values`` or
``domain_from`` to say, and saying it anyway would turn every new word into a
validation error.

What there *is*, is a corpus. Every counter anybody has used is written down in
the content that is loaded, and an author typing into an empty box is being made
to remember a spelling this already knows. So the words are gathered here and
offered as suggestions, which is a different thing from a domain in the one way
that matters: nothing is refused, and a word that appears in no pool is as good
a card as one that appears in all of them.

Which keys feed which pool is not written down here. It is read off the shapes,
where each parameter says which pool its word belongs to, so a parameter the
engine gains is gathered the moment it exists and this module never grows a list.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

from .vocabulary import POOLS, Vocabulary


def pools_by_key(vocabulary: Vocabulary) -> Mapping[str, str]:
    """
    Which written key feeds which pool, read off every shape there is.

    A key rather than a key-and-owner because a pool is one namespace: the
    ``counter`` ``add_counter`` writes is the ``counter`` ``card_counters``
    asks about, and gathering them apart would offer an author half the words
    they have used. Two parameters spelt the same and drawing from different
    pools would break that, so it is refused rather than resolved — there is no
    right answer to which pool a word went into, and guessing one would put
    event keys in with counter names.
    """
    found: dict[str, str] = {}

    for shape in _every_shape(vocabulary):
        for key, parameter in shape.params.items():
            pool = parameter.suggest_from

            if not pool:
                continue

            if found.setdefault(key, pool) != pool:
                raise ValueError(
                    f"'{key}' draws from two pools: "
                    f"'{found[key]}' and '{pool}'"
                )

    return found


def gathered(
    cards: Iterable[Any],
    keys: Mapping[str, str],
) -> dict[str, list[str]]:
    """
    Every word these cards have written, sorted, one list per pool.

    The cards are raw content — what was written, not what was loaded from it —
    because a pool is about spellings and loading throws spellings away: a card
    with a counter nothing reads still names that counter, and an author who
    used it once should be offered it twice.

    Every pool comes back, empty ones included. A page that has to tell "no
    words yet" from "no such pool" is a page that will get it wrong once.
    """
    found: dict[str, set[str]] = {pool: set() for pool in POOLS}

    for card in cards:
        _harvest(card, keys, found)

    return {pool: sorted(words) for pool, words in found.items()}


def from_roots(
    roots: Iterable[Path | str],
    keys: Mapping[str, str],
) -> dict[str, list[str]]:
    """
    The pools held by every content root a game would be dealt from.

    Both ends of the same question. The cards we ship are where nearly every
    word an author wants already is, and the cards they wrote are where the
    word they invented last week is — and the game loads both, so a form that
    offered one of them would be offering half an answer.
    """
    # Imported here rather than at the top: the loader reads this module's
    # neighbours and one of them reads it back, and a pool of words is not
    # worth a cycle in the content package.
    from .loader import ContentLoader

    loader = ContentLoader()

    return gathered(
        (
            card
            for root in roots
            if Path(root).is_dir()
            for card in loader.raw_cards(Path(root))
        ),
        keys,
    )


def _every_shape(vocabulary: Vocabulary) -> Iterator[Any]:
    """
    Every shape the language has, whatever kind of thing it describes.
    """
    for table in (
        vocabulary.shapes,
        vocabulary.condition_shapes,
        vocabulary.target_shapes,
        vocabulary.node_shapes,
    ):
        yield from table.values()


def _harvest(
    node: Any,
    keys: Mapping[str, str],
    found: dict[str, set[str]],
) -> None:
    """
    Walk one card, keeping every word written under a key that names a pool.

    By key and not by shape, which is what makes this work on a card nothing has
    validated. Resolving shapes would mean resolving heads, and a card being
    edited has half of one — while the word an author typed into it is exactly
    the word worth offering back.
    """
    if isinstance(node, list):
        for item in node:
            _harvest(item, keys, found)

        return

    if not isinstance(node, Mapping):
        return

    for key, value in node.items():
        pool = keys.get(str(key), "")

        if pool:
            _keep(value, found[pool])

        _harvest(value, keys, found)


def _keep(value: Any, words: set[str]) -> None:
    """
    One written answer, which is a word or a list of them.

    A card's ``tags`` holds several and its ``name`` holds one; both feed a
    pool, and neither is asked to say which it is.
    """
    if isinstance(value, str):
        if value:
            words.add(value)

        return

    if isinstance(value, list):
        for one in value:
            if isinstance(one, str) and one:
                words.add(one)


__all__ = ["from_roots", "gathered", "pools_by_key"]
