# What could come next, and why none of it is here yet

FSME is being shown to people for the first time. This file is the list of
directions that look worth taking — kept as a list on purpose.

Nothing below is scheduled. Each of these is a guess about what somebody will
need, and a guess about a user is worth much less than one sentence from a real
one. The point of writing them down is so that when a real need turns up, it
can be recognised as one of these rather than argued about from scratch — and
so that anything *not* on this list can be looked at freshly rather than
squeezed into a plan made before anybody had used the thing.

The order is not a priority. The signal that would justify each one is.

---

## Analysing games people actually played

**What it would be.** Import a game somebody played at a real table — from a
log, a form, a photograph of the board, whatever turns out to be practical —
and report on it the way `fsme report` reports on a game the engine dealt.

**Why it is interesting.** Every number FSME produces today comes from a table
of bots. That is honest and it is stated everywhere, but it means the analysis
has never met a human decision. A single real game would test whether the
turning-point measure and the decision weighing say anything a player
recognises.

**What would justify starting.** Somebody with a recorded game asking what
FSME makes of it. Not a hypothetical one: the hard part is the import format,
and inventing a format for games nobody has is how you get a format nobody can
use.

**What it must not become.** A play-by-post server. FSME reads games; it does
not run them for other people.

---

## More than one kind of player

**What it would be.** Agents other than `heuristic-1` and the random one: a
greedy attacker, a hoarder, a player who never fights above a certain risk.

**Why it is interesting.** Every measurement in the project is conditional on
who was playing, and right now that condition is one weak bot. "Coins gained
went with winning" may be a fact about Four Souls or a fact about a bot that
values coins at 0.6 points. Two different players disagreeing about a
measurement would be the most informative result the lab could produce.

**What would justify starting.** A finding somebody wants to trust. The moment
a card test result is used to change a card, the question "would a different
player see this?" stops being academic.

**Cost to be honest about.** Each new player is a new set of arguable weights,
and a table of five bots is five sets of assumptions rather than none.

---

## Helping a person play better

**What it would be.** Taking the decision weighing and pointing it at a human:
"here are the three moves you made that the bot rates worst, and why".

**Why it is interesting.** The machinery exists — `fsme report` already does
this for the seats a bot did not play.

**What would justify starting.** A player asking. And, first, the previous two
items: advice from a bot that thinks one move ahead and does not know what most
cards say is advice worth very little, and dressing it up as coaching would be
the least honest thing this project could do.

---

## Testing cards harder

**What it would be.** Several things that share a name:

- *paired seeds* — deal the same game with and without the card, so the two
  runs differ only where the card is. Today they differ everywhere, which is
  the largest single weakness of `fsme test-card`, and it is stated in the
  report rather than fixed;
- *per-character splits* — "this card does nothing in general but is strong
  for Isaac". Real, and a multiple-comparison trap: splitting by character
  multiplies the number of claims by the number of characters;
- *more than one card at a time* — testing a whole set rather than a card.

**Why it is interesting.** This is the tool people would come to FSME for, and
the paired-seed problem is the one that limits what it can say.

**What would justify starting.** Paired seeds need no signal at all — it is a
known weakness of a shipped feature and would improve every card test. The
other two want somebody with a real set to balance.

---

## What is deliberately not on this list

Written down so that "we never thought of it" is not mistaken for "we thought
about it and said no".

- **A card maker.** Cards are JSON, the validator names mistakes and suggests
  spellings, and a form that writes the same JSON is a large amount of
  interface for a small amount of typing.
- **A story or lore generator.** The reports describe what the record shows.
  A narrator would produce sentences that read as findings and are not.
- **A playable game.** No accounts, no network play, no rules-lawyering
  against other humans. FSME deals games so it can measure them.
- **Plugins or a module system.** There is no second implementation of
  anything yet, so an extension point would be a guess about a shape nobody
  has needed.

---

## The line that holds regardless

Whatever gets built: the core plays Four Souls and has never heard of the
laboratory, no report is part of the rules, and nothing that measures a game
may change one. That is enforced by `tests/test_architecture.py` rather than by
this paragraph.
