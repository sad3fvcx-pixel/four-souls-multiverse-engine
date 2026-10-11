# src/fsme/lab/bot/evaluation.py

"""
Why a bot chose what it chose.

An evaluation is the bot's own arithmetic, kept. Not a description of it, not a
plausible account written afterwards — the very numbers the choice was made
from, so that a log of decisions is evidence about the bot rather than a story
about it. If the two could differ, the log would be worthless for the one job
it has, which is telling you when the bot is wrong and why.

That is also why nothing here is called a win chance. A bot that reasons one
move ahead cannot know its chance of winning, and a number named that way
invites everyone to believe it. What it can know exactly — the chance a die
shows enough, whether a miss would kill it — is named for what it is; what it
merely prefers is called a preference and given a weight you can read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Reason:
    """
    One thing the bot noticed, and what it made of it.
    """

    what: str

    value: float = 0.0
    """
    What was noticed, in whatever unit the reason is about.

    A probability, a number of souls, a number of hit points. The unit lives in
    the wording of ``what``, because a reason nobody can read is not a reason.
    """

    worth: float = 0.0
    """
    What this contributed to the score, in points.

    The scores are the bot's own currency and mean nothing outside it. They are
    kept so that two choices can be compared and so that a reader can see which
    consideration actually decided a move.
    """

    def to_dict(self) -> dict[str, Any]:
        return {"what": self.what, "value": self.value, "worth": self.worth}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Reason:
        return cls(
            what=str(data.get("what", "")),
            value=float(data.get("value", 0.0)),
            worth=float(data.get("worth", 0.0)),
        )

    def __str__(self) -> str:
        return f"{self.what} ({self.value:g}) {self.worth:+.1f}"


@dataclass(frozen=True, slots=True)
class Evaluation:
    """
    One move, scored.
    """

    move: str

    score: float = 0.0
    reasons: tuple[Reason, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "move": self.move,
            "score": self.score,
            "reasons": [reason.to_dict() for reason in self.reasons],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Evaluation:
        return cls(
            move=str(data.get("move", "")),
            score=float(data.get("score", 0.0)),
            reasons=tuple(
                Reason.from_dict(reason) for reason in data.get("reasons", ())
            ),
        )


@dataclass(frozen=True, slots=True)
class Decision:
    """
    A choice, with the working that produced it.

    Every move the bot weighed is kept, not only the one it took. A log that
    held the winner alone could not tell you whether the bot chose well — you
    would see what it did and never what it passed over.
    """

    chosen: Evaluation

    considered: tuple[Evaluation, ...] = ()

    by: str = ""
    """Which bot this was, since a log outlives the run that made it."""

    notes: tuple[str, ...] = field(default_factory=tuple)
    """
    Anything the bot wants said that is not a number.

    "Nothing scored above passing" is worth recording and is not a reason.
    """

    def to_dict(self) -> dict[str, Any]:
        return {
            "by": self.by,
            "chosen": self.chosen.to_dict(),
            "considered": [
                evaluation.to_dict() for evaluation in self.considered
            ],
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Decision:
        return cls(
            by=str(data.get("by", "")),
            chosen=Evaluation.from_dict(data.get("chosen", {})),
            considered=tuple(
                Evaluation.from_dict(item) for item in data.get("considered", ())
            ),
            notes=tuple(str(note) for note in data.get("notes", ())),
        )

    @property
    def margin(self) -> float | None:
        """
        How far ahead the chosen move was of the next best.

        A move taken by a hair is a different thing from a move taken because
        everything else was hopeless, and only this tells them apart.
        """
        rest = [
            evaluation.score
            for evaluation in self.considered
            if evaluation is not self.chosen
        ]

        if not rest:
            return None

        return self.chosen.score - max(rest)
