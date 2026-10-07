"""
Deterministic random number generator used by the engine.

There are two models, and a game is played on one of them from the deal to the
end.

Model 1 is the generator the engine had first: one ``random.Random`` per seed,
consumed in a fixed order. Every recording, journal and save made before model 2
was made on it, and it still plays them back byte for byte.

Model 2 gives each kind of randomness a stream of its own, so that one part of
a game cannot move another. A deck is shuffled by a key per card rather than
by a stream: taking a card out of the game leaves every other card where it
was. That is what lets two games that differ by one card stay the same game
until that card does something. A new game is dealt on model 2 unless it asks
for model 1; a record of a game always says, or is from before there was a
choice, and then it is model 1.

Every call names its domain, on either model. Model 1 checks the name and then
does exactly what it did before; model 2 needs it to know which stream or key
to use.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Mapping, MutableSequence, Sequence
from typing import Any

from fsme.util.errors import EngineError

LEGACY_MODEL = "1"
KEYED_MODEL = "2"

RNG_MODELS = (LEGACY_MODEL, KEYED_MODEL)
"""Every model a game can be played on."""

DEFAULT_RNG_MODEL = KEYED_MODEL
"""
The model a new game is dealt on when nobody asks for another.

Only a new game: a journal, recording or save that names no model is from
before there was a choice, and is model 1 whatever this says; and a GameState
built by hand is model 1 until it is told otherwise.
"""

DEAL_DOMAINS = frozenset(
    {"deal:loot", "deal:treasure", "deal:monster", "deal:room", "deal:characters"}
)
"""What the deal shuffles. Never the same domain as a shuffle during the game."""

DECK_DOMAINS = frozenset({"deck:loot", "deck:treasure", "deck:monster", "deck:room"})
"""What the game shuffles once it is under way."""

SHUFFLE_DOMAINS = DEAL_DOMAINS | DECK_DOMAINS

STREAM_DOMAINS = frozenset({"dice", "target"})
"""What draws numbers rather than shuffling."""

DOMAINS = SHUFFLE_DOMAINS | STREAM_DOMAINS
"""Every domain there is. Anything else is a mistake, on either model."""

_TAG = b"fsme-rng/2\x00"


class RNGError(EngineError):
    """
    The generator was asked for something it does not do.
    """


class UnknownRNGDomain(RNGError):
    """
    A domain outside the closed list, or one used for the wrong kind of draw.
    """


def _shuffle_domain(domain: str) -> str:
    if domain not in SHUFFLE_DOMAINS:
        raise UnknownRNGDomain(f"{domain!r} is not a shuffle domain")

    return domain


def _stream_domain(domain: str) -> str:
    if domain not in STREAM_DOMAINS:
        raise UnknownRNGDomain(f"{domain!r} is not a stream domain")

    return domain


class RNG:
    """Deterministic random number generator: model 1."""

    model = LEGACY_MODEL

    def __init__(self, seed: int) -> None:
        self._seed = seed
        self._random = random.Random(seed)

    @property
    def seed(self) -> int:
        """Return the initial seed."""
        return self._seed

    def randint(self, a: int, b: int) -> int:
        """Return a random integer N such that a <= N <= b."""
        return self._random.randint(a, b)

    def random(self) -> float:
        """Return the next random float in the range [0.0, 1.0)."""
        return self._random.random()

    def choice[T](self, sequence: Sequence[T]) -> T:
        """Return a random element from a non-empty sequence."""
        return self._random.choice(sequence)

    def shuffle(self, sequence: MutableSequence[Any]) -> None:
        """Shuffle a mutable sequence in place."""
        self._random.shuffle(sequence)

    def randint_for(self, domain: str, a: int, b: int) -> int:
        """
        A random integer N with a <= N <= b, drawn for ``domain``.

        On model 1 the domain is checked and the draw is ``randint``, so a
        generator that scripts ``randint`` scripts this too.
        """
        _stream_domain(domain)

        return self.randint(a, b)

    def shuffle_for(self, domain: str, sequence: MutableSequence[Any]) -> None:
        """
        Shuffle ``sequence`` in place for ``domain``.

        On model 1 the domain is checked and the shuffle is ``shuffle``.
        """
        _shuffle_domain(domain)

        self.shuffle(sequence)

    def get_state(self) -> Any:
        """Return the internal RNG state."""
        return self._random.getstate()

    def set_state(self, state: Any) -> None:
        """Restore the internal RNG state."""
        self._random.setstate(state)


def _decimal(number: int) -> bytes:
    return str(number).encode("ascii")


def _whole_seed(seed: Any) -> int:
    # A bool is an int to Python and is refused here: True is not a seed
    # anybody meant, and taking it as 1 would make two games out of one.
    if type(seed) is not int:
        raise TypeError(f"a model 2 seed is a whole number, not {type(seed).__name__}")

    return seed


def stream_seed(seed: int, domain: str) -> int:
    """
    The seed of one stream: the first eight bytes of its SHA-256, big-endian.
    """
    digest = hashlib.sha256(
        _TAG
        + b"stream\x00"
        + _decimal(_whole_seed(seed))
        + b"\x00"
        + _stream_domain(domain).encode("ascii")
    ).digest()

    return int.from_bytes(digest[:8], "big")


def shuffle_key(seed: int, domain: str, number: int, definition_id: str, copy: int) -> bytes:
    """
    Where one card goes in one shuffle: a SHA-256, compared whole.

    The card is named by its definition and by which copy of it this is, and
    by nothing about where it sat before — so the cards around it do not move
    it, and it does not move them.
    """
    return hashlib.sha256(
        _shuffle_prefix(seed, domain, number) + _card_part(definition_id, copy)
    ).digest()


def _shuffle_prefix(seed: int, domain: str, number: int) -> bytes:
    """What every key of one shuffle begins with: the seed, the domain, the count."""
    return (
        _TAG
        + b"shuffle\x00"
        + _decimal(_whole_seed(seed))
        + b"\x00"
        + _shuffle_domain(domain).encode("ascii")
        + b"\x00"
        + _decimal(number)
        + b"\x00"
    )


def _card_part(definition_id: str, copy: int) -> bytes:
    """What one card adds to its shuffle's prefix: its definition, length first, and its copy."""
    if not isinstance(definition_id, str):
        raise TypeError(f"a card is keyed by its definition id, not {definition_id!r}")

    named = definition_id.encode("utf-8")

    return len(named).to_bytes(4, "big") + named + _decimal(copy)


def _definition_id(card: Any) -> str:
    # A card instance and a card definition both answer `id` with the
    # definition's identifier; a character is dealt as its definition.
    identifier = getattr(card, "id", None)

    if not isinstance(identifier, str):
        raise TypeError(f"{card!r} has no definition id to be shuffled by")

    return identifier


class KeyedRNG(RNG):
    """
    Model 2: a stream per domain that draws numbers, a key per card that
    shuffles.

    Nothing is drawn without a domain. The plain calls a model 1 generator
    answers are refused here rather than sent somewhere by default.
    """

    model = KEYED_MODEL

    def __init__(self, seed: int) -> None:
        self._seed = _whole_seed(seed)
        self._streams: dict[str, random.Random] = {}
        self._shuffles: dict[str, int] = {}
        # Each stream's state as last taken, until the stream draws again. A
        # state is a tuple of numbers and cannot be changed through the tuple,
        # so handing out the same one twice hands out the same value twice.
        self._held: dict[str, tuple[Any, ...]] = {}

    def _stream(self, domain: str) -> random.Random:
        stream = self._streams.get(domain)

        if stream is None:
            stream = self._streams[domain] = random.Random(stream_seed(self._seed, domain))

        return stream

    def randint(self, a: int, b: int) -> int:
        raise RNGError("a model 2 generator draws only for a named domain")

    def random(self) -> float:
        raise RNGError("a model 2 generator draws only for a named domain")

    def choice[T](self, sequence: Sequence[T]) -> T:
        raise RNGError("a model 2 generator draws only for a named domain")

    def shuffle(self, sequence: MutableSequence[Any]) -> None:
        raise RNGError("a model 2 generator shuffles only for a named domain")

    def randint_for(self, domain: str, a: int, b: int) -> int:
        stream = self._stream(_stream_domain(domain))
        self._held.pop(domain, None)

        return stream.randint(a, b)

    def shuffle_for(self, domain: str, sequence: MutableSequence[Any]) -> None:
        _shuffle_domain(domain)

        number = self._shuffles.get(domain, 0)
        copies: dict[str, int] = {}
        keyed: list[tuple[bytes, Any]] = []

        # Every key of this shuffle starts with the same bytes; they are hashed
        # once and each card's key carries on from there, which is the same
        # SHA-256 as ``shuffle_key`` of the whole.
        prefix = hashlib.sha256(_shuffle_prefix(self._seed, domain, number))

        for card in sequence:
            identifier = _definition_id(card)
            copy = copies.get(identifier, 0)
            copies[identifier] = copy + 1

            key = prefix.copy()
            key.update(_card_part(identifier, copy))
            keyed.append((key.digest(), card))

        keyed.sort(key=lambda pair: pair[0])

        sequence[:] = [card for _, card in keyed]

        self._shuffles[domain] = number + 1

    def get_state(self) -> dict[str, Any]:
        return {
            "model": KEYED_MODEL,
            "streams": {domain: self._stream_state(domain) for domain in sorted(self._streams)},
            "shuffles": {domain: self._shuffles[domain] for domain in sorted(self._shuffles)},
        }

    def _stream_state(self, domain: str) -> tuple[Any, ...]:
        held = self._held.get(domain)

        if held is None:
            held = self._held[domain] = self._streams[domain].getstate()

        return held

    def set_state(self, state: Any) -> None:
        written = keyed_state(state)
        self._held = {}

        streams: dict[str, random.Random] = {}

        for domain, held in written["streams"].items():
            stream = random.Random()
            stream.setstate(held)
            streams[domain] = stream

        self._streams = streams
        self._shuffles = dict(written["shuffles"])


def _tupled(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return tuple(_tupled(item) for item in value)

    return value


def keyed_state(value: Any) -> dict[str, Any]:
    """
    A model 2 state in its one canonical shape, or a refusal.

    A save holds the state as plain data — lists where the generator had
    tuples — and this turns it back, checking every part, so that a state read
    from a file and the state the game had are the same value.
    """
    if not isinstance(value, Mapping):
        raise TypeError("a model 2 generator state is a mapping")

    if set(value) != {"model", "streams", "shuffles"}:
        raise ValueError("a model 2 generator state holds model, streams and shuffles")

    if value["model"] != KEYED_MODEL:
        raise ValueError(f"this generator state is model {value['model']!r}, not model 2")

    streams, shuffles = value["streams"], value["shuffles"]

    if not isinstance(streams, Mapping) or not isinstance(shuffles, Mapping):
        raise TypeError("a model 2 generator state holds its streams and shuffles as mappings")

    for domain in streams:
        _stream_domain(str(domain))

    for domain, count in shuffles.items():
        _shuffle_domain(str(domain))

        if type(count) is not int or count < 0:
            raise ValueError(f"the shuffle count of {domain!r} is not a whole number")

    return {
        "model": KEYED_MODEL,
        "streams": {str(domain): _tupled(streams[domain]) for domain in sorted(streams)},
        "shuffles": {str(domain): shuffles[domain] for domain in sorted(shuffles)},
    }


def rng_for(seed: int, model: str = DEFAULT_RNG_MODEL) -> RNG:
    """
    A fresh generator for a game played on ``model``.
    """
    if model == LEGACY_MODEL:
        return RNG(seed)

    if model == KEYED_MODEL:
        return KeyedRNG(seed)

    raise RNGError(f"there is no RNG model {model!r}; the models are {', '.join(RNG_MODELS)}")
