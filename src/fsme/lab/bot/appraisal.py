# src/fsme/lab/bot/appraisal.py

"""
What a card is worth, read off what the card says.

The bot used to price every treasure at one constant. That is the same as not
reading the card, and it made one particular decision impossible to get right:
buying. A purchase is a trade of a known price for an unknown gain, and a bot
that scores the gain as a constant is not deciding anything — it is applying a
sign.

This module reads the gain. It walks the effect data the engine already keeps
on a definition — ``Ability.effects``, ``Ability.cost``, ``Static`` — and prices
each entry it recognises in the currency the bot already scores moves in.

**It is not a second rule engine.** It never executes an effect, never resolves
a target, never evaluates a condition, and never touches game state to change
it. It reads the same frozen data the interpreter reads and adds numbers up.
Where the interpreter would ask "what happens", this asks only "how much". The
distinction matters, because the moment an appraiser starts predicting outcomes
it has to agree with the engine about them, and two things that must agree
about the rules are one thing too many.

**What it cannot read, it says so.** An effect name absent from :data:`WORTH`
contributes nothing and is counted in :attr:`Appraisal.unread`. That number is
the honest measure of how much of a card the bot understood, and it is carried
out to the caller rather than averaged away. Most of FSME's treasure pool is
currently unreadable in this sense — see ``docs/LIMITATIONS.md`` — and a bot
that quietly scored those at zero would prefer implemented cards over
unimplemented ones for no reason connected to the game.

**Nothing here is tuned to produce a behaviour.** Every weight is stated
against an anchor the bot already had (a soul, a hit point, a card in hand),
the horizon is measured rather than chosen, and the worth of a cent is worked
out from the card pool rather than picked. That is deliberate: it must be
possible to disagree with this bot by disagreeing with a stated number, and
impossible to make it buy more by nudging one. The one number that would do
that — "what an item is worth" — does not exist here any more. It is an answer,
not an input.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from fsme.cards import CardDefinition
from fsme.cards.definition import Ability, Static
from fsme.cards.types import CardType
from fsme.rules.constants import SOULS_TO_WIN, TREASURE_COST
from fsme.state.modifiers import ATTACK, LOOT_PLAYS, LOOT_STEP, MAX_HP

from .evaluation import Reason

# ----------------------------------------------------------------------
# The anchors this is stated against
# ----------------------------------------------------------------------

SOUL_IS_WORTH = 12.0
"""Points for a soul. Four of them win, so nothing one move away outweighs one."""

DAMAGE_COSTS = 1.5
"""
Points per hit point.

Used in both directions. A point of damage costs its receiver this much, so a
point of damage dealt is worth this much, and a point of health kept is too.
The bot already priced a missed attack this way; the appraiser does not invent
a second exchange rate for the same thing.
"""

DYING_COSTS = 9.0
"""
Points for dying.

Health is priced at this instead of :data:`DAMAGE_COSTS` when the buyer is one
hit from dying, because at one hit point the hit point in question is the last
one and no longer costs what an ordinary one costs.
"""

LOOT_IS_WORTH = 1.2
"""Points for a card in hand."""

TURNS_AHEAD = 6.0
"""
How many of their own turns a buyer still has when an item becomes affordable.

Measured, not chosen: over 40 four-handed games played by this bot before it
could buy anything, a purchase first became affordable with a median of 6 of
that seat's own turns still to come (mean 8.2, quartiles 2 and 12). An item
bought now is therefore expected to be used about six more times, and that is
the multiplier a repeatable ability gets.

The measurement was taken from games in which nobody bought anything, which is
the only kind of game that existed when it was taken. Buying changes those
games, so this number describes the situation the decision is made in rather
than the situation that follows it. It is a baseline, and re-measuring it after
the bot has been buying for a while is the obvious next correction.
"""

TRIGGERS_FIRE = 0.5
"""
How often a triggered ability is assumed to find its trigger, per turn.

Unlike :data:`TURNS_AHEAD` this is a guess, and it is the only guess of its
kind here. A triggered ability fires when its trigger happens, and how often
that is depends on the trigger, on the board, and on what everybody else does —
none of which this module reads. Half a turn is a deliberately unambitious
placeholder, chosen to be clearly less than an activated ability's one use per
turn without pretending to know more.
"""

ONCE = 1.0
"""The multiplier for an ability that happens on arrival and never again."""


# ----------------------------------------------------------------------
# What each effect is worth, per unit of what the card printed
# ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Worth:
    """
    What one effect is worth, and which printed number scales it.
    """

    per_unit: float
    """Points per unit, in the anchors above. ``coin`` means a cent's worth."""

    parameter: str = ""
    """
    Which of the effect's parameters counts the units.

    Empty means the effect happens once however it is written: stealing a soul
    steals a soul.
    """

    coins: bool = False
    """
    Whether ``per_unit`` is measured in cents rather than points.

    A cent's worth is not a constant here — it is solved for from what cents
    buy — so effects denominated in cents carry a flag instead of a number.
    """

    capped: bool = False
    """
    Whether the printed number is bounded by what a card can actually absorb.

    Nine hundred and ninety-nine damage is not nine hundred and ninety-nine
    damage. It is enough, and enough is :attr:`Scale.most_health`.
    """

    health: bool = False
    """
    Whether this is worth health, and so worth more to a buyer about to die.

    Only about health the buyer keeps. Damage dealt to somebody else does not
    become more valuable because the dealer is nearly dead.
    """


WORTH: Mapping[str, Worth] = {
    # Money. Priced in cents, converted at the rate the scale works out.
    "gain_coins": Worth(1.0, "amount", coins=True),
    "lose_coins": Worth(-1.0, "amount", coins=True),
    "transfer_coins": Worth(1.0, "amount", coins=True),
    # Cards in hand.
    "draw_loot": Worth(LOOT_IS_WORTH, "count"),
    "discard_loot": Worth(-LOOT_IS_WORTH, "count"),
    # Health, in both directions.
    "deal_damage": Worth(DAMAGE_COSTS, "amount", capped=True),
    "heal": Worth(DAMAGE_COSTS, "amount", capped=True, health=True),
    "prevent_damage": Worth(DAMAGE_COSTS, "amount", capped=True, health=True),
    "prevent_next_damage": Worth(
        DAMAGE_COSTS, "amount", capped=True, health=True
    ),
    # Souls, which are the game.
    "gain_soul": Worth(SOUL_IS_WORTH, "count"),
    "claim_soul": Worth(SOUL_IS_WORTH),
    "steal_soul": Worth(SOUL_IS_WORTH),
    "lose_soul": Worth(-SOUL_IS_WORTH, "count"),
    # Items, priced at whatever an unread treasure is worth.
    "gain_treasure": Worth(float(TREASURE_COST), "count", coins=True),
    "steal_treasure": Worth(float(TREASURE_COST), coins=True),
}
"""
Every effect this module can put a number on.

Short on purpose. The engine knows sixty-odd effects and most of them do
something whose worth does not follow from any anchor the bot has: what is a
reroll worth, or a card moved to the top of a deck, or a monster discarded? A
number for those would be invented, and an invented number in a table like this
is indistinguishable from a measured one once it is written down.

So the table holds the effects whose worth is an exchange the bot already makes
elsewhere — cents, cards, hit points, souls, items — and everything else is
reported as unread. Adding an entry here is a claim that the exchange is
defensible, not that the effect is important.
"""


STATIC_WORTH: Mapping[str, tuple[float, bool]] = {
    ATTACK: (DAMAGE_COSTS, True),
    MAX_HP: (DAMAGE_COSTS, False),
    LOOT_PLAYS: (LOOT_IS_WORTH, True),
    LOOT_STEP: (LOOT_IS_WORTH, True),
}
"""
What a permanent modifier is worth per point, and whether it pays every turn.

The second element is the difference between income and stock. ``+1 attack``
pays out on the attack its controller makes each turn, so it is worth its
points once per turn for as long as the item is in play. ``+1 max HP`` raises a
ceiling once and then stops; it is worth its points, not its points per turn.
Conflating the two is how a bot ends up believing a single hit point is worth
more than a soul.

``purchases``, ``attacks``, ``difficulty`` and ``shop_cost`` are left out, and
each for the same reason: pricing them needs a number this bot does not have.
An extra attack per turn is worth whatever an attack is worth, which depends on
the monsters; a point of difficulty is worth a sixth of a hit, and what a hit
is worth depends on the same thing. ``shop_cost`` is the odd one — it is worth
cents, but only to a player who buys, and this bot is being taught to buy in
the same change that would price it. They are counted as unread rather than
guessed at.
"""


# ----------------------------------------------------------------------
# The scale
# ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Scale:
    """
    What this game's cards are like: what a cent buys, and how big a number gets.

    A cent's worth is not a preference. The rules print exactly one exchange
    between cents and anything else — ten cents buys a treasure — so a cent is
    worth a tenth of a treasure by the rules, and a treasure is worth whatever
    the treasures in *this* game happen to do. Change the card pool and the
    exchange rate changes with it, which is correct and is not something a
    constant could have expressed.

    **Money is a medium, not a store of value.** The pool is read once with a
    cent priced at nothing, so a treasure's worth is measured only in the things
    cents are not — souls, hit points, cards in hand — and the cent is then
    priced off that. The alternative is to let cents count towards the worth of
    the cards that cents buy, which is circular. It is a solvable circle: the
    appraisal is linear in the worth of a cent, so two readings give the line
    and the fixed point follows. It was solved, and the answer was rejected —
    on FSME's own content the loop nearly closes (the pool grants about 9.4
    cents' worth of cents per card against a price of 10), so the solution sits
    on a near-singularity and swings by a factor of sixty on a rounding change.
    A number that unstable is not a measurement. Reading money out of the
    denominator makes it stable and says something defensible while it is at it:
    a cent is worth what it buys, and what it buys is worth what it *does*.
    """

    coin: float
    """Points per cent."""

    item: float
    """Points for a treasure that has not been read."""

    most_health: int
    """
    The largest health printed on any card in this game.

    A cap, not an estimate. A card that deals 999 damage does not deal 999
    damage to anything — it kills what it hits, exactly like a card that deals
    enough — and an appraiser that multiplies the printed number by the worth of
    a hit point will value one board wipe above every soul in the game. Damage
    beyond what anything present can absorb is worth nothing extra, and this is
    where "what anything present can absorb" is read off the pool rather than
    assumed.
    """

    readable: int
    """How many of the pool's treasures had rules the appraiser could read."""

    pool: int
    """How many treasures were in the pool."""


FALLBACK_ITEM_IS_WORTH = 5.0
"""
What an unread treasure is worth when there is nothing to read.

The number the bot used for every item before it could read any of them. Kept
only as the answer to a pool with no rules in it at all — an empty content
directory, a test fixture — and never used otherwise.
"""

FALLBACK_HEALTH = 6
"""
The damage cap for a pool that prints no health anywhere.

Six is the die: the largest number this game asks anybody to roll, and the only
printed bound available when no card carries one.
"""


def scale_of(cards: Iterable[CardDefinition]) -> Scale:
    """
    Work out what a cent is worth from what this game's cards do.

    ``cards`` is the whole pool, not only the treasures: the cap on damage comes
    from the monsters, and the worth of a cent comes from the treasures.
    """
    pool = list(cards)

    treasures = [card for card in pool if card.type is CardType.TREASURE]
    readable = [card for card in treasures if card.abilities or card.statics]

    printed = [card.health for card in pool if card.health]
    most_health = max(printed) if printed else FALLBACK_HEALTH

    if not readable:
        return Scale(
            coin=FALLBACK_ITEM_IS_WORTH / TREASURE_COST,
            item=FALLBACK_ITEM_IS_WORTH,
            most_health=most_health,
            readable=0,
            pool=len(treasures),
        )

    # Priced with a cent at nothing, so that cents are not counted towards the
    # worth of the thing that gives cents their worth.
    item = sum(
        _read(card, 0.0, most_health=most_health).points for card in readable
    ) / len(readable)

    return Scale(
        coin=item / TREASURE_COST,
        item=item,
        most_health=most_health,
        readable=len(readable),
        pool=len(treasures),
    )


# ----------------------------------------------------------------------
# The appraisal
# ----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Appraisal:
    """
    What one card is worth, and how much of it was understood.
    """

    points: float

    reasons: tuple[Reason, ...] = ()

    read: int = 0
    """Effect entries and statics the appraiser recognised."""

    unread: tuple[str, ...] = ()
    """
    What it did not recognise, by name, in the order met.

    Carried out rather than swallowed: a card scored at two points because the
    appraiser understood a fifth of it is a different fact from a card scored
    at two points because that is what it does.
    """

    @property
    def understood(self) -> float:
        """
        The share of this card's entries the appraiser could price, 0 to 1.
        """
        total = self.read + len(self.unread)

        return 1.0 if not total else self.read / total


def appraise(
    face: CardDefinition,
    scale: Scale,
    *,
    hurt: bool = False,
    turns: float = TURNS_AHEAD,
) -> Appraisal:
    """
    What this card is worth to a buyer, in the bot's points.

    ``hurt`` prices health at what dying costs rather than what a hit point
    costs, and is true when the buyer is one hit from dead. ``turns`` is how
    long the item is expected to serve; a caller who knows the game is nearly
    over passes a shorter horizon and every repeatable ability shrinks with it.

    A card with no rules the engine knows is worth what an unread treasure is
    worth, not nothing. FSME has not implemented most of its own treasure pool,
    and a bot that scored the unimplemented ones at zero would be preferring
    cards for a reason that has nothing to do with Four Souls.
    """
    if not face.abilities and not face.statics:
        return Appraisal(
            scale.item,
            (Reason("a card FSME has not written down", 0, scale.item),),
            read=0,
            unread=("(no rules)",),
        )

    return _read(
        face, scale.coin, hurt=hurt, turns=turns, most_health=scale.most_health
    )


def _read(
    face: CardDefinition,
    coin: float,
    *,
    hurt: bool = False,
    turns: float = TURNS_AHEAD,
    most_health: int = FALLBACK_HEALTH,
) -> Appraisal:
    """
    Add up what a card's abilities and statics come to.

    Kept separate from :func:`appraise` because :func:`scale_of` calls it with
    a cent priced at nothing to find what a cent is worth, and must not go
    through the branch that prices an unreadable card at the answer it is
    looking for.
    """
    points = 0.0
    reasons: list[Reason] = []
    read = 0
    unread: list[str] = []

    for ability in face.abilities:
        unpriced = _unpriced_cost(ability)

        if unpriced:
            # An ability whose price cannot be read cannot be valued either.
            # Counting the payout and skipping the bill is how a card that
            # costs nine counters comes out as the best card in the game.
            unread.append(f"cost:{unpriced}")
            continue

        uses = _uses(ability, turns)

        if not uses:
            continue

        worth, counted, missed = _effects(
            ability.effects, coin, hurt=hurt, most_health=most_health
        )

        read += counted
        unread.extend(missed)

        if ability.optional:
            # Nobody is made to use an ability that would hurt them.
            worth = max(0.0, worth)

        each = worth - _cost(ability, coin)

        if not each:
            continue

        points += each * uses
        reasons.append(
            Reason(
                _describe(ability),
                round(uses, 2),
                round(each * uses, 3),
            )
        )

    for static in face.statics:
        worth, counted, missed = _static(static, turns, hurt=hurt)

        read += counted
        unread.extend(missed)

        if not worth:
            continue

        points += worth
        reasons.append(
            Reason(
                static.description or f"{static.stat} while in play",
                static.amount,
                round(worth, 3),
            )
        )

    return Appraisal(points, tuple(reasons), read=read, unread=tuple(unread))


def _uses(ability: Ability, turns: float) -> float:
    """
    How many times this ability is expected to happen, once bought.
    """
    if _destroys_itself(ability):
        # "Destroy this. If you do, ..." is the whole card, once.
        return ONCE

    if ability.trigger == "on_activate":
        # Tap, recharge at the start of your turn, tap again.
        return turns

    if ability.trigger in ("on_enter", "on_purchase"):
        return ONCE

    return turns * TRIGGERS_FIRE


def _destroys_itself(ability: Ability) -> bool:
    """
    Whether using this ability takes the card off the board.
    """
    return any(
        isinstance(entry, Mapping)
        and entry.get("effect") == "destroy_treasure"
        and entry.get("target") == "self"
        for entry in _everywhere(ability.effects)
    )


def _everywhere(effects: Any) -> Iterator[Any]:
    """
    Every effect entry in a list, including the ones inside conditionals.
    """
    if isinstance(effects, Mapping):
        yield effects

        for key in ("then", "else"):
            yield from _everywhere(effects.get(key, ()))
    elif isinstance(effects, (list, tuple)):
        for entry in effects:
            yield from _everywhere(entry)


def _effects(
    effects: Sequence[Any], coin: float, *, hurt: bool, most_health: int
) -> tuple[float, int, list[str]]:
    """
    Add up a list of effect entries.
    """
    points = 0.0
    read = 0
    unread: list[str] = []

    for entry in effects:
        worth, counted, missed = _entry(
            entry, coin, hurt=hurt, most_health=most_health
        )

        points += worth
        read += counted
        unread.extend(missed)

    return points, read, unread


def _entry(
    entry: Any, coin: float, *, hurt: bool, most_health: int
) -> tuple[float, int, list[str]]:
    """
    What one effect entry is worth.

    A conditional entry is worth the average of the branches it might take, not
    their sum: a card that does one of three things does one of them. Where
    there is no ``else``, the missing branch is worth nothing, which is what
    happens when the condition does not hold.
    """
    if not isinstance(entry, Mapping):
        return 0.0, 0, []

    if "if" in entry:
        taken, read, unread = _effects(
            entry.get("then", ()), coin, hurt=hurt, most_health=most_health
        )
        missed, more_read, more_unread = _effects(
            entry.get("else", ()), coin, hurt=hurt, most_health=most_health
        )

        return (taken + missed) / 2.0, read + more_read, [*unread, *more_unread]

    if entry.get("effect") == "add_modifier" or "add_modifier" in entry:
        # A modifier handed out by an effect is the same thing a static grants,
        # for the turn it lasts rather than for as long as the card is in play.
        return _granted(entry, hurt=hurt)

    name, units = _named(entry)

    if not name:
        return 0.0, 0, []

    worth = WORTH.get(name)

    if worth is None:
        return 0.0, 0, [name]

    rate = worth.per_unit * (coin if worth.coins else 1.0)

    if worth.capped:
        # Damage past what anything present can absorb is worth nothing extra.
        units = max(-float(most_health), min(units, float(most_health)))

    if worth.health and hurt:
        rate = rate / DAMAGE_COSTS * DYING_COSTS

    return rate * units, 1, []


def _granted(entry: Mapping[str, Any], *, hurt: bool) -> tuple[float, int, list[str]]:
    """
    What a modifier handed out by an effect is worth, for the turn it lasts.
    """
    stat = str(entry.get("stat", ""))
    amount = entry.get("amount", 0)

    known = STATIC_WORTH.get(stat)

    if known is None or not isinstance(amount, int):
        return 0.0, 0, [f"add_modifier:{stat or '?'}"]

    per_point, _income = known

    if stat == MAX_HP and hurt:
        per_point = DYING_COSTS

    return per_point * amount, 1, []


def _named(entry: Mapping[str, Any]) -> tuple[str, float]:
    """
    The effect an entry names, and how many units of it the card printed.

    Two forms mean the same thing. ``{"effect": "deal_damage", "amount": 2}``
    is the long one, and ``{"deal_damage": 2}`` is the shorthand the DSL allows
    where the effect declares which parameter the bare value fills. This reads
    both, and reads the count off whichever form it found.
    """
    if "effect" in entry:
        name = str(entry["effect"])
        worth = WORTH.get(name)
        parameter = worth.parameter if worth else ""
        printed = entry.get(parameter) if parameter else None

        return name, _count(printed)

    for key, value in entry.items():
        if key in WORTH:
            return str(key), _count(value)

    return "", 0.0


def _count(printed: Any) -> float:
    """
    How many units a printed value stands for.

    A number is itself. Anything else — ``{"from": "dice"}``, a name the ability
    learns while it runs — is a number this module cannot know without running
    the ability, so it counts as one. That is a floor, not an estimate, and a
    card whose payout is written that way is worth at least as much as this
    says.
    """
    if isinstance(printed, bool):
        return 1.0

    if isinstance(printed, (int, float)):
        return float(printed)

    return 1.0


PRICED = frozenset({"tap", "coins", "discard"})
"""
The parts of an ability's price this module has an exchange rate for.

Tapping is free in points because being usable once a turn is already what the
horizon assumes. Cents and discarded cards are priced where the table prices
them. Everything else — counters spent, hit points paid — is a bill the
appraiser cannot read, and an ability with one is not valued at all.
"""


def _unpriced_cost(ability: Ability) -> str:
    """
    The part of this ability's price the appraiser cannot read, if there is one.
    """
    unknown = sorted(str(key) for key in ability.cost if key not in PRICED)

    return unknown[0] if unknown else ""


def _cost(ability: Ability, coin: float) -> float:
    """
    What using an ability costs its controller, per use.

    Only reached once :func:`_unpriced_cost` has confirmed every part of the
    price is one of :data:`PRICED`, so nothing is silently left off the bill.
    """
    paid = 0.0

    coins = ability.cost.get("coins")

    if isinstance(coins, int):
        paid += coins * coin

    discard = ability.cost.get("discard")

    if isinstance(discard, int):
        paid += discard * LOOT_IS_WORTH

    return paid


def _static(
    static: Static, turns: float, *, hurt: bool
) -> tuple[float, int, list[str]]:
    """
    What a permanent modifier is worth for as long as the card is in play.
    """
    if static.forbids:
        return 0.0, 0, [f"forbids:{static.forbids}"]

    known = STATIC_WORTH.get(static.stat)

    if known is None:
        return 0.0, 0, [f"static:{static.stat or '?'}"]

    per_point, income = known

    if static.stat == MAX_HP and hurt:
        per_point = DYING_COSTS

    if static.per_counter:
        # Worth its amount for each counter, and it starts with none.
        return 0.0, 0, [f"static:{static.stat}:per_counter"]

    return per_point * static.amount * (turns if income else 1.0), 1, []


def _describe(ability: Ability) -> str:
    """
    The ability in the words the card wrote, short enough for a log line.
    """
    said = ability.description or ability.trigger

    return said if len(said) <= 60 else f"{said[:57]}..."


# ----------------------------------------------------------------------
# How long the item has to work
# ----------------------------------------------------------------------


def horizon(souls_held: int, *, turns: float = TURNS_AHEAD) -> float:
    """
    How long an item bought now is expected to serve, given how the game stands.

    An item that pays out over six turns is worth six turns of payout in a game
    with six turns left in it, and rather less in a game somebody is about to
    win. ``souls_held`` is the largest number of souls anybody at the table has;
    the fraction of the game still to play is what is left of
    :data:`~fsme.rules.constants.SOULS_TO_WIN`.

    This is the one place a card's worth depends on the position rather than on
    the card, and it is deliberately the crudest possible reading of the
    position: how close is anybody to winning. A bot that modelled the race
    properly would be a different bot.
    """
    left = max(0, SOULS_TO_WIN - souls_held)

    return max(1.0, turns * left / SOULS_TO_WIN)


__all__ = [
    "Appraisal",
    "DAMAGE_COSTS",
    "DYING_COSTS",
    "FALLBACK_HEALTH",
    "FALLBACK_ITEM_IS_WORTH",
    "LOOT_IS_WORTH",
    "STATIC_WORTH",
    "SOUL_IS_WORTH",
    "Scale",
    "TRIGGERS_FIRE",
    "TURNS_AHEAD",
    "WORTH",
    "Worth",
    "appraise",
    "horizon",
    "scale_of",
]
