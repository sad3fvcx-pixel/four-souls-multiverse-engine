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

Measured: repeated runs of one seed on each of three paths — the simulation
path a study uses, the Session path Watch uses, and replay — with whole
journals compared field by field, not just winners and lengths. Identical every
time, including the chain of position fingerprints. Repeated across seeds and
across two, three and four players, and across one worker against four:
dividing the work does not change any answer.

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

Measured on both shapes: 60 simulation games at two and four players and six
Watch games at four — 33 787 commands — every one faithful to its recorded
fingerprints. And more than the fingerprints: each journal was replayed a
second time with a keeper attached and the two journals compared event by
event, every field of every event, not only the digest.

### An experiment is reproducible from its journal alone

A game set up from a scenario records that scenario **inside** its journal —
in full, not by reference — along with a fingerprint of it, which content it
was dealt from, and whether the table was offered priority.

So the file the experiment was written in can be deleted, or edited into
something else, and the game still replays. Measured that way rather than
described: the scenario is written to a file, the game is set up from what was
read back, the journal is saved, the file is overwritten with a *different*
scenario, and the journal replays faithfully from itself. A replay that
quietly reached for the file would come back with the wrong answer rather than
no answer, which is why the test replaces the file instead of deleting it.

Two experiments on one seed are two games and fingerprint differently; one
experiment on one seed is one game, compared journal against journal.

**Scenario is not Save, and the difference is worth holding on to.**

| | what it is | what it is for |
|---|---|---|
| **Scenario** | the configuration a game starts from — which sets are in the decks, who sits where, what each seat opens with, what the table is worth winning | setting up an experiment, before any game exists |
| **Save** | a position: every card in every zone, whose turn it is, what is on the stack, where the generator stands | continuing one game from the middle |
| **Journal** | the history of one particular game: every command, every event, a fingerprint after each, and the scenario it was set up from | reading a game, replaying it, counting across thousands |

Every request to add "one more thing the game starts with" to a scenario is a
request to reinvent the save format inside it.

**The lifecycle.**

```
scenario.json          written by hand, or taken from a folder of them
      │                `fsme scenario validate` checks it before a long run
      ▼
Game.from_content(scenario=)     Watch · Study · one game
      │
      ▼
journal.json           carries the scenario in full, its fingerprint, the
      │                content it was dealt from, and how it was played
      ▼
replay · report        from the journal alone; the scenario file, and the
                       whole folder it came from, may be gone
```

**Two identifiers, because two questions get asked.** A scenario's `id` names
the experiment somebody is maintaining and survives being edited — renaming a
study does not make it a different study. Its digest identifies the
configuration and is taken over what reaches the engine, so renaming or
reseeding leaves it alone and changing the setup always moves it. A journal
records both, and needs neither to replay.

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

Two journal formats are readable: format 2, which carries the scenario a game
was set up from, and format 1, which predates scenarios and therefore has none
— a true statement about such a journal rather than a missing field. A format
this build does not know is refused by number, saying which ones it reads.

Two file shapes are both readable: the journal written bare, and the journal
inside an `fsme-journal` envelope. A file that is not one of ours is refused by
name — unreadable JSON, not ours, a version this build cannot read, no game
inside, or a saved *report* handed to the wrong loader.

### It does not fall over

**2500 games finished out of 2500**, at two, three and four players: no
crashes, no exceptions, no recursion limits, no game abandoned. The longest ran
327 turns at four players, 249 at three, 163 at two; the medians are 66, 57 and
42. Before the deck-exhaustion fix, six games in a thousand ran for ever.

Checked in every journal entry of all 2500 games, not only at the end:

- no negative health, coins or souls;
- exactly one `winner_declared` and one `game_end` per finished game;
- never two winners;
- the winner holds the souls the win requires.

### A finished game is finished

After `game_end` the engine accepts nothing: no legal moves are offered, and a
command submitted anyway is refused with "the game is over". Measured over the
thousand-game run and asserted directly.

### A deck that runs out is rebuilt

`COMPREHENSIVE_RULES.md` §9, for all four decks and by one mechanism: when the
last card leaves a deck it is rebuilt at once by shuffling its discard pile, so
an effect that looks at the deck between two actions sees what the rules say is
there rather than a deck that is briefly empty.

Running out is treated as something a deck *does* — its last card leaves —
rather than a state it sits in, which is what keeps a discard pile from turning
into a deck the moment anything is put in it. Asserted on all four decks: the
rebuild as the last card leaves, the rebuild when a draw finds a deck that ran
out earlier, a card put on the bottom of a deck it has just emptied, a search
that takes the last card, a card moved into its own deck's discard, and the
things that must *not* rebuild — a shuffle, a reveal, a card discarded beside a
deck that was already empty.

This is what ended the six games in a thousand that used to run for ever. No
turn limit, no loop detection and no special case for any card was added; the
six seeds are named in the tests and finish on the mechanic alone. See
[DECK_EXHAUSTION.md](DECK_EXHAUSTION.md).

### The economy balances

Coins started with, plus every coin gained, minus every coin lost, equals the
coins held at the end — **per seat**, not merely in total. No drift in any game
measured. Money does not appear or vanish without an event that says so.

### Death, penalty, revival

The sequence died → penalty → revived is never out of order, and nobody acts
while dead. A revival without a death is impossible by construction: the effect
skips a living player. A player dies at most once per turn (§10), and health
returns at the end of the *next* end phase — so somebody who died in the turn
the game ended on is still down, correctly, in the final position.

Measured over 120 games at two to four players: 2898 deaths, 2891 revivals, no
penalty paid without a death and no revival without one.

### A card is in exactly one place

A deck, a discard, a hand, a shop slot, the room slot, a monster slot, or
somebody's play area. Traced by instance identity after every command of whole
games, across all four decks and every card type — identified, not counted.
`active_monsters` is not a place: it is the face-up view of the slot row, and
counting it as one is how a census can be made to agree with anything.

Measured: 120 games at two, three and four players, 28 918 commands, **no card
in two places at any point of any of them**. Plus two hundred four-player games
checked for the same thing.

This claim was false until the Core Stable audit. The earlier census followed
loot cards only, so monsters were never traced, and `Flush!` — which sweeps the
board into the monster deck — put them there while leaving them standing in
their slots.

**Cards that leave the game.** Two, both known and both rare, and neither is
bookkeeping losing a card:

- a card that became a soul and is then *destroyed* — `XX. Judgement` — leaves
  the game instead of going to the discard pile of its own deck. Where a
  destroyed soul card should go is not written in the specifications, so
  nothing was invented; five cases in 120 games;
- a loot card played in the very command that ends the game never reaches the
  discard, because the object that would put it there is dropped with the rest
  when the game is over. One case in 120 games, in the final position only.

Both are in [LIMITATIONS.md](LIMITATIONS.md) and `PROJECT_PLAN.md` §11.5.

### The stack resolves in causal order

The deepest chain the current content reaches is 159 events in one command, and
the order holds throughout: a push before its resolution, `before_damage` before
`damage_dealt` before `after_damage`, a kill before its reward before the soul.

Nothing resolves that was never pushed, and nothing resolves twice: checked on
69 481 pushes across 120 games. A lethal effect is the one damage that opens no
window before it — §8 counts it as a death rather than as damage — and it says
`lethal` in the event, so the two can be told apart.

State-based actions run between steps: deaths settle, monster and shop slots
refill, decks that ran out are rebuilt, and a win is noticed as soon as it is
true.

### The turn runs in order

Start, loot, action, end, and never backwards; a roll is 1 to 6 and a monster's
difficulty is 1 to 6 (§5), so no monster can ask for more than a die can give;
everyone and every monster is at full health when the next turn opens (§3.3);
the player whose turn ended is holding ten cards or fewer; the winner holds the
souls the win requires (§11); an allowance never goes negative.

Measured over 120 games at two to four players: 11 574 rolls, 15 178 phase
changes, and every clause above held in all of them.

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

### Two shapes of journal

A game played through a `Session` records the deal as its first command. A
simulation's journal begins at the first move, because its keeper starts after
the cards are dealt. Both are complete records of what they cover, and both
replay, but they are not directly comparable: the simulation journal is missing
the opening hands, the starting cents, and anything that happens during setup.

This has already misled one audit — a monster that killed a player during the
deal produced a journal with a revival and no death in it. Unifying the two is
on the list; it is deferred because it moves every number ever measured.

### A journal from before format 2 does not say how it was played

Interactive priority changes the game. Journals of format 2 record it and are
believed; a format-1 journal predates the field, and replay works it out from
what the journal contains — a game that records the deal, or that contains a
pass, was interactive. That inference is marked as inference in the code, and
it is now the fallback rather than the rule.

### Most cards do nothing

Of 287 treasures in the loaded content, 166 carry no rules the engine can read:
buying one costs ten cents and changes nothing. The proportion is similar
elsewhere. This is the largest single gap between FSME and Four Souls, and it is
a content gap rather than an engine one — see
[OFFICIAL_CARD_COVERAGE.md](OFFICIAL_CARD_COVERAGE.md).

### A turn ended by a card does not enter the end phase

§3.3 step 1 says an effect that ends a turn jumps straight into the end phase,
so the "at the end of your turn" abilities still fire. The engine puts the
turn-advancing object on the stack instead: healing, revival, the expiry of
"till end of turn" bonuses and the discard down to ten all happen, and the
`turn_end` triggers do not.

40% of turns end this way. The cost is much smaller than that: about 1.6
abilities a game fail to fire at four players, nearly all of them "recharge
this", and no room change was missed in any measured game.

A gap in how completely the rules are simulated, not a hole in the state:
nothing is lost or left inconsistent, and such a game replays like any other.

### Some events are emitted after the game ends

A stack push announced in the same command that declared a winner, immediately
discarded. Cosmetic: nothing is accepted afterwards.

### The stack log cannot say what was pushed

`stack_push` and `stack_resolve` carry the source card and the controller, but
not the object's label, so a push with no card behind it — settling a roll,
advancing a turn — reads as the player's name and nothing else. The engine knows
the label; the event does not carry it. `stack_cancel` is the other way round:
it names the label and not the id, so a cancelled object cannot be matched to
the push that put it there.

### A card that becomes a soul and is then destroyed leaves the game

Where a destroyed soul *card* goes is not written in the specifications, so
nothing was invented. Five cases in 120 games, always `Lost Soul`. See
[LIMITATIONS.md](LIMITATIONS.md).

---

## The next stage

Not promises, and not scheduled — the shape of what is left, so that "Core
Stable" is not read as "finished".

**Rules completeness.** The turn ended by an effect should enter the end phase.
A destroyed soul card should have somewhere to go. Both are written up in
`PROJECT_PLAN.md` §11.5 with what blocks them; neither is a hole in the state.

**Content.** 352 of 1045 known cards have working rules, and 166 of 287
treasures carry none the engine can read. This is the largest gap between FSME
and Four Souls and it is a content gap, not an engine one — see
[OFFICIAL_CARD_COVERAGE.md](OFFICIAL_CARD_COVERAGE.md).

**One shape of journal.** A Session records the deal and a simulation does not.
Both are complete records of what they cover and both replay, but they are not
directly comparable, and unifying them moves every number ever measured.

**Custom cards.** They already load and play — a folder with a manifest and
card files is an expansion, and a scenario can name it — but nothing tells
anybody that, and two people's `my_set` collide. Naming is the design decision,
and it gets much more expensive after people have made sets.

Everything else that has been considered is in [NEXT.md](NEXT.md), which is a
list of directions rather than a plan.

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

Everything above is a test or a measurement. `pytest` runs the tests — 1015 of
them; the measurements are in the commit messages and the audit notes, with the
seeds they were taken from.

The claims that would be worth doubting first are the ones about *many* games.
They were measured on 2500 games for finishing and on 120 for the checks that
look at every command, at two to four players, with one bot. A different table,
a different content set, or many more games could show something these did not.

The measurements themselves have been wrong here before, in ways worth knowing
about if you repeat them. Events are queued when they are emitted and delivered
when the queue drains, so reading the state after a command has finished is
reading it several things later — that produced three false findings in one
pass of this audit. `active_monsters` looks like a zone and is a view, so
counting it doubles every standing monster. And `replay_journal` reports a
divergence as a return value rather than an exception, so catching exceptions
proves nothing about fingerprints.
