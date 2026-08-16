# When a deck runs out

A known limitation, its cause, and the three things that could be done about
it. Nothing here has been changed: the reading of the rule that would settle it
is a decision, not a bug fix, and it moves every number the project has
measured.

## What happens

Six seeds in a thousand — 113, 137, 167, 251, 300 and 727 — produce a game that
never ends. Each runs to roughly 7950 turns before a step budget stops it, with
a journal of 63 MiB and nearly 290 000 events. Nothing crashes and nothing
loops in the engine's own sense: all 20 000 positions are distinct, so the
stability guard never fires. The game simply makes no progress.

Every one of them is the same shape:

```
the loot deck is empty
  ↓
XIX. The Sun is played: "Put this on the bottom of the loot deck.
  If you do, take an extra turn after this one if it's your turn."
  ↓
the deck now holds exactly one card, The Sun
  ↓
the loot step of the extra turn draws it
  ↓
the deck is empty again, and the player has The Sun
  ↓
repeat
```

The loot discard sits at 145 cards throughout and is never shuffled back in.

## Why

Not the card. `XIX. The Sun` is implemented completely and correctly: both
effects are present, and the printed condition "if it's your turn" is there as
`player_active` and does apply. An earlier audit note of mine said the condition
was missing; that was wrong, and this document supersedes it.

The cause is *when* a deck is rebuilt.

`COMPREHENSIVE_RULES.md` §9 says:

> A deck that runs out is rebuilt by shuffling its discard pile. This does not
> use the queue.

The engine reads "runs out" as *when somebody tries to draw and cannot*. The
rebuild lives inside the draw (`fsme/effects/builtin/loot.py`, `_next_loot`):
if the deck is empty at the moment of a draw, the discard is shuffled in first.

The other reading is *when the deck becomes empty*. Under it, drawing The Sun
empties the deck, the 145-card discard is shuffled back at once, and The Sun
goes to the bottom of a full deck instead of an empty one.

The two readings are indistinguishable in every game where nothing is put into
a deck between it emptying and the next draw. `XIX. The Sun` is the one card
that does exactly that.

That the timing is the whole cause was checked rather than argued. Patching the
refill to the eager reading — in a scratch process, nothing committed — made all
six games finish normally:

| seed | as it is | rebuilt when the deck empties |
|---|---|---|
| 113 | 20 000 commands, turn 7975, unfinished | 634 commands, turn 186, finished |
| 137 | 20 000, 7953, unfinished | 766, 184, finished |
| 167 | 20 000, 7946, unfinished | 560, 174, finished |
| 251 | 20 000, 7927, unfinished | 946, 231, finished |
| 300 | 20 000, 7913, unfinished | 849, 195, finished |
| 727 | 20 000, 5631, unfinished | 758, 225, finished |

## Classification

**RULE GAP.** Not a defect of the card, and not a defect of the deck mechanic
in the sense of contradicting something written down: the engine implements one
of two available readings of one sentence. What is missing is a decision about
which reading is right.

## What else touches this

Two things widen it beyond one card.

**Only one deck is rebuilt at all.** `_refill_loot_deck` is the only place in
the engine that shuffles a discard back into a deck. The monster, treasure and
room decks are never rebuilt — when they run out they stay out. This is latent
rather than reachable: across sixty measured games the monster deck never fell
below 228 of ~277 cards, the treasure deck below 259 of ~285, and the room deck
below 52 of 67. The loot deck is the only one under real pressure, because it
is drawn every turn.

**Forty-eight cards move cards between deck positions.** `move_cards` is used 48
times in the loaded content, including eight to the bottom of the treasure deck,
eight to the top of the monster deck and five to the bottom of the monster deck.
Every one of them meets the same question, and today they meet it against decks
that are never rebuilt.

## Options

### A — change the deck mechanic

Rebuild a deck the moment it runs out, for every deck.

*For:* it is the reading §9 most naturally supports; it removes the six stuck
games without inventing anything; it settles the monster, treasure and room
decks by the same stroke; and the forty-eight `move_cards` cards stop depending
on which of two readings is in force.

*Against:* it changes when the loot deck is shuffled, so it changes the deal of
every game from that point on. Every measured number in the project — the
studies, the examples, the demonstration, the numbers quoted in the
documentation — is recomputed. It should be done once, deliberately, together
with the decision about the other three decks, and not as a side effect of
fixing one card.

### B — keep the mechanic, add a rule about repetition

Leave the deck alone and stop the repetition some other way: a cap on
consecutive extra turns, or a stalled-turn guard like the one that already ends
a combat in which neither side can hurt the other.

*For:* the six games finish and almost no measured number moves, because the
guard fires only where the game was already stuck.

*Against:* it is a rule that appears on no card and in no specification, so it
would have to be marked as a safeguard of the engine rather than a rule of the
game — the way `STALLED_COMBAT_ROUNDS` is. And it treats the symptom: a card
sent to the bottom of an empty deck stays anomalous for the other forty-seven
cards that can do it.

### C — change nothing

Record the limitation, keep a step budget in anything that runs many games, and
carry on.

*For:* nothing moves. Six games in a thousand is 0.6%, and every one of them is
recognisable — a turn count in the thousands.

*Against:* a person running `fsme study --games 1000` meets it, and a game that
never ends is a bad first impression however well documented. It also leaves
the §9 divergence in place, which is the sort of thing that is much cheaper to
settle now than after a year of measurements have been taken on top of it.

## Recommendation

**A, but as its own decision.** §9 reads for it, it removes the whole class
rather than this instance, and it answers the monster/treasure/room question at
the same time. It is not urgent — the limitation is documented and the failure
is recognisable — and it should not be smuggled in alongside unrelated work,
because the day it lands every number measured before it stops being comparable
with every number measured after.
