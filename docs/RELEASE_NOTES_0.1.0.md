# FSME 0.1.0

**A rules engine, a journal of every game, and a laboratory for asking
questions about both.**

---

## What this is

FSME plays *The Binding of Isaac: Four Souls* — properly, from real card data,
with the stack and priority and state-based actions that the printed rules
describe. Then it writes down everything that happened, and answers questions
about it.

That second half is the point. There are ways to play Four Souls online. There
is no way to play it *four hundred times* and be told which moves decided the
games, which cards did the work, and whether the card you just wrote actually
changes anything. That is what this is for.

It is a tool for the people who **make** Four Souls content, not a way to play
with your friends.

## Try it in twenty seconds

```bash
pip install .        # Python 3.12 or newer, no dependencies
fsme demo
```

`fsme demo` needs no arguments. It plays a game, proves the record of that game
is reproducible, reports on it, plays sixty more and says what they have in
common, then measures one card by playing the same games without it — printing
the command behind each step, so the tour is also the tutorial.

Not ready to install? [`examples/`](../examples/) holds the real output of each
of those steps, one file each.

## What it can do

**Play deterministically.** A seed and a list of commands reproduce a game
exactly. 352 of 1045 known cards have working rules, each written from its
printed text with a test of its own.

**Keep a journal.** Not a replay — every position, everything else the engine
would have accepted at that moment, what was chosen, why (when a bot chose it),
and every event that followed. `fsme replay` plays it back and confirms it
still holds, naming the first command that diverges if the engine has changed
underneath.

**Report on one game.** `fsme report` gives the moments the game turned on
(measured from the events, not chosen), what set the winner apart, the
decisions weighed against a bot that shows its arithmetic, and which cards'
effects moved the scoreboard.

**Study many.** `fsme study` asks what a run of games has in common, and ends
by naming the cards worth putting under test.

**Test a card.** `fsme test-card` plays the same seeds with a card in the deck
and without it, and reports the difference with the uncertainty it sits inside.

**Run from a browser.** `fsme desk` puts all of it behind buttons, running the
same functions the commands run and printing the same text.

**Ship as one file.** A PyInstaller build carries the cards and both pages
inside itself and needs nothing installed.

## What it will not claim

Every report in FSME is written to be honest before it is impressive.

- Winners are compared with everybody else, so what separates them is as much
  symptom as cause. The wording is always "went with winning", never "caused".
- "No effect this run could see" is never shortened to "no effect".
- Turning points are where the game *went*, not proof it had to go there — no
  other line of play is tried.
- The bot is weak on purpose so that its reasoning can be read and argued with.
  Every statistic here is conditional on it.

The full list is in [LIMITATIONS.md](LIMITATIONS.md), including the largest
one: removing a card reshuffles every game, so a card test compares two
populations rather than two versions of one game.

## Notable fixes in this release

Everything below worked on the machine it was written on and failed for
everybody else. They were found by installing into an empty environment,
cloning into a clean directory, and reading CI.

- **The cards were not in the wheel.** A clean `pip install` produced an `fsme`
  that could print its version and nothing else.
- **`packaging/fsme.spec` and the Target expansion were not in the
  repository** — `*.spec` and `target/` in a stock Python `.gitignore` had
  swallowed them. A test now fails if anything under `content/`, `spec/`,
  `docs/`, `examples/` or `packaging/` becomes ignored.
- **`fsme demo` crashed on Windows** with a `UnicodeEncodeError` on its first
  line: cp1252 cannot encode a box-drawing rule. Found by CI, not by reasoning.
- **Error bars on the card test were about seven times too narrow**, so the
  tool was announcing effects that were not there. Spread is now measured from
  the games played rather than assumed.
- **The release workflow was falsely green** — it tested the built executable
  from inside the checkout, where the card data sits.

The full list is in [the changelog](../CHANGELOG.md).

## Verified on

Linux, Windows and macOS, by CI, on the commit this release is cut from:

| | installed with pip | as a single executable |
|---|---|---|
| Linux | ✅ | ✅ |
| Windows | ✅ | ✅ |
| macOS | ✅ | ✅ |

Each check runs from a directory with no card data in it — a build that
shipped no cards passes any test run beside the repository — and each ends by
running a study across two processes, which is the check that catches a frozen
Windows build restarting itself once per worker.

The author has run the Linux build by hand. Windows and macOS are CI's word.

## Known limits worth knowing before you start

- Two thirds of the card content has no behaviour yet.
- Some pairs of cards copy each other without end; the engine stops and names
  them rather than inventing a rule the published rules do not give.
- No network play, no accounts, no card editor, no mobile client.
- Not official, and not affiliated with anyone who publishes Four Souls.

## Please tell us what happened

This release exists to meet users, not to be finished. The most useful things
you can do are in [CONTRIBUTING.md](../CONTRIBUTING.md); the shortest version:

- **Report anything that surprised you, including a report you did not
  believe.** A statistic that reads as misleading is a defect here even when
  the arithmetic is right.
- **Always include the seed.** Every game is reproducible from one, which turns
  "it crashed sometimes" into a game we can watch happen.
- **Tell us the question you had**, not the feature you designed. There is more
  machinery here than the commands suggest.

Where this might go next — and what signal would justify each direction — is in
[NEXT.md](NEXT.md). Nothing on that list is scheduled, because a guess about a
user is worth much less than one sentence from a real one.
