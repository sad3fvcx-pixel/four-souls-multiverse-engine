# When a deck runs out

One rule, four decks, and the timing that makes it work. This started as a
record of a known limitation; it is now a record of what was decided and what
changed.

## The rule

`COMPREHENSIVE_RULES.md` §9:

> A slot refills as soon as it is empty, as though it carried the triggered
> effect "when this slot is empty, refill it".
> […]
> A deck that runs out is rebuilt by shuffling its discard pile. This does not
> use the queue.

Two sentences, and everything below follows from reading them exactly.

## What "runs out" means

Running out is something a **deck does**: its last card leaves it. It is not a
state the deck sits in.

That distinction is the whole mechanism, and it is easy to get wrong in either
direction.

**Too late** is rebuilding when somebody *finds* the deck empty — at the next
draw. This is what the engine used to do, and it is indistinguishable from the
right answer in every game where nothing is put into a deck between it emptying
and the next draw. Where something is, the two part company completely; see
below.

**Too early** is rebuilding whenever a deck *is* empty and its discard is not.
That sounds like the same rule and is not: it makes a discard pile into a deck
the moment anything is put in it. A monster killed while the monster deck is
out would be shuffled up and turned straight back over into the slot it just
died from. Nobody at a table does that. This was tried, during the fix, and the
tests that caught it are still in the suite.

So there are exactly two moments a deck comes back, and both are about cards
leaving:

1. **the last card leaves** — whatever took it: a draw, a search, a card that
   moves it somewhere. The deck is rebuilt at once, so the next effect to look
   at it sees a full deck;
2. **somebody needs a card and there is none** — the deck ran out earlier when
   its discard was empty, and the discard has filled since. They shuffle, then
   draw.

Both live in `fsme/effects/builtin/decks.py`: `restock` does the rebuild,
`draw_from` is the drawing that both moments run through, and `take_card` and
`move_cards` restock the deck a card was taken out of.

## What it fixed

Six seeds in a thousand — 113, 137, 167, 251, 300 and 727 — used to produce a
game that never ended. Each ran to roughly 7950 turns before a step budget
stopped it, with a journal of 63 MiB and nearly 290 000 events. Nothing
crashed and nothing looped in the engine's own sense: all 20 000 positions were
distinct, so the stability guard never fired. The game simply made no progress.

Every one of them was the same shape:

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

The loot discard sat at 145 cards throughout and was never shuffled back in.

Not the card's fault. `XIX. The Sun` is implemented completely and correctly:
both effects are present, and the printed condition "if it's your turn" is
there as `player_active` and does apply. An earlier audit note of mine said the
condition was missing; that was wrong, and this document supersedes it.

Under the rule as it now stands, the draw that empties the deck rebuilds it, so
The Sun goes to the bottom of a 145-card deck like any other card:

| seed | before | after |
|---|---|---|
| 113 | 20 000 commands, turn 7975, unfinished | 634 commands, turn 186, finished |
| 137 | 20 000, 7953, unfinished | 766, 184, finished |
| 167 | 20 000, 7946, unfinished | 560, 174, finished |
| 251 | 20 000, 7927, unfinished | 853, 198, finished |
| 300 | 20 000, 7913, unfinished | 849, 195, finished |
| 727 | 20 000, 5631, unfinished | 758, 225, finished |

No turn limit, no loop detection, no special case for The Sun. The deck
mechanic alone ends them, which is the point: forty-eight cards in the loaded
content move cards between deck positions, and every one of them used to meet
the same question.

The same thousand four-player games, re-run afterwards: **1000 of 1000
finished**, no crashes, no invariant violated in any journal entry, the longest
game 327 turns and the median 65.

## All four decks

The loot deck used to be the only one that could be rebuilt — `_refill_loot_deck`
was the only place in the engine that shuffled a discard back — which made a
rule about decks into a fact about one deck. The monster, treasure and room
decks now behave identically, through the same two functions.

This was latent rather than reachable before: across sixty measured games the
monster deck never fell below 228 of ~277 cards, the treasure deck below 259 of
~285, and the room deck below 52 of 67. The loot deck is the only one under
real pressure, because it is drawn every turn. It is fixed anyway, because one
rule implemented once is the thing that went wrong.

## Consequences worth knowing

**Small decks behave oddly, and correctly.** With one room card in the game,
changing the room discards it, finds the deck empty, shuffles the discard, and
turns the same card back up. That is §9 met at its smallest, not a defect —
and it is a test.

**The deal changed.** Rebuilding a deck shuffles it, and a shuffle is the
engine RNG. Moving when the RNG is asked for a shuffle moves every game dealt
after that point. Every number measured before this change is measured on a
different set of games from every number measured after; they are not
comparable. Determinism is unaffected and is asserted: the same seed still
names one game, command for command and fingerprint for fingerprint.

**A deck can still be genuinely empty.** A deck and a discard pile that are
both empty is a legal position. Whoever was drawing does not get a card, and
the effect says so rather than raising.
