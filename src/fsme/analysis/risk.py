# src/fsme/analysis/risk.py

"""
The decisions a game was lost on, measured against a yardstick that says so.

A journal records what a player did and what else the engine would have
accepted. It cannot say which of those was the better move, because nothing in
the engine has an opinion about better. So this brings one: the game is
replayed through the ordinary engine, and at every move the heuristic bot is
asked to weigh everything on offer. The gap between what was played and what
the bot would have played is the number reported.

That number is a disagreement, not a mistake. The yardstick is
``fsme.bot.heuristic`` — a bot that looks one move ahead, knows four things
about the game, and has no idea what most cards say. Calling its preference a
mistake would be dressing up an opinion as a finding, and the wording never
does. What makes the opinion usable anyway is that it is legible: every gap
comes with the reasons behind both moves, in the bot's own arithmetic, so a
reader who thinks the bot is wrong can see precisely which weight to argue
with.

Two of the numbers are not opinion at all, and they are the ones worth reading
first. The chance an attack roll lands is exact — one die against a printed
difficulty. Whether a miss would have been lethal is exact — the attacker's hit
points against the monster's attack. "Attacked at 1 hit point on a 50% roll" is
arithmetic; whether it was the wrong thing to do is not, and the report keeps
the two apart.

A last honesty. For a seat the bot itself played, the gap is zero everywhere by
construction — it cannot disagree with itself — so the report says which seats
those were rather than letting a wall of zeroes read as good play.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from fsme.bot import HeuristicBot
from fsme.bot.evaluation import Evaluation, Reason
from fsme.commands import Command
from fsme.content import ContentLibrary
from fsme.game import Game
from fsme.journal import Journal

WORTH_MENTIONING = 1.0
"""
How large a disagreement has to be before it is printed, in the bot's points.

A little under a loot card. Below this the bot is choosing between things it
barely tells apart, and printing its preference would suggest it had one.
"""

A_DANGER = -1.0
"""
How negative a reason has to be to be called a danger.
"""


@dataclass(slots=True)
class Risky:
    """
    One move, and what the yardstick made of it.
    """

    index: int
    turn: int
    phase: str

    player: int
    who: str

    label: str

    taken: float = 0.0
    """What the bot scored the move that was made."""

    best: float = 0.0
    """What the bot scored the best move on offer."""

    instead: str = ""
    """The move the bot would have made."""

    considered: int = 0
    """How many moves the seat had to choose between."""

    times: int = 1
    """
    How often this seat made this same move in this game.

    A player who attacks the same monster at two hit points nine times has made
    one mistake nine times, not nine mistakes, and a report that filled its
    three rows with the same move would be hiding the other two findings.
    """

    dangers: tuple[Reason, ...] = ()
    """
    The reasons in the move that counted against it.

    Some of these are exact — the chance a die lands, whether a miss is lethal
    — and some are preferences. Each is printed with its own words, which is
    where the difference shows.
    """

    @property
    def regret(self) -> float:
        return self.best - self.taken

    @property
    def was_a_choice(self) -> bool:
        """
        Whether the seat had anything else to do.

        A forced move is not a decision, and a report that scolded a player for
        one would be scolding them for the engine's arithmetic.
        """
        return self.considered > 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "turn": self.turn,
            "phase": self.phase,
            "player": self.player,
            "who": self.who,
            "label": self.label,
            "taken": self.taken,
            "best": self.best,
            "instead": self.instead,
            "regret": self.regret,
            "considered": self.considered,
            "times": self.times,
            "was_a_choice": self.was_a_choice,
            "dangers": [danger.to_dict() for danger in self.dangers],
        }


@dataclass(slots=True)
class Risks:
    """
    What a whole game looked like against the yardstick.
    """

    seed: int
    by: str = ""
    """The yardstick that judged it, named so the judgement can be dismissed."""

    weighed: int = 0
    """Moves the bot was able to have an opinion about."""

    skipped: int = 0
    """
    Moves it could not: answers to questions, and moves it failed to recognise.

    Reported rather than hidden. A report that weighed a tenth of a game and
    said nothing about the other nine would be worse than no report.
    """

    forced: int = 0

    bot_seats: tuple[int, ...] = ()

    riskiest: list[Risky] = field(default_factory=list)
    """Moves carrying the largest danger, whatever the bot thought overall."""

    worst: list[Risky] = field(default_factory=list)
    """Moves the bot most disagreed with."""

    faithful: bool = True
    """
    Whether the replay reproduced the journal.

    False means the engine has changed under the game and every number here is
    about a different one.
    """

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "by": self.by,
            "weighed": self.weighed,
            "skipped": self.skipped,
            "forced": self.forced,
            "bot_seats": list(self.bot_seats),
            "faithful": self.faithful,
            "riskiest": [risk.to_dict() for risk in self.riskiest],
            "worst": [risk.to_dict() for risk in self.worst],
        }


def risks(
    journal: Journal,
    library: ContentLibrary,
    *,
    top: int = 3,
    seat: int | None = None,
) -> Risks:
    """
    Replay a game and hold every move against what the bot would have played.

    ``seat`` narrows it to one player's decisions, which is what somebody
    asking why they lost wants. Without it, every seat is weighed.
    """
    bot = HeuristicBot(journal.seed)

    told = Risks(seed=journal.seed, by=bot.name, bot_seats=_who_thought(journal))

    game = Game.from_content(library, list(journal.players), seed=journal.seed)
    game.start()

    weighed: list[Risky] = []

    for entry, (kind, player, payload) in zip(
        journal.entries, journal.commands(), strict=True
    ):
        judged = (
            None
            if (seat is not None and entry.player != seat)
            else _judge(game, journal, entry, bot)
        )

        if judged is None:
            told.skipped += 1
        else:
            told.weighed += 1

            if judged.was_a_choice:
                weighed.append(judged)
            else:
                told.forced += 1

        if not game.submit(
            Command(type=kind, player=player, payload=dict(payload))
        ).accepted:
            told.faithful = False

            break

    told.worst = _the_distinct_ones(
        sorted(
            (risk for risk in weighed if risk.regret >= WORTH_MENTIONING),
            key=lambda risk: -risk.regret,
        ),
        weighed,
        top=top,
    )

    told.riskiest = _the_distinct_ones(
        sorted(
            (risk for risk in weighed if risk.dangers),
            key=lambda risk: sum(danger.worth for danger in risk.dangers),
        ),
        weighed,
        top=top,
    )

    return told


def _the_distinct_ones(
    ranked: list[Risky], weighed: list[Risky], *, top: int
) -> list[Risky]:
    """
    Take the worst of each repeated move rather than the worst few moves.

    The first time a seat walks into something is the finding; the eighth is
    the same finding. Each row keeps the count of how often the move was made,
    so nothing is lost by not printing it eight times.
    """
    often: Counter[tuple[int, str]] = Counter(
        (risk.player, risk.label) for risk in weighed
    )

    kept: list[Risky] = []
    seen: set[tuple[int, str]] = set()

    for risk in ranked:
        signature = (risk.player, risk.label)

        if signature in seen:
            continue

        seen.add(signature)

        risk.times = often[signature]

        kept.append(risk)

        if len(kept) >= top:
            break

    return kept


def _who_thought(journal: Journal) -> tuple[int, ...]:
    """
    The seats whose moves came with a bot's working attached.
    """
    return tuple(
        sorted({entry.player for entry in journal.entries if entry.decision})
    )


def _judge(
    game: Game, journal: Journal, entry: Any, bot: HeuristicBot
) -> Risky | None:
    """
    Weigh one move against everything the seat could have done instead.

    ``None`` when there is nothing to weigh: an open question, which the bot
    has no opinion about and says so, or a move the bot could not find among
    the ones on offer — which would be a disagreement between two parts of the
    engine and is counted as unweighed rather than guessed at.
    """
    if game.runtime.awaiting_decision is not None:
        return None

    opinions = bot.opinions(game, seats=(entry.player,))

    if not opinions:
        return None

    taken = _the_one_that_was_played(opinions, entry)

    if taken is None:
        return None

    best = max(opinions, key=lambda opinion: opinion[1].score)

    return Risky(
        index=entry.index,
        turn=entry.before.turn,
        phase=entry.before.phase,
        player=entry.player,
        who=(
            journal.players[entry.player]
            if 0 <= entry.player < len(journal.players)
            else str(entry.player)
        ),
        label=entry.label or entry.command,
        taken=taken.score,
        best=best[1].score,
        instead=str(best[0]["label"]),
        considered=len(opinions),
        dangers=tuple(
            reason for reason in taken.reasons if reason.worth <= A_DANGER
        ),
    )


def _the_one_that_was_played(
    opinions: tuple[tuple[dict[str, Any], Evaluation], ...], entry: Any
) -> Evaluation | None:
    """
    Find the move that was actually made among the ones on offer.
    """
    for move, evaluation in opinions:
        if int(move["player"]) != entry.player:
            continue

        if str(move["type"]) != str(entry.command):
            continue

        if dict(move["payload"]) == dict(entry.payload):
            return evaluation

    return None
