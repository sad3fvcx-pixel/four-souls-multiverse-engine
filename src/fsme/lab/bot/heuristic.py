# src/fsme/lab/bot/heuristic.py

"""
A bot that thinks one move ahead, and shows its working.

It is not strong and is not trying to be. It knows four things — that souls
win, that dying is expensive, that a die has six faces, and what the cards in
front of it say they do — and it applies them to the moves the engine says it
may make. Every number it uses comes from the position, from the rules, or from
the printed text of a card; nothing is estimated from games it has not played.

Its purpose is to be *legible*. A bot whose reasoning can be read is one whose
mistakes can be found, and finding them is the whole point of writing the
reasoning down. Where it guesses, the guess is a named preference with a weight
beside it, so that a reader disagreeing with a choice can see exactly which
number to argue with.

What it does not do is worth stating too. It does not look ahead past the move
in front of it, and it does not model what other players will do. It reads
cards only where it is deciding about a particular card — which today means
buying, and does not yet mean playing a loot card, where anything it has no
opinion about is still worth a small constant.
"""

from __future__ import annotations

import random
from typing import Any

from fsme.api.moves import legal_moves
from fsme.cards import CardRegistry
from fsme.commands import Command, CommandType
from fsme.game import Game
from fsme.rules.constants import DICE_SIDES
from fsme.rules.shop import DECK as BUY_DECK
from fsme.rules.shop import shop_price
from fsme.rules.statics import DIFFICULTY, monster_value

# The currency lives next door because the appraiser is denominated in it and
# cannot import from here without a cycle. One definition, two readers.
from .appraisal import (
    DAMAGE_COSTS,
    DYING_COSTS,
    LOOT_IS_WORTH,
    SOUL_IS_WORTH,
    TURNS_AHEAD,
    Appraisal,
    Scale,
    appraise,
    horizon,
    scale_of,
)
from .evaluation import Decision, Evaluation, Reason

NAME = "heuristic-1"

__all__ = [
    "DAMAGE_COSTS",
    "DYING_COSTS",
    "LOOT_IS_WORTH",
    "NAME",
    "SOUL_IS_WORTH",
    "HeuristicBot",
]


class HeuristicBot:
    """
    Scores the legal moves and takes the best, keeping its working.
    """

    def __init__(self, seed: int = 0, *, name: str = NAME) -> None:
        self._rng = random.Random(seed)
        self._name = name

        # What a cent is worth depends on what this game's treasures do, so it
        # is worked out once from the card pool and kept beside the registry it
        # was worked out from. A bot handed a different set of content asks
        # again rather than carrying the old answer into it.
        self._scale: Scale | None = None
        self._scaled_from: CardRegistry | None = None

    @property
    def name(self) -> str:
        return self._name

    def choose(
        self, game: Game, seats: tuple[int, ...] = ()
    ) -> tuple[Command, str, Decision] | None:
        """
        Decide the next thing to do, and say why.

        ``seats`` are the seats this bot is playing. The engine offers every
        legal move at the table, including cards other players may respond
        with, and a bot that took those would be playing their game as well as
        its own — which would make any comparison between it and them
        meaningless. So it chooses from its own moves when it has any.
        """
        decision = game.runtime.awaiting_decision

        if decision is not None:
            return self._answer(game, decision)

        opinions = self.opinions(game, seats=seats)

        if not opinions:
            return None

        moves = [move for move, _ in opinions]
        weighed = [evaluation for _, evaluation in opinions]

        best = max(weighed, key=lambda evaluation: evaluation.score)

        # Ties go to chance rather than to whichever the engine listed first:
        # a bot that always breaks ties the same way plays a much narrower
        # range of games than it appears to.
        tied = [
            evaluation
            for evaluation in weighed
            if evaluation.score >= best.score - 1e-9
        ]

        chosen = self._rng.choice(tied)
        move = moves[weighed.index(chosen)]

        return (
            Command(
                type=CommandType(move["type"]),
                player=int(move["player"]),
                payload=dict(move["payload"]),
            ),
            str(move["label"]),
            Decision(
                by=self._name,
                chosen=chosen,
                considered=tuple(weighed),
                notes=(
                    ("nothing scored above doing nothing",)
                    if chosen.score <= 0
                    else ()
                ),
            ),
        )

    def opinions(
        self, game: Game, seats: tuple[int, ...] = ()
    ) -> tuple[tuple[dict[str, Any], Evaluation], ...]:
        """
        Weigh every move on offer, without taking any of them.

        The same arithmetic ``choose`` runs, exposed so that a move somebody
        else made can be held against it. That is the only way this bot's
        opinion is worth anything about a game it did not play: it says what it
        would have done, in the currency it says everything in.
        """
        moves = legal_moves(game)

        if seats:
            mine = [move for move in moves if int(move["player"]) in seats]

            # Falling back is not politeness: if this bot has nothing to do and
            # the game is waiting on it, somebody has to move or the run stops.
            moves = mine or moves

        return tuple((move, self._weigh(game, move)) for move in moves)

    def _weigh(self, game: Game, move: dict[str, Any]) -> Evaluation:
        """
        Score one move from what the position and the rules say about it.
        """
        kind = str(move["type"])
        label = str(move["label"])
        seat = int(move["player"])

        if kind == str(CommandType.ATTACK):
            return self._weigh_attack(game, move, label, seat)

        if kind == str(CommandType.BUY_TREASURE):
            return self._weigh_purchase(game, move, label, seat)

        if kind == str(CommandType.PLAY_LOOT):
            return Evaluation(
                label,
                LOOT_IS_WORTH,
                (Reason("a card played is a card working", 1, LOOT_IS_WORTH),),
            )

        if kind == str(CommandType.ACTIVATE_TREASURE):
            return Evaluation(
                label,
                LOOT_IS_WORTH,
                (Reason("an item used is an item working", 1, LOOT_IS_WORTH),),
            )

        if kind in (str(CommandType.END_TURN), str(CommandType.END_PHASE)):
            return Evaluation(label, 0.0, (Reason("nothing left worth doing", 0, 0.0),))

        return Evaluation(label, -0.1, (Reason("passing", 0, -0.1),))

    def _weigh_attack(
        self, game: Game, move: dict[str, Any], label: str, seat: int
    ) -> Evaluation:
        """
        Score an attack from the die, the monster and the attacker's health.

        The chance of hitting is exact: one six-sided die against a printed
        difficulty. What follows from a hit or a miss is one round's worth and
        no further — this bot does not fight the whole fight in its head.
        """
        state = game.state
        player = state.player(seat)

        monster = self._monster(game, move)

        if monster is None:
            return Evaluation(
                label,
                0.5,
                (Reason("an unknown monster, turned over blind", 0, 0.5),),
            )

        printed = getattr(getattr(monster, "definition", None), "roll", None)
        required = monster_value(state, DIFFICULTY, monster, int(printed or 4))

        hits = max(0.0, min(1.0, (DICE_SIDES - required + 1) / DICE_SIDES))

        souls = int(getattr(getattr(monster, "definition", None), "souls", 0) or 0)
        attack = int(getattr(getattr(monster, "definition", None), "attack", 1) or 1)
        health = int(getattr(monster, "hp", 0) or 0)

        reasons = [Reason("chance the die is enough", round(hits, 3), 0.0)]

        score = 0.0

        # One hit finishes it, so the souls are on the table this round.
        if health <= 1 and souls:
            worth = hits * souls * SOUL_IS_WORTH
            score += worth
            reasons.append(Reason("a hit would finish it", souls, worth))
        elif souls:
            worth = hits * souls * SOUL_IS_WORTH / max(1, health)
            score += worth
            reasons.append(Reason("souls, further off", souls, worth))

        misses = 1.0 - hits

        if attack >= player.hp:
            worth = -misses * DYING_COSTS
            score += worth
            reasons.append(Reason("a miss would kill you", player.hp, worth))
        else:
            worth = -misses * attack * DAMAGE_COSTS
            score += worth
            reasons.append(Reason("what a miss costs", attack, worth))

        return Evaluation(label, score, tuple(reasons))

    def _weigh_purchase(
        self, game: Game, move: dict[str, Any], label: str, seat: int
    ) -> Evaluation:
        """
        Score a purchase by reading the card and pricing what it says.

        Four separate quantities, kept separate on purpose, because conflating
        any two of them is what made this decision wrong before:

        * **the price** — what the shop charges right now, which is a rules
          question and is asked of the rules rather than assumed to be ten;
        * **what the cents are worth** — a tenth of a treasure, because that is
          the only exchange the rules print;
        * **what the card does** — read off the card, in the same currency;
        * **what it is worth here** — the same reading, shortened when the game
          is nearly over and dearer when the buyer is nearly dead.

        The last three are what the appraiser answers. This method's own job is
        only to subtract the first from the third.
        """
        state = game.state
        player = state.player(seat)

        scale = self._scale_for(game)
        price = shop_price(state, seat)
        spent = -price * scale.coin

        turns = horizon(max(other.soul_count for other in state.players))
        hurt = player.hp <= 1

        card = self._on_offer(game, move)

        if card is None:
            # The top of the treasure deck, bought unseen. Nothing to read, so
            # it is worth what a treasure is worth — which at the printed price
            # makes this an even trade, and the bot is genuinely indifferent.
            return Evaluation(
                label,
                scale.item + spent,
                (
                    Reason("a treasure, bought unseen", 1, scale.item),
                    Reason("what it costs", price, spent),
                ),
            )

        read = appraise(card.face, scale, hurt=hurt, turns=turns)

        return Evaluation(
            label,
            read.points + spent,
            (
                *read.reasons,
                Reason("what it costs", price, spent),
                *self._caveats(read, player.pennies, turns),
            ),
        )

    def _caveats(
        self, read: Appraisal, pennies: int, turns: float
    ) -> tuple[Reason, ...]:
        """
        What the bot wants on the record beside a purchase, worth nothing itself.

        A card the appraiser understood a third of is a different card from one
        it understood all of, and the score alone cannot tell them apart. These
        carry no points; they are here so that a reader looking at a purchase
        that went badly can see whether the bot was wrong or merely blind.
        """
        said: list[Reason] = [Reason("cents in hand", pennies, 0.0)]

        if read.unread:
            said.append(
                Reason(
                    "of the card it could not read: " + ", ".join(read.unread[:4]),
                    len(read.unread),
                    0.0,
                )
            )

        if turns < TURNS_AHEAD:
            said.append(Reason("turns it expects the item to serve", turns, 0.0))

        return tuple(said)

    def _on_offer(self, game: Game, move: dict[str, Any]) -> Any | None:
        """
        The card a purchase would take, when the purchase names one.
        """
        payload = move["payload"]

        if payload.get("source") == BUY_DECK:
            return None

        index = int(payload.get("index", 0))
        shop = game.state.treasure_shop.cards

        return shop[index] if 0 <= index < len(shop) else None

    def _scale_for(self, game: Game) -> Scale:
        """
        What a cent buys in this game, worked out once from the card pool.

        The pool is the printed card list, which is public: reading it is not
        the same as looking at the deck. What the bot never sees is the order
        the deck is in, and nothing here asks.
        """
        registry = game.runtime.cards

        if self._scale is None or self._scaled_from is not registry:
            self._scale = scale_of(registry)
            self._scaled_from = registry

        return self._scale

    def _monster(self, game: Game, move: dict[str, Any]) -> Any | None:
        """
        The monster a declared attack is aimed at, when it is aimed at one.
        """
        payload = move["payload"]

        if payload.get("source") == "deck":
            return None

        index = int(payload.get("index", 0))
        monsters = game.state.active_monsters.cards

        return monsters[index] if 0 <= index < len(monsters) else None

    def _answer(self, game: Game, decision: Any) -> tuple[Command, str, Decision]:
        """
        Answer a question the engine asked.

        The bot has no opinion about most questions — which loot card to
        discard, which of three effects to take — and says so rather than
        inventing a preference it does not have. It answers with the fewest
        options the question allows, which is the least it can do without
        pretending to a judgement it has not made.
        """
        count = len(decision.options)

        lowest = max(0, min(decision.minimum, count))
        highest = max(lowest, min(decision.maximum, count))

        wanted = lowest if lowest else min(highest, 1 if count else 0)
        picks = self._rng.sample(range(count), wanted) if count else []

        chosen = ", ".join(
            str(getattr(decision.options[index], "name", decision.options[index]))
            for index in picks
        )

        label = f"{decision.prompt or decision.kind} → {chosen or 'nothing'}"

        return (
            Command(
                type=CommandType.CHOOSE_TARGET,
                player=decision.player,
                payload={"choices": picks},
            ),
            label,
            Decision(
                by=self._name,
                chosen=Evaluation(label, 0.0, ()),
                notes=("no opinion about this question; answered at random",),
            ),
        )
