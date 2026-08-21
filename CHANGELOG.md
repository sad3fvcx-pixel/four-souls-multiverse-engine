# Changelog

Notable changes, newest first. FSME follows [semantic
versioning](https://semver.org): while the major number is 0, the engine's
internals may change between minor versions. The two things treated as
promises even now are the **journal format** (bumped explicitly, and a journal
that cannot be read says so) and the **card schema**.

## 0.3.0 — author experience

- Added a writable workspace for author-created sets.
- Added the Author UI for creating and editing cards without writing JSON.
- Added capability discovery from the engine's existing registries.
- Added human-readable descriptions for conditions, targets, parameters, and triggers.
- Added target selection for effects that operate on players or items.
- Added in-app card validation and playable card preview.
- Added persistence of author-created sets across application restarts.
- Added an end-to-end authoring workflow and comprehensive Author UI tests.

## Unreleased

## 0.2.0 — author preview

- **A card that is wrong is refused before anybody plays it.** The pipeline
  checked that an effect's name existed and never looked at what the card gave
  it, so `{"effect": "gain_coins", "amount": "lots"}` loaded cleanly and then,
  hundreds of moves into a game, raised `TypeError: '<' not supported between
  instances of 'str' and 'int'` — naming no card, no file and no field. For
  content somebody else wrote, that is the difference between a tool and a
  trap.

  Now:

  ```
  [semantic] example_expansion cards/loot.json: example_expansion-loot-dark_coin:
    ability 0: effects[0].amount: 'gain_coins' takes a whole number of at least
    0 here, and the card gives text ('lots')
  ```

  The descriptions are **derived, never declared**: all 63 effects have fully
  annotated signatures, so what each one takes is read off the function that
  implements it. A second table of effect parameters is a second table that
  drifts; a signature cannot drift from its own function. Domains a type cannot
  express — the four decks, the three positions, the two destinations — are
  named in the `register(...)` call from the same constants the runtime guards
  check against, so there is one list and not two.

  **The seam is intact and that mattered more than the feature.** The content
  pipeline still holds no live effect: what crosses is a plain description of
  names, kinds and domains, built by the one function that knows both sides.
  A caller with no engine still gets structure and spelling and no argument
  checking, exactly as before, and there is a test that says so.

  `Any` on a handler means *the engine cannot judge this without a board* —
  fourteen parameters take a card, a player or a structure. It does not mean
  "accept whatever": the guard inside the effect stays where it is and still
  refuses.

  Also caught now: a parameter the effect does not take, with the nearest one
  it does offered; `true` where a count belongs, since in Python that is 1; an
  explicit `null`; a number below its floor; and a misspelled way of naming a
  value the ability works out while it runs — the executor knows five and hands
  anything else straight to the effect, so `{"frmo": "dice"}` was a dictionary
  arriving where a number was expected.

  Nothing about the card format changed. The whole of `content/` — 1045 cards,
  352 with rules — loads unchanged, and the thousand-game run is identical to
  the one taken before any of this work: 0 of 1000 games moved.
- **A seat can open differently from the others, and experiments can be kept
  in a folder.** The two things the Scenario layer was missing.

  **Per-seat openings.** A scenario asked for the opening hand and cents per
  seat and the engine dealt one opening to the whole table, refusing anything
  else. `PlayerState` carries what that seat is dealt — `None` meaning whatever
  the table deals, which is every seat of an ordinary game — and `start_game`
  reads the seat, then the game, and never the constants. One loop, not two: a
  scenario that gives one player five cents is dealt by the same code that
  gives everybody three, because a second way of dealing an opening is a second
  thing that can be wrong. Nothing touches the RNG, because drawing a card does
  not consume it; shuffling does, and the shuffles are where they were.

  **A scenario library** is a folder of scenario files and a way to ask for one
  by name. The other shape — a directory per scenario with a `metadata.json`
  beside it — was refused: it splits one record into two files that have to
  agree, and the scenario format already carries what the second would hold.
  `scenarios/` in the repository holds two to copy from. A library is a
  convenience and never a dependency: deleting the whole folder does not stop a
  journal replaying, and there is a test that deletes it.

  **Two identifiers, because two questions get asked.** A scenario's `id` names
  the experiment somebody is maintaining; the digest identifies the
  configuration. This turned up a defect in the digest as it shipped last
  week — it was taken over the whole file, so renaming an experiment or dealing
  it from another seed made it look like a different one. It is now taken over
  what reaches the engine: content, table, seats, priority. Renaming leaves it
  alone; changing the setup always moves it. A journal records both and needs
  neither to replay.

  `fsme scenario validate FILE` checks a file and prints its digest before a
  long run spends an hour finding a typo; `fsme scenario list [DIR]` reads a
  folder. Two subcommands, because those are the two things worth doing before
  a run and neither was available any other way.
- **An experiment is reproducible from its journal alone.** A game set up from
  a scenario now records that scenario inside its journal — in full, not by
  reference — with a fingerprint of it, which content it was dealt from, and
  whether the table was offered priority. The file the experiment was written
  in can be deleted, or edited into something else, and the game still replays:
  the test overwrites it with a *different* scenario first, because a replay
  quietly reaching for the file would come back with the wrong answer rather
  than no answer.

  **`JOURNAL_FORMAT_VERSION` is `"2"`, and format 1 still reads.** A version-1
  journal is one from before scenarios existed, which means it has none — a
  true statement about it rather than a missing field — so it loads, replays,
  and says so. A format this build does not know is refused by number, naming
  the ones it reads. Nothing anybody has already recorded is orphaned, and no
  older build can silently misread a newer journal.

  Replay stops guessing. It took the scenario from nowhere and worked out
  interactive priority from whether the journal recorded a deal; it now reads
  both, and the inference survives only as the fallback for format 1.

  The scenario reaches Watch (`Session`), Study (`play_one`, and the worker
  pool as plain data across the process boundary, parsed again on the far
  side), and the analysers. `--scenario FILE` is on `serve`, `play`, `simulate`
  and `study` — the four commands that deal a new game. `show`, `cards`,
  `replay` and `report` do not take it and must not: they work from a journal,
  which already carries it.

  One thing was fixed along the way rather than on purpose. `risks()` — what
  `fsme report` uses — dealt the game itself and then met the journal's own
  `start_game`, so a journal kept by Watch produced nothing at all: `faithful`
  false, nothing weighed. It reads the journal the way replay does now, and the
  same game gives 642 weighed decisions of 652 commands.

  An empty scenario records nothing, because an empty scenario is not an
  experiment: it deals the game FSME deals anyway, so two records of the same
  game would otherwise differ. Verified again that ordinary games did not move:
  the thousand-game run repeated and diffed against the run taken before any of
  this work — 0 of 1000 changed.
- **A game can be set up from a file.** `fsme/scenario/` holds a scenario: the
  configuration a game starts from, as plain data with no behaviour and no
  knowledge of the engine. Which sets are in the decks, which cards are left
  out, who sits where and with what, what the table is worth winning, and the
  opening each player is dealt.

  It arrives as one optional argument on `Game.from_content`, which is the one
  door every game in the project comes through — Watch, Study, Replay and the
  analysers all call it. **With no scenario the engine deals exactly what it
  dealt before there was one**, and that is asserted rather than assumed: three
  seeds compared journal against journal, and the thousand-game run repeated
  and diffed against the run taken before this work — all 1000 games identical
  in outcome, turns, commands and events.

  Two things were load-bearing in the setup change. The character shuffle still
  happens, in the same place, whatever a scenario pinned — the pinned cards are
  lifted out of the shuffled pile afterwards, so the RNG stands where it always
  stood and everything dealt after it follows. And the opening hand and cents
  moved from `rules/constants.py` onto `GameState`: a module constant belongs
  to the *process*, and a study plays a thousand games in one, so a scenario
  that set the constant would have set it for the other nine hundred and
  ninety-nine with nothing saying so. There is a test for exactly that.

  A scenario that is wrong is refused with a sentence per problem and never
  repaired: an unknown key, a version this build cannot read, a card that is
  not in the content, one character in two chairs, seats that disagree about
  the opening, and `monster_slots: 0` — which is refused because it does not
  hold, the first monster revealed making a slot for itself.

  Not yet wired to the command line, and the journal does not record it yet.
  Both are the next step, and until then a scenario is available to anything
  calling the engine directly. `examples/scenario-base-game.json` is one.
- **The Core Stable audit.** No code changed: the engine was measured rather
  than edited, and what it could not do was written down. 2500 games at two,
  three and four players all finished, with no invariant flagged in any journal
  entry. 120 games were checked after every one of their 28 918 commands and no
  card was ever in two places. Determinism holds on all three paths across
  seeds and table sizes; 66 journals of both shapes replay to their recorded
  fingerprints, and replaying them a second time with a keeper attached
  produced the same events field by field. The fundamental rules — phases,
  dice, death and revival, healing, the hand limit, victory, the stack — held
  in every game checked.

  Two things the audit found are limitations rather than defects, and both are
  now documented in `LIMITATIONS.md` and `PROJECT_PLAN.md` §11.5: a card that
  became a soul and is then destroyed leaves the game rather than going to a
  discard pile, because the specifications do not say where it should go; and a
  turn ended by a card or by the death penalty does not enter the end phase, so
  the "at the end of your turn" abilities do not fire. The second is 40% of
  turns and costs about 1.6 abilities a game, almost all of them "recharge
  this".

  `CORE_STABLE.md` gained what the engine promises about turn order and the
  stack, an honest account of the two ways a card can leave the game, and a
  section on what belongs to the next stage. It also records the three ways
  these measurements were got wrong before they were got right, because
  somebody repeating them will meet the same traps.
- **A card could be in two places at once.** The monster area is kept twice:
  `monster_area` is the row of slots and the truth, and `active_monsters` is
  the face-up card of each slot, which is what the rest of the engine reads.
  `rules.slots` is the only code allowed to write both. The effect that moves
  cards between zones did not know that, found the view, took the monster out
  of it and left the slot alone — so the card went into a deck *and* stayed on
  the table, and the next sync put it back into the view too. A buried monster
  was worse: it is in no zone at all, so it was copied into the deck and left
  where it was. Found by tracing instance identity through whole games, in
  five of two hundred, every one of them `Flush!` sweeping the board into the
  monster deck. Fixed in the zone search rather than in the card: a monster now
  leaves through the slots, which also bring back whatever it was covering.
  `Flush!` is unchanged.
- **A monster could be given a difficulty no die could roll.**
  `COMPREHENSIVE_RULES.md` §5: "A roll result and a monster's difficulty are
  never above 6 nor below 1." The roll was bounded and the difficulty was not,
  so +1 on a monster printed at 6 asked for a 7 and made it unbeatable by
  attacking. Three attack rolls in two games of two hundred, against The Beast.
  The bound now lives where the stat is worked out, so everything that asks
  what a monster needs gets the same answer; a monster's attack, which is not
  a roll, is not bounded by the die.
- **The hand limit was counted before the end phase had happened.**
  §3.3 puts "at the end of your turn" effects at step 1 and the discard at step
  3. The engine resolved them in that order but decided *how many* cards were
  over the limit when the phase opened, so a player at ten who was then dealt
  two by an end-of-turn trigger carried twelve into somebody else's turn. Two
  turns in 4318. Asking how many is now its own object, resolving after
  everything ahead of it; the ability that asks *which* is pushed only if the
  answer is more than none. The same object goes on the stack when a card or
  the death penalty ends a turn, which is how nearly two turns in five end and
  where the limit was not applied at all.
- **A deck that ran out was rebuilt too late, and only one deck knew how.**
  `COMPREHENSIVE_RULES.md` §9: "A deck that runs out is rebuilt by shuffling
  its discard pile." The engine read *runs out* as *somebody tried to draw and
  could not*, and implemented it for the loot deck alone. Both halves are
  fixed, by one mechanism used by all four decks. Running out is now what a
  deck does — its last card leaves it, whether to a draw, a search or a card
  that moves it — and the rebuild happens at that moment, so an effect reading
  the deck between two actions sees what the rules say is there.

  This is what ended the six games in a thousand that never finished. Every one
  of them was `XIX. The Sun` — "put this on the bottom of the loot deck; if you
  do, take an extra turn" — played onto a deck that the draw for it had just
  emptied: rebuilt lazily, the deck held exactly that card, the extra turn drew
  it again, and 145 loot cards sat in the discard untouched for 7950 turns. All
  six seeds are named in the tests and now finish in under 900 commands. No
  turn limit, no loop detection and no special case for any card: the deck
  mechanic alone ends them. The same thousand four-player games, re-run: 1000
  of 1000 finished, nothing crashed, and no invariant was violated in any
  journal entry.

  What did *not* change is as deliberate. A discard pile does not become a deck
  the moment something is put in it — an empty deck beside a growing discard is
  an ordinary position, and the alternative shuffles a monster's corpse up and
  turns it straight back over into the slot it died from. Shuffling an empty
  deck and revealing the top of one rebuild nothing, because no card left.

  **Every game dealt is different from before.** A rebuild shuffles, a shuffle
  is the engine RNG, and moving when the RNG is asked moves the deal. Numbers
  measured before this change are not comparable with numbers measured after.
  Determinism is unaffected and is asserted seed by seed, command for command
  and fingerprint for fingerprint. `docs/DECK_EXHAUSTION.md` is the whole
  account.
- **Save journal and `fsme replay` could not be used together.** A file saved
  from Watch failed twice over: the envelope was not understood — "this journal
  is written in format fsme-journal, and this engine reads format 1", the
  envelope's name read as a journal version — and, unwrapped, it was refused at
  entry 0 because replay deals the game itself and a Watch journal already
  records the deal. Reading a journal file now takes either shape, and replay
  deals the game only when the journal does not. It also works out from the
  journal whether the game was played with interactive priority, because the
  journal does not say and the answer changes the game; that inference is
  marked as inference where it is made.
- **A shop slot refilled only if a purchase emptied it.**
  `COMPREHENSIVE_RULES.md` §9: "A slot refills as soon as it is empty." A card
  that took, stole or destroyed a shop item left the hole open for the rest of
  the game — five games in sixty ended with a short shop and a full treasure
  deck behind it. The refill moved to the state-based actions, beside the one
  that fills the monster slots, so every way of emptying a slot is followed by
  the same refill. Two card tests changed with it: Flush and The Capricious
  sweep the shop, and both asserted that the shop stayed swept, which recorded
  the engine rather than the cards.
- **`docs/CORE_STABLE.md`** says what the engine guarantees, what it does not,
  and what it is not trying to do — each guarantee a measurement somebody can
  repeat.
- **A card could delete itself from the game.** O. The Fool says "cancel
  everything that hasn't resolved", and it did — including the engine's own
  bookkeeping for putting the played card into the discard. The card had
  already left the hand, so cancelling only the half that puts it down left it
  in no zone at all: not in the deck, the discard, any hand or on the table.
  Found in a thousand-game audit at seed 113, turn 38, as the only
  `stack_cancel` in twenty thousand commands. A stack object now says whether
  it may be cancelled, and the one that may not is the tail of an action
  already taken — not a rule about any card, and everything a player did or a
  card is doing is still as answerable as it was.
- **Every journal claimed to come from 0.1.0.** The package carried one version
  and the packaging carried another; `JournalKeeper` stamps the package's, so
  the field nobody reads until something is incompatible was the one that was
  wrong. There is one version now, in `fsme.__version__`, and `pyproject.toml`
  reads it rather than repeating it. The old consistency test compared the
  packaging with the command line — both read the same literal, so both agreed
  while the third copy did not; it checks the derivation now.
- **A game watched can be kept.** *Save journal* writes the whole journal of
  the game on screen — the deal, the starting cents, every command, every
  event including the bookkeeping, `controller`, `actor`, the rolls, the
  damage, the deaths and revivals, the rewards, the purchases,
  `winner_declared` and `game_end`. *Load journal* opens one and reads it in
  the same page, with the same step log and the same account, because it is
  the same record drawn by the same code. There is no second format: the file
  is `Journal.to_dict()` inside a named envelope (`fsme-journal`, version 1),
  so what comes back out is what went in — asserted field by field, not by
  eye. Named for the seed, `fsme-journal-seed-4.json`, since the seed is what
  deals the game again.
- **A loaded journal says it is one.** The page has two modes now and shows
  which: reading a saved game hides the board, the moves, the stack and the
  deal controls, because a button that cannot do anything is a claim about
  what is on screen. Nothing is asked of `/api/journal` while a saved game is
  open, and the live game is untouched underneath — *Back to the live game*
  finds it where it was. A file that is not a journal is refused by name:
  unreadable JSON, not ours, a version this build cannot read, no game inside,
  or a saved *report*, which is a different file for a different job.
- **A tagged build no longer needs finishing by hand.** Pushing a tag creates a
  *tag*; it does not create a *release*, and `gh release upload` against a tag
  with none fails with `release not found`. Every tagged build did — v0.1.2 and
  v0.1.3 both built on all three platforms, passed every smoke test, and failed
  on the last step, and both were completed by creating the release by hand and
  re-running the failed jobs. The workflow now creates the release when there is
  none and uses the existing one when there is, leaving its title and notes
  alone. Publishing moved out of the build matrix into a single job that runs
  after every platform has built, because three runners racing to create the
  same release is the next version of the same bug. A last step asks the release
  what it actually has, since a release page with no assets looks exactly like
  one whose build has not finished. `tests/test_release_workflow.py` reads the
  real workflow and fails if an upload step ever again sits in a job that does
  not make sure of the release first.

## 0.1.3 — the bot reads the card, and the watcher reads the game

### Every step

The watch page had an account of the game and a flat list of events. The
account leaves most events out on purpose, and the list said what happened
without saying who did it or when — so neither of them was a record.

- **The full log is now the game's journal**, move by move: every accepted
  command in order, grouped under the turn it was taken in, with the player,
  the phase, the move in the words it was offered in, and every event it
  caused — bookkeeping included. It reads `/api/journal`, which is the same
  file `fsme replay` reads; the page keeps no event list of its own, so the
  account and the log cannot drift into two versions of one game.
- **The account still leads.** The step log is folded away behind *Every step*,
  each turn folds independently, the whole thing scrolls, and *Fold every turn*
  turns a three-hundred-move game into sixteen lines.
- **The journal now begins at the deal.** It was started *after* the game was
  dealt, so the opening hands, the starting cents and the first loot happened
  before anything was writing: a reader looking for where three cents came from
  found nothing. Sixteen events, missing from every browser game FSME has
  played.
- **The bots' moves are in the journal at all.** *Let the bots play* submitted
  straight into the game rather than through the session, so it played past the
  recorder — the mode most likely to be watched was the one mode that left no
  record of itself, and the bot's own words for each move were thrown away.
- **The account of a bot game no longer repeats itself.** Autoplay answered
  every batch with the whole history, so a watcher saw each sentence again for
  every batch that followed it: a game of 281 moves read as 2167 lines instead
  of 126. Found by counting the account against the step log, which is what a
  second reading of one record is for.
- `/api/journal` takes `?since=`, so a long game costs one page one request per
  click rather than the whole game after every click.

### The bot reads the card

`heuristic-1` never bought anything. Not rarely: never, in any game FSME had
ever played. 748 positions across sixty four-handed games where a purchase was
legal, and not one taken.

- **The arithmetic was self-defeating.** A purchase scored
  `ITEM_IS_WORTH + (-TREASURE_COST × COIN_IS_WORTH)` = `5.0 - 10 × 0.6` =
  **-1.0**, which is below ending the turn (0.0) and below passing (-0.1). The
  cause is visible in the constant's own docstring: a cent was "a tenth of an
  item, plus a little for flexibility", and ten cents at a tenth-plus-a-little
  are worth more than the item they buy. The markup was applied to the price
  and not to what the price bought, so every purchase was a loss by
  construction.
- **A card is now read rather than assumed.**
  `src/fsme/lab/bot/appraisal.py` walks the effect data the engine already
  keeps on a definition — `Ability.effects`, `Ability.cost`, `Static` — and
  prices what it recognises in the currency the bot already scores moves in. It
  executes nothing, resolves no targets and evaluates no conditions: it is an
  appraiser, not a second interpreter, and the rules stay in one place.
- **The constant that caused this is gone rather than corrected.** There is no
  `ITEM_IS_WORTH` any more. What a treasure is worth is the average of what
  this game's treasures do, and what a cent is worth is a tenth of that,
  because ten cents buying a treasure is the only exchange the rules print. Both
  fall out of the card pool: change the content and they change with it. The
  point is that nobody can make the bot buy more by nudging a number, because
  the number that would do it is an answer and not an input.
- **Four things are kept apart that used to be one.** The price is asked of the
  rules (`shop_price`, so a card that makes shopping cheaper is noticed, which
  it never was before); the worth of the cents spent is the printed exchange;
  the worth of the card is read off the card; and the worth of the card *here*
  shortens as somebody approaches four souls and rises when the buyer is one
  hit from dying.
- **Three readings that would have been badly wrong.** An ability whose price
  the appraiser cannot read is not valued at all, or a card costing nine
  counters comes out as the best in the game. An ability that destroys its own
  card is worth one use. Damage is capped by the largest health printed in the
  pool, because 999 damage is not 999 damage — read literally it made one board
  wipe worth 8991 points against a soul's 12.
- **Measured, not asserted.** On sixty four-handed games, the same seeds
  before and after: 0 purchases → 92, and the score a purchase gets went from a
  flat -1.0 to a range of -4.31 to +32.88. Of the 58 shop purchases, the 24
  where the card had rules appraised at a mean of 8.66 against a par of 3.12 —
  it buys above average when it can read. **The win rate did not move**
  (0.710 → 0.705 over 200 games, one thinking seat against three random), and
  that is reported rather than buried: 58% of the treasure pool has no rules,
  so most of what there is to buy does nothing in this engine. See
  [LIMITATIONS.md](docs/LIMITATIONS.md).
- Everything else about the bot is unchanged. It still scores a loot card at a
  small constant, because reading loot was not what was broken.

## 0.1.2 — what a watcher could not see

A second pass over the same ground: the engine was working and the person
watching could not tell what was happening.

- **The game is read out in sentences.** `src/fsme/narration.py` turns events
  into English — "Ann attacks Polycephalus." / "Ann rolls a 5 — a hit, 4 was
  needed." / "Polycephalus is defeated — worth 1 soul." / "Ann gains a soul."
  The watch page leads with that account and keeps every event behind *Every
  event*. Most events get no sentence on purpose: a push onto the stack is
  true and is not news, and narrating it would bury the four lines that say
  what the turn was about. A live game and a saved journal share the
  vocabulary, so two accounts of one game cannot drift.
- **Cards say what they do.** 1014 of 1045 cards carry their printed text and
  the API was already sending it; nothing displayed it. Now a card on the
  table opens its text on a click, the card test shows what it is about to
  measure, and `fsme cards "The Bone"` explains a name seen in a report —
  reports name cards and cannot carry their rules, so that is where a name
  gets explained.
- **A seed nobody has to invent.** *Random seed* and *Copy* beside the seed
  box. Reproducibility is the point of a seed and it was being asked for like
  a password.
- **The bots can play the game you are watching.** *Let the bots play* runs
  the table a few moves at a time so it redraws as it goes. The button asks
  the server whether it exists first: the core game server has never heard of
  the bot, and only the desk answers. This is the watch-mode counterpart of
  the headless bot-vs-bot added in 0.1.1.

## 0.1.1 — what the first user found

Four things, all reported by somebody using 0.1.0 for the first time. No new
analysis; the point of this release is that the path works.

- **Players started with no money.** `COMPREHENSIVE_RULES.md` §2 says each
  player is dealt 3 loot cards and 3¢. The loot was dealt from the first
  version of setup and the cents were not, so every game FSME had ever played
  began three cents short. It is a small number and not a small change: the
  first purchase moves later in every game, and every statistic measured from
  those games moves with it. Every example and the demonstration are
  regenerated, and one of the two deals that used to reach the card-copying
  loop now settles — the seeds were examples of that defect, never a
  definition of it.
- **The card picker showed identifiers instead of names.** It was a
  `<datalist>`, and a datalist displays the value it submits, which was the
  identifier. The name was never broken; it was never shown. It is now a
  select, grouped by set — a name alone cannot identify a card, since twelve
  of them are called "Pills!" — and cards the engine has no rules for are
  marked, because testing one can only ever come back "no effect".
- **A report could not be saved.** `Save report` and `Load report` now write
  and read a file that carries **the game**, not the text. Every analyser in
  the project reads games, so a report nobody can re-ask a question of is a
  dead end; loading re-runs the analysers, which means a file saved today
  gets tomorrow's improvements to them. The format is versioned and a file
  from a newer FSME says so.
- **Only one seat could be given to the bot.** `Play a game` now offers every
  seat by the bot, seat 0 only, or none. The detailed decision log exists for
  seats a bot played, so a table of one bot and three coin-flippers made a log
  that was three quarters noise.

## 0.1.0 — first release candidate

The first version meant to be handed to somebody else. Everything below already
worked; what changed for this release is that a stranger can now reach it.

### What FSME does

- **Plays Four Souls deterministically.** A seed and a list of commands
  reproduce a game exactly. 352 of 1045 known cards have working rules, each
  written from its printed text with a test of its own.
- **Writes down what happened.** A journal holds every position, everything the
  engine would have accepted at that moment, what was chosen, and every event
  that followed — and can be replayed to prove it still holds.
- **Answers questions about it.** `fsme report` gives one game's turning
  points, the decisions it turned on and which cards did the work; `fsme study`
  asks what a run of games has in common; `fsme test-card` plays the same seeds
  with a card and without it.
- **Runs from a browser.** `fsme desk` puts all of it behind buttons, running
  the same functions the commands run.
- **Ships as one file.** A PyInstaller build carries the cards and both pages
  inside itself and needs nothing installed.

### Added for this release

- `fsme demo` — a twenty-second tour, no arguments: a game, its record checked,
  a full report, sixty more games studied, and a card measured. Every step
  prints the command that made it.
- `examples/` — the real output of each of those steps, one file each, so the
  project can be judged without installing it. Generated, not written by hand.
- `docs/GETTING_STARTED.md`, `docs/LIMITATIONS.md`, `docs/NEXT.md` — what to
  do, what this cannot do, and where it might go.
- Issue templates and `CONTRIBUTING.md`.
- Grouped `--help`, with a starting point rather than twelve commands in the
  order they were written.
- "Did you mean" for mistyped commands, effects, triggers, conditions and
  targets.

### Fixed for this release

Found by installing into an empty environment and typing what a newcomer would
type — every one of these worked perfectly on the machine it was written on.

- **The cards were not in the wheel.** A clean `pip install` produced an `fsme`
  that could print its version and nothing else. The build now copies
  `content/` into the package.
- **The desk page and the laboratory were missing from the wheel and the
  frozen build**, so `fsme` with no arguments — the double-click path — served
  a 500 either way.
- **`packaging/fsme.spec` was not in the repository.** `.gitignore` carries
  `*.spec` from the standard Python template; it swallowed the only description
  of how to build the executable, so a clone could not build one.
- **The Target expansion was not in the repository.** The same `.gitignore`
  carries `target/` for Java and Rust build directories, and it swallowed three
  cards. A test now fails if anything under `content/`, `spec/`, `docs/`,
  `examples/` or `packaging/` stops being tracked.
- **The release workflow was falsely green.** It smoke-tested the built
  executable from inside the checkout, where `content/` sits — so a build
  carrying no cards passed the check that it could find its cards.
- **Error bars on the card test were about seven times too narrow.** `_mean`
  assumed a per-game count's variance equalled its mean, as a Poisson count's
  does; game lengths run 40 to 250 around an average of 120. The tool was
  announcing effects that were not there — a 40-game run claimed "+6.58 turns"
  where 200 games claimed "−2.95", both marked significant. Spread is now
  measured from the games played, and both of those were artefacts.
- **`transfer_coins` raised when there was nobody to steal from** — "steal 1¢
  from another player" in a two-player game whose other player is dead. It now
  passes over, as the other effects do.
- **A game that would not settle said only that it had given up.** It now names
  what kept happening, which is how Placebo and Rainbow Tapeworm copying each
  other for ever was identified.
- **Forking a worker from a thread.** The desk starts runs from a background
  thread, and forking a multi-threaded process can deadlock the child. The
  start method is now chosen at the fork by whether other threads exist —
  keeping plain `fork` for the ordinary single-threaded case, which a REPL and
  a notebook need.
- **`freeze_support()`** in the entry point, so a frozen build on Windows does
  not launch a copy of itself per worker. Verified: the Windows executable is
  built by CI and made to run `fsme study --jobs 2` from a directory with no
  card data in it.
- **A set directory outside four known names was silently ignored.** A
  directory with a manifest is now a set wherever it sits.
- **Content errors arrived as tracebacks.** They now arrive as the validator's
  own report, with a suggestion.
- Missing files, malformed journals and a port already in use are explained
  instead of raised.
- **`fsme demo` crashed on Windows on its own first line.** Windows gives a
  Python process a cp1252 console and cp1252 cannot encode a box-drawing rule,
  so the first thing a newcomer is told to run died with a
  `UnicodeEncodeError` from inside `print`. The console is now put into UTF-8,
  with fallbacks, and a test reproduces the failure anywhere by wrapping stdout
  in a cp1252 writer. Found by CI, which had been failing on every push while
  the local suite was green — the more useful lesson of the two.

- **A tag would not have built anything.** The workflow listened for `v*` and
  the release was cut as `0.1.0`, so no build ran and the release was
  published with no binaries on it — invisible, because a release page with no
  assets looks the same as one whose build has not finished. Any tag now
  builds, and the binaries are attached to the release itself rather than left
  as Actions artifacts, which expire and need a GitHub login to download.

### Known limitations

Two thirds of the card content has no behaviour yet; some pairs of cards can
copy each other without end and the engine stops rather than inventing a rule;
the card test compares two populations rather than two versions of one game;
and every statistic is conditional on a bot that thinks one move ahead. These
and the rest are in [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

### Before this

Development history is in the commit log and in
[docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md), which records what was built,
what it cost, and — in §11.5 — every place the engine knowingly departs from
the published rules, with the reason.
