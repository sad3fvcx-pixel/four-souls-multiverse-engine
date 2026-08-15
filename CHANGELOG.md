# Changelog

Notable changes, newest first. FSME follows [semantic
versioning](https://semver.org): while the major number is 0, the engine's
internals may change between minor versions. The two things treated as
promises even now are the **journal format** (bumped explicitly, and a journal
that cannot be read says so) and the **card schema**.

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
