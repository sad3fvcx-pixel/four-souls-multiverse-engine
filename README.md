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

## Documentation

- [Project Plan](docs/PROJECT_PLAN.md) — structure, stages, current state
- [Engine Specification](docs/ENGINE_SPEC.md) — architectural principles
- [Engine Execution Model](docs/ENGINE_EXECUTION_MODEL.md) — main loop
- [Development Guidelines](docs/DEVELOPMENT_GUIDELINES.md) — mandatory rules
- [Rules Specification](spec/RULES_SPEC.md) — game rules
- [Comprehensive Rules](spec/COMPREHENSIVE_RULES.md) — the rules the engine implements
- [Official Card Coverage](docs/OFFICIAL_CARD_COVERAGE.md) — generated from the content
