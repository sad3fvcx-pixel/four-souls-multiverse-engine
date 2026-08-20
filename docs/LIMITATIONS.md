# What FSME cannot do

Collected in one place so that nobody has to discover them one at a time, and
so that a number this project prints can be trusted exactly as far as it should
be.

Everything here is a known limit, not a bug to report. Anything *not* here that
surprises you is worth [an issue](../.github/ISSUE_TEMPLATE/bug_report.yml).

---

## The content is incomplete

**352 of 1045 known cards have working rules.** `fsme cards` prints the current
count per set.

The rest are card data with a name, a type and printed text, and no behaviour.
A game may deal one and do nothing with it. This matters for every measurement:
a study of the whole content is a study of a game in which two thirds of the
deck is inert.

Cards are implemented from their printed text, one at a time, with a test each.
Nothing is guessed: a card whose rules the specifications do not settle is
recorded as a gap in `PROJECT_PLAN.md` §11.5 rather than invented.

## A turn ended by a card skips its end-of-turn triggers

`COMPREHENSIVE_RULES.md` §3.3 step 1 says an effect that ends a turn jumps
straight into the end phase, so the "at the end of your turn" effects still
fire. In the engine a turn ended by a card — or by the death penalty, whose
last clause ends the active player's turn — goes straight to passing the seat.
Healing, the expiry of "till end of turn" bonuses and the discard down to ten
all happen; the triggers do not, and neither does the offer to change rooms.

Not rare: 1615 of 4325 measured turns end this way rather than by the active
player saying so.

## Some pairs of cards never finish

Placebo copies an item's ability; Rainbow Tapeworm becomes a copy of an item.
Together they can copy one another without end. The engine stops after 512
steps and names what kept happening:

```
StabilityError: game state did not stabilise within 512 steps. Still arriving
when it gave up: stack_push(Placebo) ×10, stack_resolve(Rainbow Tapeworm) ×10
```

The official rules say nothing about infinite loops, so no rule was invented to
break them. In a run of hundreds of games this shows up as an abandoned game,
counted and reported by seed rather than silently dropped.

See `examples/a-problem-found.txt` for the whole thing.

## The card test compares two populations, not two versions of one game

This is the largest limit on the tool most people will come for.

Removing a card from the deck reshuffles **every game that deck deals**. So the
run with the card and the run without it differ everywhere, not only where the
card is. FSME reports this rather than working around it:

- a card that reached the table in fewer than one game in ten gets nothing
  marked at all, and the verdict is *too scarce to say*;
- every difference is printed with the uncertainty it sits inside, measured
  from the games actually played;
- "no effect this run could see" is never shortened to "no effect".

Paired seeds — dealing the same game with and without the card — would fix
this. It is the one item in [NEXT.md](NEXT.md) that needs no external signal.

## Every number comes from a table of bots

There are two players in FSME: one that chooses uniformly among legal moves,
and `heuristic-1`, which looks one move ahead and knows souls win, dying is
expensive, a die has six faces, and — since 0.1.3 — what the card in front of
it says it does.

Consequences worth holding on to:

- **statistics are conditional on the player.** "Coins gained went with
  winning" may be a fact about Four Souls or a fact about how this bot prices a
  cent;
- **the bot is weak on purpose.** It is built to be readable, so its mistakes
  can be found. When a report says "the bot would have played X", that is a
  disagreement with a stated opinion, not a verdict;
- **nothing here has met a human decision.** No game analysed by FSME was ever
  played by a person.

## The bot can read less than half of what it can buy

`heuristic-1` prices a treasure by reading the effect data on its definition.
That reading is bounded twice over, and both bounds are worth knowing before
believing anything it says about shopping.

**Most treasures have no rules to read.** 166 of the 287 treasures in the
loaded content carry no abilities and no statics, so 58% of the shop is inert
in this engine — buying one costs ten cents and changes nothing. The appraiser
scores those at what an average treasure is worth rather than at zero, which
is deliberate: pricing them at nothing would make the bot prefer the cards FSME
happens to have implemented, which is a preference about FSME and not about
Four Souls. The cost of that choice is that the bot pays a fair price for cards
that do nothing here, and it is why buying does not yet show up as a win-rate
improvement. Scoring them at zero is a one-line change in
`src/fsme/lab/bot/appraisal.py`; it would make the bot stronger at FSME-as-built
and less honest about the game.

**Of the treasures that do have rules, most do something unpriceable.** The
appraiser puts a number only on effects whose worth follows from an anchor it
already has — cents, cards in hand, hit points, souls, items. A reroll, a card
moved to the top of a deck, a monster discarded, an extra attack per turn: it
records those as unread and scores them at nothing, rather than inventing a
number that would be indistinguishable from a measured one. The median readable
treasure therefore appraises at exactly 0. What it did not understand is
carried on every appraisal, so a purchase that went badly can be checked for
whether the bot was wrong or merely blind.

## Correlation is reported as correlation

Winners are compared with everybody else, and everything separating them is as
much symptom as cause: a player who killed four monsters won partly because of
it and killed the fourth partly because they were already winning. The reports
say "went with winning", never "caused".

The pairs table is worse and says so: with hundreds of cards there are tens of
thousands of pairs, so the top of any such table is striking by arithmetic
alone. Every row is offered as a hypothesis for `fsme test-card`.

## The turning points are not counterfactuals

`fsme report` names the moves that moved the scoreboard furthest towards the
result. It does **not** say the game would have gone differently had they gone
otherwise — no other line of play is tried. Where a swing followed a die, the
die is named along with the chance it had.

## It is not a way to play with people

The browser page is one local game for one person looking at it. No accounts,
no network play, no matchmaking, no mobile client. FSME deals games so that it
can measure them.

## Practical limits

| | |
|---|---|
| Players per game | 1 to 4 |
| Python | 3.12 or newer |
| Journal size | roughly 120 KB a game, or 1.7 MB with `--offers` |
| A game | about 0.2 seconds |
| Windows executable | built, smoke-tested and attached to the release by CI on every tag; not run by hand by the author |
| Rooms (Requiem) | the slot is implemented; the 68 room cards are not |

## Not official

No affiliation with Studio71, Edmund McMillen, or anyone who publishes Four
Souls. Card text is transcribed from published cards for use with a copy of the
game you own.
