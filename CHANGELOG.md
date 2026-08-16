# Changelog

Notable changes, newest first. FSME follows [semantic
versioning](https://semver.org): while the major number is 0, the engine's
internals may change between minor versions. The two things treated as
promises even now are the **journal format** (bumped explicitly, and a journal
that cannot be read says so) and the **card schema**.

## Unreleased

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
  repeat. **`docs/DECK_EXHAUSTION.md`** is the whole account of the six games
  in a thousand that never finish: the cause, the sentence of the rules it
  turns on, and the three things that could be done, with none of them done.
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
