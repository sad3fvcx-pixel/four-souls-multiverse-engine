# src/fsme/analysis/moments.py

"""
The moments a game turned on.

An account of a game says what happened. This says *where it was decided* —
which handful of moves, out of the several hundred a game takes, moved the
scoreboard furthest towards the ending it actually got.

The measurement is a ledger, not a model. Every entry in a journal carries the
events it caused, and those events say in so many words how many souls were
gained, how many cents changed hands, how much damage landed and who died. A
move's weight is what its own events did to the eventual winner's lead over
the rest of the table. Nothing is simulated, nothing is estimated, and no
counterfactual is claimed: this does not say the game would have gone
differently, only that this is where it went.

Two cautions live in the code rather than in the reader's head.

The scoreboard is arithmetic on named preferences, and the preferences are
arguable. A soul is one unit because four of them win; a cent is a hundredth
because ten of them buy an item and an item is not a quarter of a game. A
reader who disagrees can ignore the totals entirely, because every moment is
printed with the souls, cents and hit points it moved, and those are counts.

And a moment can be large without anybody having decided anything. A die
settles most of the big swings in this game, so a moment whose events came
after a roll is marked as one the dice decided. Reading those as good play is
the mistake this whole module exists to make harder.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from fsme.journal import Entry, Journal

A_SOUL = 1.0
"""
What a soul is worth on the scoreboard: the game is four of them.
"""

A_CENT = 0.01
"""
What a cent is worth: ten buy an item, and an item is not a quarter of a game.
"""

A_HIT_POINT = 0.02
"""
What a hit point is worth: being alive to take the next turn, and no more.
"""

A_DEATH = 0.15
"""
What dying costs beyond the hit points: a card, a cent, an item, the turn.

The largest of the guesses here, and the one to argue with first.
"""

SOUL_GAINED = "soul_gained"
SOUL_LOST = "soul_lost"
COINS_GAINED = "coins_gained"
COINS_LOST = "coins_lost"
DAMAGE_DEALT = "damage_dealt"
HEALED = "healed"
PLAYER_DIED = "player_died"
MONSTER_KILLED = "monster_killed"
AFTER_ROLL = "after_roll"
AFTER_ATTACK_ROLL = "after_attack_roll"

A_PLAYER = "player"


@dataclass(slots=True)
class Ledger:
    """
    What one move did to one seat, in counts.
    """

    souls: int = 0
    coins: int = 0
    hp: int = 0
    deaths: int = 0

    @property
    def standing(self) -> float:
        """
        The counts added up in the scoreboard's currency.
        """
        return (
            self.souls * A_SOUL
            + self.coins * A_CENT
            + self.hp * A_HIT_POINT
            - self.deaths * A_DEATH
        )

    @property
    def empty(self) -> bool:
        return not (self.souls or self.coins or self.hp or self.deaths)

    def to_dict(self) -> dict[str, Any]:
        return {
            "souls": self.souls,
            "coins": self.coins,
            "hp": self.hp,
            "deaths": self.deaths,
            "standing": self.standing,
        }


@dataclass(slots=True)
class Moment:
    """
    One move, and what it did to the game's direction.
    """

    index: int
    turn: int
    phase: str

    player: int
    who: str

    command: str
    label: str

    swing: float = 0.0
    """
    How far this moved the eventual winner's lead over the rest of the table.

    Positive towards the winner. Negative moments are the setbacks they had to
    come back from, and are as much a part of where a game turned as the gains.
    """

    ledgers: dict[int, Ledger] = field(default_factory=dict)

    dice: tuple[int, ...] = ()
    """
    The faces rolled while this move resolved, when any were.
    """

    chance: float | None = None
    """
    The chance the attack roll in this move would land, when it was an attack.

    Exact, from the printed difficulty the engine used and the sides of the
    die. Present so that a large swing can be read as the gamble it was.
    """

    said: tuple[str, ...] = ()
    """What the events said, in words, for the reader who ignores the totals."""

    @property
    def decided_by_dice(self) -> bool:
        return bool(self.dice)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "turn": self.turn,
            "phase": self.phase,
            "player": self.player,
            "who": self.who,
            "command": self.command,
            "label": self.label,
            "swing": self.swing,
            "ledgers": {
                str(seat): ledger.to_dict() for seat, ledger in self.ledgers.items()
            },
            "dice": list(self.dice),
            "chance": self.chance,
            "decided_by_dice": self.decided_by_dice,
            "said": list(self.said),
        }


@dataclass(slots=True)
class Turning:
    """
    Where a game turned, and towards whom.
    """

    seed: int

    towards: int | None = None
    """
    The seat the swings are measured towards: the winner, when there was one.
    """

    towards_name: str = ""
    won: bool = False
    """
    Whether ``towards`` actually won, or is only whoever came closest.
    """

    moments: list[Moment] = field(default_factory=list)

    weighed: int = 0
    """How many moves moved anything at all, out of the whole game."""

    moves: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "towards": self.towards,
            "towards_name": self.towards_name,
            "won": self.won,
            "moves": self.moves,
            "weighed": self.weighed,
            "moments": [moment.to_dict() for moment in self.moments],
        }


def turning_points(journal: Journal, *, top: int = 3) -> Turning:
    """
    Find the moves that moved a game furthest towards its ending.

    Measured towards the winner. Without a winner there is no ending to have
    been moved towards, so the seat that got closest stands in for one and the
    report says that is what it is doing.
    """
    seats = len(journal.players)

    told = Turning(seed=journal.seed, moves=len(journal.entries))

    if seats < 2 or not journal.entries:
        return told

    winner = journal.outcome.get("winner")
    winner = None if winner is None else int(winner)

    told.won = winner is not None
    told.towards = winner if winner is not None else _who_got_closest(journal, seats)

    if told.towards is None:
        return told

    told.towards_name = journal.players[told.towards]

    weighed: list[Moment] = []

    for entry in journal.entries:
        moment = _weigh(journal, entry, told.towards, seats)

        if moment is not None:
            weighed.append(moment)

    told.weighed = len(weighed)
    told.moments = sorted(weighed, key=lambda moment: -abs(moment.swing))[:top]

    return told


def _who_got_closest(journal: Journal, seats: int) -> int | None:
    """
    In a game nobody won, whoever had the most souls at the end.
    """
    souls: Counter[int] = Counter()

    for entry in journal.entries:
        for event in entry.events:
            if event.controller is None or not 0 <= event.controller < seats:
                continue

            if event.type == SOUL_GAINED:
                souls[event.controller] += 1
            elif event.type == SOUL_LOST:
                souls[event.controller] -= 1

    if not souls:
        return None

    return max(souls, key=lambda seat: (souls[seat], -seat))


def _weigh(
    journal: Journal, entry: Entry, towards: int, seats: int
) -> Moment | None:
    """
    Read one entry's events into a ledger per seat, and take the difference.

    ``None`` when nothing countable happened, which is most moves: passing
    priority, ending a phase, drawing into a hand. A game of six hundred moves
    turns on the twenty or so that moved something.
    """
    ledgers: dict[int, Ledger] = {}
    said: list[str] = []
    dice: list[int] = []
    chance: float | None = None

    def ledger(seat: int) -> Ledger:
        return ledgers.setdefault(seat, Ledger())

    for event in entry.events:
        seat = event.controller
        ours = 0 <= seat < seats if seat is not None else False

        if event.type in (AFTER_ROLL, AFTER_ATTACK_ROLL):
            face = event.payload.get("value")

            if isinstance(face, int):
                dice.append(face)

        if event.type == AFTER_ATTACK_ROLL and chance is None:
            # The first roll, not the last: a reroll is a second decision, and
            # reporting its odds as the odds the attack was made under would
            # credit the attacker with knowing they would get one.
            chance = _chance_of(event.payload)

        if not ours or seat is None:
            continue

        if event.type == SOUL_GAINED:
            ledger(seat).souls += 1
            said.append(f"{journal.players[seat]} gained a soul")
        elif event.type == SOUL_LOST:
            ledger(seat).souls -= 1
            said.append(f"{journal.players[seat]} lost a soul")
        elif event.type == COINS_GAINED:
            amount = int(event.payload.get("amount") or 0)
            ledger(seat).coins += amount
        elif event.type == COINS_LOST:
            amount = int(event.payload.get("amount") or 0)
            ledger(seat).coins -= amount
        elif event.type == DAMAGE_DEALT:
            if str(event.payload.get("target_kind") or "") != A_PLAYER:
                continue

            ledger(seat).hp -= int(event.payload.get("amount") or 0)
        elif event.type == HEALED:
            ledger(seat).hp += int(event.payload.get("amount") or 0)
        elif event.type == PLAYER_DIED:
            ledger(seat).deaths += 1
            said.append(f"{journal.players[seat]} died")
        elif event.type == MONSTER_KILLED:
            said.append(f"{journal.players[seat]} killed {event.source or 'it'}")

    if all(kept.empty for kept in ledgers.values()):
        return None

    theirs = ledgers.get(towards, Ledger()).standing
    others = [
        ledgers.get(seat, Ledger()).standing
        for seat in range(seats)
        if seat != towards
    ]

    swing = theirs - (sum(others) / len(others) if others else 0.0)

    if not swing:
        return None

    return Moment(
        index=entry.index,
        turn=entry.before.turn,
        phase=entry.before.phase,
        player=entry.player,
        who=(
            journal.players[entry.player]
            if 0 <= entry.player < seats
            else str(entry.player)
        ),
        command=entry.command,
        label=entry.label or entry.command,
        swing=swing,
        ledgers=ledgers,
        dice=tuple(dice),
        chance=chance,
        said=tuple(dict.fromkeys(said)),
    )


def _chance_of(payload: Any) -> float | None:
    """
    The chance an attack roll would land, from what the engine required of it.
    """
    required = payload.get("required")
    sides = int(payload.get("sides") or 6)

    if not isinstance(required, int) or sides <= 0:
        return None

    return max(0.0, min(1.0, (sides - required + 1) / sides))
