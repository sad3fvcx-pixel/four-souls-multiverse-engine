# Four Souls Multiverse Engine

Deterministic engine for The Binding of Isaac: Four Souls with support for the custom expansion Syndrome of the Multiverse.

FSME is not an engine for a single expansion. It is a universal rules simulator that runs
official cards and user-created content through the same data pipeline and ability DSL.

Current version: 0.1.0-alpha

## Running it

```bash
pip install -e .

fsme serve          # a game in the browser at http://127.0.0.1:8000/
fsme play --seed 3  # play one through with nobody watching
fsme cards          # what the content holds, and how much of it is implemented
```

### Journals

A journal is a whole game written down: where it stood at every decision, what
the engine would have accepted, what was chosen, and everything that followed.

```bash
fsme play --seed 3 --journal party.json --offers
fsme show party.json          # read it as a game
fsme replay party.json        # play it back and check it still holds
```

It is a replay as well as a reading — it holds the commands and a fingerprint
of the position after each — so `fsme replay` reports the first entry whose
outcome no longer matches instead of only that something changed. A game played
in the browser keeps one too, at `/api/journal`.

`fsme serve` opens a page showing the table, the stack, the log and every move
the engine will accept; clicking one submits it. The page is a client and
nothing more — it decides no rule, and every button on it came from the
engine's own validators.

### A single executable

For people without Python:

```bash
pip install -e ".[build]"
pyinstaller packaging/fsme.spec     # → dist/fsme, or dist/fsme.exe on Windows
```

The build carries the cards and the page inside itself and needs nothing
installed to run. Started with no arguments — double-clicked, as an `.exe`
usually is — it serves the game and opens a browser at it.

An executable cannot be cross-compiled: a Windows `.exe` has to be built on
Windows. `.github/workflows/build.yml` does that for Windows, macOS and Linux
and uploads all three, so a tag is enough to get an `.exe` without owning a
Windows machine.

### Simulation

```bash
fsme simulate --games 100 --players 3 --jobs 4
fsme test-card treasure_deck-active_items-base_game-guppy_s_paw --games 500
```

Plays a run of games — each from its own seed, each through the ordinary engine
— and counts what happened across all of them: characters, cards, monsters and
events. `--journals DIR` keeps every game as a journal; `--json` prints the
tally as data.

The numbers describe the game under a table that chooses at random among legal
moves, and the report says so. A card's "won %" is how often the player holding
it went on to win — a correlation, not the card's doing.

`test-card` is the tool that can do better: it plays the same seeds with the
card in the content and without it, and reports each difference with the noise
it sits in. Taking a card out reshuffles every game, so when a card reached the
table rarely the report marks nothing and says the difference is the deck
rather than the card.

## Documentation

- [Project Plan](docs/PROJECT_PLAN.md) — structure, stages, current state
- [Engine Specification](docs/ENGINE_SPEC.md) — architectural principles
- [Engine Execution Model](docs/ENGINE_EXECUTION_MODEL.md) — main loop
- [Development Guidelines](docs/DEVELOPMENT_GUIDELINES.md) — mandatory rules
- [Rules Specification](spec/RULES_SPEC.md) — game rules
- [Comprehensive Rules](spec/COMPREHENSIVE_RULES.md) — the rules the engine implements
- [Official Card Coverage](docs/OFFICIAL_CARD_COVERAGE.md) — generated from the content
