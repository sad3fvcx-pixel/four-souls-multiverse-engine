# src/fsme/narration.py

"""
What happened, in words a person reads.

The engine emits events, and an event is a fact about the machine:
``after_attack_roll`` with ``value 5``, ``required 4``, ``hit true``. Anybody
who built the engine can read that. Nobody else can, and until now the only
thing FSME offered a watcher was the raw list — which is why somebody opening
the game could see it working and not see what was *happening*.

This turns an event into a sentence. "Ann attacks Polycephalus." "Rolls a 5 —
a hit, 4 was needed." "Polycephalus is defeated." "Ann gains a soul."

Three rules hold it honest, and they are the reason this is one module rather
than a few lines of JavaScript in each page.

**Nothing here decides anything.** Every sentence is built from what the event
already carries. Where the engine did not say something, the sentence does not
say it either — no sentence infers a cause, a total or an intention.

**Silence is a valid reading.** Most events are bookkeeping: a push onto the
stack, a phase changing, a static recalculating. They are true and they are not
news, so they get no sentence and the reader is not made to skim past them. The
technical log still has every one of them.

**One vocabulary.** A live game and a saved journal are the same events, so
they get the same words. Two narrators would drift, and the first time they
disagreed about a game nobody could say which was right.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

CENT = "¢"


def told(
    event: Any,
    *,
    names: Mapping[int, str] | None = None,
) -> str:
    """
    One event as a sentence, or "" when it is not worth a line.

    ``event`` is anything with ``type``, ``source``, ``targets``, ``payload``
    and ``controller`` — the live view's dictionaries and a journal's
    ``Happening`` both qualify, which is the point.
    """
    kind = str(_get(event, "type", ""))

    if kind not in SAID:
        return ""

    return str(SAID[kind](_Event(event, names or {})))


class _Event:
    """
    One event, read the same way whatever shape it arrived in.
    """

    def __init__(self, event: Any, names: Mapping[int, str]) -> None:
        self._event = event
        self._names = names

    @property
    def source(self) -> str:
        return str(_get(self._event, "source", "") or "")

    @property
    def targets(self) -> list[str]:
        return [str(target) for target in _get(self._event, "targets", []) or []]

    @property
    def who(self) -> str:
        """
        The player the event was about, by name where a name is known.
        """
        seat = _get(self._event, "controller", None)

        if seat is None:
            return self.targets[0] if self.targets else "somebody"

        return self._names.get(int(seat), f"seat {seat}")

    def payload(self, key: str, fallback: Any = None) -> Any:
        carried = _get(self._event, "payload", {}) or {}

        return carried.get(key, fallback)

    def amount(self, key: str = "amount") -> int:
        try:
            return int(self.payload(key) or 0)
        except (TypeError, ValueError):
            return 0


def _get(event: Any, name: str, fallback: Any = None) -> Any:
    if isinstance(event, Mapping):
        return event.get(name, fallback)

    return getattr(event, name, fallback)


def _plural(count: int, one: str, many: str = "") -> str:
    return one if abs(count) == 1 else (many or f"{one}s")


# ----------------------------------------------------------------------
# The vocabulary
# ----------------------------------------------------------------------


def _turn(event: _Event) -> str:
    return f"{event.who}'s turn begins."


def _attack(event: _Event) -> str:
    monster = event.source or "a monster"

    return f"{event.who} attacks {monster}."


def _attack_roll(event: _Event) -> str:
    value = event.amount("value")
    needed = event.payload("required")
    hit = bool(event.payload("hit"))

    landed = "a hit" if hit else "a miss"

    if needed is None:
        return f"{event.who} rolls a {value} — {landed}."

    return f"{event.who} rolls a {value} — {landed}, {needed} was needed."


def _roll(event: _Event) -> str:
    return f"{event.who} rolls a {event.amount('value')}."


def _damage(event: _Event) -> str:
    amount = event.amount()

    if not amount:
        return ""

    hurt = event.targets[0] if event.targets else event.who
    left = event.payload("remaining_hp")

    hit = f"{hurt} takes {amount} {_plural(amount, 'damage', 'damage')}"

    if event.payload("lethal"):
        return f"{hit} — enough to finish it."

    return f"{hit}." if left is None else f"{hit}, {left} left."


def _healed(event: _Event) -> str:
    amount = event.amount()

    return f"{event.who} heals {amount}." if amount else ""


def _killed(event: _Event) -> str:
    monster = event.source or "the monster"
    souls = event.amount("souls")

    if souls:
        return f"{monster} is defeated — worth {souls} {_plural(souls, 'soul')}."

    return f"{monster} is defeated."


def _died(event: _Event) -> str:
    return f"{event.who} dies."


def _soul(event: _Event) -> str:
    from_where = event.source

    if from_where:
        return f"{event.who} gains a soul from {from_where}."

    return f"{event.who} gains a soul."


def _soul_lost(event: _Event) -> str:
    return f"{event.who} loses a soul."


def _coins(event: _Event) -> str:
    amount = event.amount()

    return f"{event.who} gains {amount}{CENT}." if amount else ""


def _coins_lost(event: _Event) -> str:
    amount = event.amount()

    return f"{event.who} loses {amount}{CENT}." if amount else ""


def _played(event: _Event) -> str:
    return f"{event.who} plays {event.source}." if event.source else ""


def _activated(event: _Event) -> str:
    return f"{event.who} uses {event.source}." if event.source else ""


def _bought(event: _Event) -> str:
    card = event.source or (event.targets[0] if event.targets else "an item")

    return f"{event.who} buys {card}."


def _drew(event: _Event) -> str:
    count = event.amount("count") or 1

    return f"{event.who} draws {count} loot {_plural(count, 'card')}."


def _won(event: _Event) -> str:
    return f"{event.who} wins the game."


SAID: dict[str, Any] = {
    "turn_start": _turn,
    "attack_start": _attack,
    "after_attack_roll": _attack_roll,
    "after_roll": _roll,
    "damage_dealt": _damage,
    "healed": _healed,
    "monster_killed": _killed,
    "player_died": _died,
    "soul_gained": _soul,
    "soul_lost": _soul_lost,
    "coins_gained": _coins,
    "coins_lost": _coins_lost,
    "on_play": _played,
    "on_activate": _activated,
    "treasure_bought": _bought,
    "loot_drawn": _drew,
    "winner_declared": _won,
}
"""
Every event that gets a sentence.

Deliberately short. The engine emits well over a hundred kinds of event and
most of them are true without being news — a push onto the stack, a phase
changing, a static recalculating. Narrating those would bury the four lines
that say what the turn was about, which is the problem this module exists to
solve rather than one to reproduce in nicer words.

Adding a kind here is a decision that it is *news*. The technical log already
has all of them.
"""
