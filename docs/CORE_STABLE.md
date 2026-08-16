# FSME Core Stable

What the engine promises, what it does not, and what it is not trying to do.

This is written for somebody deciding whether to build on FSME. It is not a
feature list: everything below is either measured or refused, and where a
number appears it came from a run somebody can repeat.

The engine is the part that plays Four Souls: rules, cards, effects, events,
state, stack, runtime, journal. The laboratory — bots, simulation, analysis,
the desk — is built on it and is not covered by these promises.

---

## Guaranteed

### Determinism

The same seed, the same players and the same commands produce the same game,
command for command and die for die.

Measured: ten runs of one seed on each of three paths — the simulation path a
study uses, the Session path Watch uses, and replay — with whole journals
compared field by field, not just winners and lengths. Identical every time,
including the chain of position fingerprints. Repeated across five seeds and
two to four players, and across one worker against four: dividing the work
does not change any answer.

A seed names one game **per path**. Interactive priority makes rolls
answerable, so a game watched and a game simulated from the same seed are
different games. Both are deterministic; they are not each other.

### Replay

A journal replays through the ordinary engine — there is no replay path, and a
shortcut would only prove the shortcut works. Every command is submitted the
way it was first submitted, and the position after each is compared with the
fingerprint recorded at the time. A replay that diverges stops at the command
that diverged and says which.

Both shapes of journal replay: one that records the deal (Watch, Save journal)
and one that begins at the first move (simulation).

### The journal

Every accepted command, in order, with the position it was made from, every
event it caused including the bookkeeping, who each event was about, and a
fingerprint of the position afterwards. Nothing is computed or inferred; it is
what the engine produced, kept instead of discarded.

Read by everything that reads games: the step log, the account, the analysers,
replay. One record, several readings.

### Save and load

A journal written to a file and read back is the same journal — asserted on the
serialised data field by field, not on anything rendered from it: order of
events, indexes, `controller`, `actor`, `source`, `targets`, payloads, seed,
players, format. Verified on games from 35 to 978 commands, including ones with
purchases, deaths, revivals and 11876 events.

Two file shapes are both readable: the journal written bare, and the journal
inside an `fsme-journal` envelope. A file that is not one of ours is refused by
name — unreadable JSON, not ours, a version this build cannot read, no game
inside, or a saved *report* handed to the wrong loader.

### It does not fall over

A thousand four-player games: no crashes, no exceptions, no recursion limits.
994 finished; the six that did not are one known defect, described below.

Checked in every journal entry of all thousand games, not only at the end:

- no negative health, coins or souls;
- exactly one `winner_declared` and one `game_end` per finished game;
- never two winners;
- the winner holds the souls the win requires.

### A finished game is finished

After `game_end` the engine accepts nothing: no legal moves are offered, and a
command submitted anyway is refused with "the game is over". Measured over the
thousand-game run and asserted directly.

### The economy balances

Coins started with, plus every coin gained, minus every coin lost, equals the
coins held at the end — **per seat**, not merely in total. No drift in any game
measured. Money does not appear or vanish without an event that says so.

### Death, penalty, revival

The sequence died → penalty → revived is never out of order, and nobody acts
while dead. A revival without a death is impossible by construction: the effect
skips a living player.

### Cards are conserved

A card is somewhere: a deck, a discard, a hand, in play, or attached. Traced by
instance identity through whole games. The only cards that leave are the ones
whose own text says they leave — Lost Soul becomes a soul, and stops being a
loot card.

### The stack resolves in causal order

The deepest chain the current content reaches is 159 events in one command, and
the order holds throughout: a push before its resolution, `before_damage` before
`damage_dealt` before `after_damage`, a kill before its reward before the soul.

State-based actions run between steps: deaths settle, monster and shop slots
refill, and a win is noticed as soon as it is true.

### Content is checked, not trusted

A card file that the engine cannot read is refused with a reason naming the
card and the problem. The card schema is versioned; so is the journal format;
so is the journal file envelope. Each says so when it cannot read something.

### The core does not depend on the laboratory

Enforced by reading the imports, not promised in prose: no module of the engine
imports `fsme.lab`. Only the command line sees both. A report can never become
part of the rules.

---

## Known limitations

### A game can fail to finish

Six games in a thousand run for ever. All six are the same shape, and it is
understood: see [DECK_EXHAUSTION.md](DECK_EXHAUSTION.md).

Short version: the loot deck is rebuilt from its discard *lazily* — when a draw
finds the deck empty. A card that puts itself on the bottom of an empty deck is
therefore always the only card in it, and is drawn again next turn. With
`XIX. The Sun`, which also grants an extra turn, that repeats without end.

Until this is decided, a run over many games needs a step budget. `fsme study`
has one; anything else calling the engine in a loop should have one too.

### One deck of four is rebuilt

`COMPREHENSIVE_RULES.md` §9 says a deck that runs out is rebuilt by shuffling
its discard pile. The engine does this for the loot deck. The monster, treasure
and room decks are not rebuilt: when they run out, they stay out.

Latent rather than reachable — over sixty measured games the monster deck never
fell below 228 of ~277, the treasure deck below 259 of ~285, the room deck below
52 of 67. The loot deck is the only one under real pressure. Recorded because
the rule is one rule and it is implemented once.

### Two shapes of journal

A game played through a `Session` records the deal as its first command. A
simulation's journal begins at the first move, because its keeper starts after
the cards are dealt. Both are complete records of what they cover, and both
replay, but they are not directly comparable: the simulation journal is missing
the opening hands, the starting cents, and anything that happens during setup.

This has already misled one audit — a monster that killed a player during the
deal produced a journal with a revival and no death in it. Unifying the two is
on the list; it is deferred because it moves every number ever measured.

### The journal does not record how the game was played

Interactive priority changes the game, and the journal does not say whether it
was on. Replay works it out from what the journal contains — a game that
records the deal, or that contains a pass, was interactive — which is inference
and is marked as inference in the code. A journal produced some third way could
be replayed under the wrong assumption.

### Most cards do nothing

Of 287 treasures in the loaded content, 166 carry no rules the engine can read:
buying one costs ten cents and changes nothing. The proportion is similar
elsewhere. This is the largest single gap between FSME and Four Souls, and it is
a content gap rather than an engine one — see
[OFFICIAL_CARD_COVERAGE.md](OFFICIAL_CARD_COVERAGE.md).

### Some events are emitted after the game ends

A stack push announced in the same command that declared a winner, immediately
discarded. Cosmetic: nothing is accepted afterwards.

### The stack log cannot say what was pushed

`stack_push` and `stack_resolve` carry the source card and the controller, but
not the object's label, so a push with no card behind it — settling a roll,
advancing a turn — reads as the player's name and nothing else. The engine knows
the label; the event does not carry it.

---

## Not a goal

These are not defects and are not on any list to fix before the engine is
considered stable.

**Balance.** FSME does not know whether a card is good. It reports what happened
and says how sure it is.

**A strong AI.** `heuristic-1` looks one move ahead and shows its working. It is
built to be *readable*, so that its mistakes can be found — not to play well.
When a report says "the bot would have played X", that is a disagreement with a
stated opinion, not a verdict.

**A polished interface.** The pages that exist are for watching a game and
running the tools. They are not the product.

**Every card implemented.** Cards are data and arrive one at a time. Nothing
about the engine waits on them.

**Playing with other people.** No network, no lobbies, no accounts. FSME plays
games and writes down what happened.

**Being official.** FSME is not affiliated with the publisher. Card text belongs
to its owners; the engine is an independent implementation of published rules.

---

## How to check any of this

Everything above is a test or a measurement. `pytest` runs the tests; the
measurements are in the commit messages and the audit notes, with the seeds
they were taken from.

The claims that would be worth doubting first are the ones about *many* games,
because they were measured on a thousand games at four players and one bot.
A different table, a different content set, or many more games could show
something these did not.
