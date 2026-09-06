# How to help

FSME is being shown to people for the first time. The most valuable thing
anybody can do right now is **use it and say what happened** — the project has
never met a user, and every guess about what people need is worth less than one
sentence from somebody who tried.

## The most useful things, roughly in order

**1. Tell us what you were trying to find out.** Not what feature you want —
what question you had. There is machinery here that answers more than its
commands suggest, and a question often reshapes a feature entirely.
[Open a request](.github/ISSUE_TEMPLATE/feature_request.yml).

**2. Report anything that surprised you**, including a report you did not
believe. A statistic that reads as misleading is a bug in this project even
when the arithmetic is right. Always include the **seed** — every game is
reproducible from one, so a seed turns a story into something we can watch.
[Open a bug](.github/ISSUE_TEMPLATE/bug_report.yml).

**3. Implement a card.** 693 of 1045 known cards are data with no behaviour.
This is the largest single gap and the most self-contained work in the project.

**4. Point at a rule we got wrong.** Quote the printed card or the rulebook.
Deliberate departures are listed in `docs/PROJECT_PLAN.md` §11.5; anything not
there is unintended.

## Implementing a card

Cards are data. Nothing you write here is code.

1. Find the card in `content/<set>/cards/` — it will have a name, a type and
   its printed text, and no `abilities`.
2. Write the ability into `content/<set>/_abilities.json`, keyed by card id.
3. `fsme cards` validates it. Mistakes are named where they are, with the
   nearest thing the engine knows.
4. Write a test in `tests/test_official_cards.py` — one per card, asserting
   what the printed text says.
5. `pytest -q`.

Two rules that are not negotiable:

- **Write the ability from the printed text of the card in front of you.** Do
  not write it from memory of the game, and do not guess at what a card
  "probably" does. A card whose behaviour the text and the rules do not settle
  is recorded as a gap in `docs/PROJECT_PLAN.md` §11.5 rather than invented.
- **A card with no test is not implemented.** The test is what makes the next
  person able to change the engine without silently changing your card.

The vocabulary the engine understands is in `docs/EFFECT_REGISTRY.md`,
`docs/TRIGGER_REGISTRY.md`, `docs/CONDITION_REGISTRY.md` and
`docs/TARGET_REGISTRY.md`. If a card needs something not in there, that is a
missing mechanic — say so in the issue rather than approximating it.

## Working on the engine

```bash
pip install -e ".[dev]"
pytest -q
ruff check .
mypy --strict src/fsme
```

All three must pass. There are no exceptions configured and adding one needs a
reason in the pull request.

### The one architectural rule

The **core** plays Four Souls: rules, cards, effects, events, state, the stack,
the runtime, the journal. The **laboratory** (`fsme.lab`) asks questions about
it: the bot, simulation, analysis, the desk.

The dependency runs one way. The lab imports the core; the core has never heard
of the lab. `tests/test_architecture.py` reads the imports and fails if that
stops being true. It means no report can become part of the rules, and nothing
that measures a game can change one.

### What the code is expected to look like

Match the file you are editing. Beyond that:

- **A comment explains why, not what.** The code says what it does.
- **A number that could have been another number gets a name and a docstring
  saying what would justify changing it.** There are a lot of these in the lab
  and they are all arguable on purpose.
- **Wording is part of the work.** This project prints statistics for people to
  act on, so a report that says "caused" where it means "went with" is a
  defect. If you add a measurement, add the sentence that says what it is not.

## What will not be merged

Written down so nobody spends an evening on it. `docs/NEXT.md` has the
reasoning.

- a card maker or card editor UI
- a story, narrative or lore generator
- network play, accounts, matchmaking, a mobile client
- a plugin or module system — there is no second implementation of anything
  yet, so an extension point would be a guess at a shape nobody has needed
- anything that lets analysis change how a game plays

## Pull requests

Small ones. One card, one fix, one measurement. Say what you changed and what
you checked; if you changed a report, paste the before and after — the output
is the product.
