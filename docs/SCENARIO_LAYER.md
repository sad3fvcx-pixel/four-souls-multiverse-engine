# The Scenario layer

An architectural study, written after Core Stable and before any code. Nothing
here has been built. What has been done is reading the engine and running it,
so that every claim below is either a file and a line or a measurement somebody
can repeat.

The question is narrow on purpose: **what is the smallest change that lets a
person set up their own experiment?** Not an editor, not a UI, not a new game
model. A scenario describes the position a game starts from; the game that
follows is the game FSME already plays.

---

## 1. How a game comes into existence today

### One door, four callers

Every game in the project is built by the same classmethod:

```
Game.from_content(library, players, seed=, interactive_priority=, rng=)
                          │
      ┌───────────────────┼───────────────────┬──────────────────┐
      │                   │                   │                  │
  Session              play_one          replay_journal      risk.py
  (api/session.py)  (lab/simulation)   (journal/replay.py)  (lab/analysis)
      │                   │                   │                  │
    Watch          Study / simulate         Replay            report
                    / test-card
```

Four call sites, and no fifth. This is the single most useful fact in this
document: a scenario applied at `Game.from_content` reaches Watch, Study,
Replay and the analysis path at once, and a scenario applied anywhere else has
to be applied four times.

### The deal happens in two stages, not one

This is the second load-bearing fact, and it is easy to get wrong.

**Stage one — `rules.setup.new_game()`** builds the table before anybody has
acted: decks built from the library and shuffled in a fixed order, bonus souls
laid out, a character and its printed starting item dealt to each seat, monster
slots and shop slots turned face up, the first room turned over. It returns a
`GameState` with `started = False`.

**Stage two — the `start_game` command** deals the opening hands and the
starting cents, picks the first seat, and opens the first turn
(`rules/turn.py`, `StartGameHandler.execute`).

So "three loot cards and 3¢" is not part of the layout — it is the first
command of the game, and it is in the journal. Anything a scenario does to the
*table* belongs in stage one. Anything it does to *starting resources* is
currently inside a command, which is a different kind of change and a more
delicate one.

### What is already a parameter, and what is not

`new_game()` already takes `souls_to_win`, `monster_slots` and `shop_slots`.
**`Game.from_content` does not forward any of them**, so from outside the rules
package they are unreachable — three parameters that exist and cannot be used.
That is the seam a scenario wants, already cut and not yet opened.

| A scenario would set | Where it lives now | Reachable today? |
|---|---|---|
| number of players, names | `new_game(players=[...])` | yes |
| seed | `new_game(seed=)` | yes |
| interactive priority | `Game.from_content` | yes |
| which cards are in the decks | the `ContentLibrary` handed in; `library.without(ids)` already exists | yes, by choosing the library |
| souls to win | `GameState.souls_to_win` | in `new_game`, not forwarded |
| monster and shop slots | `GameState.monster_slots` / `shop_slots` | in `new_game`, not forwarded |
| character per seat | `setup._seat_players` shuffles and assigns by seat | **no seam** |
| starting item per seat | `setup._give_starting_item`, read from the character's metadata | **no seam** |
| starting coins, opening hand | `rules/constants.py`, read inside `StartGameHandler` | **no seam** |

### Where a number may live, and where it may not

`GameState.monster_slots` carries a docstring that settles this question for
every field a scenario would want to add:

> Cards expand both, so the number belongs to the game rather than to the
> rules: a constant cannot be changed mid-game and a game that was expanded
> has to reload expanded.

`rules/constants.py` says it exists "so that a custom ruleset can change them
without editing rule logic" — but they are module constants, imported by name
at import time. Changing one changes it for **every game in the process**,
including the other 999 games a study worker is playing. They are safe to read
and unsafe to set.

**Rule: anything a scenario changes must be a field on `GameState`.** Then it
is per-game, it is saved (`serialization/game_save.py` already writes
`souls_to_win`, `monster_slots`, `shop_slots`), and it reloads with the game.

### What can already be serialized

Three formats exist and all three are versioned:

- **the save** (`save_game`) — every card in every zone, the turn, the stack's
  absence, the priority window, combat, the RNG position. Enough to continue a
  game. Refuses to write mid-ability;
- **the journal** (`Journal.to_dict`) — seed, player names, characters, engine
  version, `content_version`, every accepted command with the position before
  it, every event it caused, and a digest of the position after. Enough to
  replay a game;
- **the journal file envelope** (`journal/file.py`) — `fsme-journal`, version 1,
  around either of the journal's two shapes.

`content_version` is a field that **nothing ever fills in**. It is the slot a
scenario identity belongs in, and it has been empty since it was added.

### The minimum entry point

**`Game.from_content` — one new keyword argument, defaulted to nothing.**

```python
Game.from_content(library, players, seed=..., scenario=None)
```

With `scenario=None` the engine behaves exactly as it does today, which is what
keeps 1015 tests and every measured number valid. With a scenario it forwards
the fields to `new_game()` and lets the setup read them.

Nothing else is required for a scenario to reach all four callers.

---

## 2. Scenario v1, as a format

A scenario is **a description of a starting position, not a game model**. It
names things that already exist, and every field is optional: an empty scenario
is the game FSME plays today.

```json
{
  "format": "fsme-scenario",
  "version": 1,

  "name": "Two players, base game only, no shop",
  "description": "Does the shop matter? Play without one and see.",

  "seed": 1234,
  "interactive_priority": false,

  "content": {
    "root": "content",
    "expansions": ["base_game"],
    "exclude_cards": ["treasure_deck-active_items-base_game-flush"]
  },

  "table": {
    "souls_to_win": 4,
    "monster_slots": 2,
    "shop_slots": 0
  },

  "players": [
    {
      "name": "Ann",
      "character": "characters-base_game-isaac",
      "starting_item": "starting_items-base_game-the_d6",
      "coins": 3,
      "loot": 3
    },
    { "name": "Bo" }
  ]
}
```

### Why each field is shaped that way

**`content.expansions` is the most valuable field in the format**, and the
reason is a measurement rather than a preference. FSME loads every directory
under the content root, so **every game it has ever played was dealt from all
24 expansions at once — 1045 cards, of which 254 are duplicate printings of 101
names.** There are twelve copies of `Pills!` in the loot deck and six of Eden
among the characters. No table plays that way. One field turns the project's
measurements from "a game with everything ever printed in it" into "a game
somebody could sit down to".

**`content.exclude_cards` already has an implementation.**
`ContentLibrary.without(ids)` is what `fsme test-card` runs on. A scenario would
use the same call rather than a new one.

**`players` is a list, not a count.** A seat with only a name is dealt the way
it is dealt today, so `[{"name": "Ann"}, {"name": "Bo"}]` is exactly today's
two-player game. Naming a character fixes that seat; leaving it out shuffles as
before. This keeps "partly specified" scenarios possible, which is what an
experiment usually wants — fix one thing, randomise the rest.

**`coins` and `loot` per seat, not per game.** "What happens if one player
starts rich?" is a scenario somebody will want, and a per-game number cannot
express it. These are the two fields that need new `GameState` storage.

**No effects, no rules, no cards.** A scenario cannot say "damage is doubled"
or "add this ability to that card". The moment it can, it is a second place
where the rules live, and the engine stops being the only answer to what a game
does. Rules changes belong in the rules; card changes belong in content.

### What v1 deliberately leaves out

- **starting board state** — a monster already wounded, a card already in a
  discard. This is what the *save* format is for, and a scenario that could
  express it would be a worse save file;
- **scripted opponents** — which seats a bot plays is a property of the run,
  not of the position. `--bot-seats` already says it;
- **anything about the run** — how many games, how many cores, what to measure.
  A scenario describes one starting position; a study describes what to do with
  many of them.

---

## 3. Integration

### Should a scenario build a `Game` directly, or go through `Session`?

**Directly, at `Game.from_content`.** `Session` is a client boundary — it holds
one game, forwards commands and returns views, and its own docstring says that
if a rule needs stating to make a client work, it belongs in `fsme.rules`.
Putting scenario handling in `Session` would leave Study and Replay without it.

`Session` gains a pass-through: `Session(library, players=..., scenario=...)`.
Its current signature also caps players at 2–4 while `new_game` allows 1 and
more; a scenario naming five seats would need that cap reconsidered, and that
is a decision, not a detail.

### How does a scenario meet Watch?

`Session._new_game()` builds the game and immediately submits `start_game`
through the keeper, so **the deal is the journal's first entry**. A scenario
changes what that deal produces and nothing about the shape of the record.

The CLI seam is small: every lab command already shares three arguments —
`--content`, `--seed`, `--players`. A fourth, `--scenario FILE`, sits beside
them, and where a scenario names something the flag also names, the flag wins
or the run refuses. That choice should be made once and written down.

### How does a scenario meet Study?

This is the constraint that shapes the format. `lab/simulation/pool.py` starts
each worker with `_prepare(root, drop)` — **a directory path and a tuple of
card ids**, never a loaded library, because a library is large and every worker
needs its own anyway.

So a scenario reaching a study must be **plain data or a path**, and must be
cheap to re-read per worker. A JSON file is both. A scenario that held a loaded
library, or anything unpicklable, would not cross the process boundary. This is
why the format above names content by root and expansion id rather than by
object.

### How is a scenario kept beside a journal?

It has to be, and this is the sharpest risk in the whole design.

Replay rebuilds the game with `Game.from_content(library, journal.players,
seed=journal.seed)` and compares each position against the digest the journal
recorded. **A journal that does not name its scenario replays into a different
game.**

The existing behaviour is already the right shape: replaying a journal against
a library with one card removed fails at entry 0 — verified, not assumed —
because the digest chain catches it. It fails safe. What it cannot do is say
*why*: the message is "left the game in a different state", not "you replayed
this against different content".

Two options, and the choice is a decision rather than a detail:

- **an optional `scenario` field in the journal**, holding the scenario inline
  or its identity and a hash. Old journals stay readable; a new journal read by
  an older build would be silently replayed without its scenario, which is the
  failure this is meant to prevent;
- **a journal format bump to `2`**, which makes old builds refuse new journals
  by name rather than misread them. `Journal.from_dict` already refuses a
  format it does not know, with a sentence saying so.

The second is safer and costs a migration. Either way, the empty
`content_version` field should stop being empty at the same time.

### The shape it lands in

```
scenario.json ──► Game.from_content(library, players, seed, scenario)
                            │
        ┌───────────────────┼───────────────────┐
      Watch               Study               Replay
    (Session)           (play_one)       (replay_journal,
                                          reading the scenario
                                          back out of the journal)
```

---

## 4. Custom cards: the boundary

### They already work

This was tested rather than reasoned about. A directory under the content root
with a `manifest.json` and a card file is loaded as an expansion — the loader
walks every directory that has a manifest, and files whose names start with `_`
are skipped as working material.

A two-card set was written by hand and put beside `base_game`:

- the good card loaded, was shuffled into the loot deck of an ordinary deal,
  was played, and paid out: **288 cards, coins 3 → 10**;
- the nonsense card was refused before any game existed, by name and by file:
  `[semantic] my_set/cards/loot.json: my_set-loot-a_thing_that_cannot_work:
  ability 0: unknown effect 'summon_a_dragon'`.

**No new mechanism is needed for custom cards.** What is missing is only that
nothing tells a person this is possible, and that a scenario cannot yet say
"use my set and the base game and nothing else".

### Data and logic are already separate — twice over

**At runtime**, a card is data and only data. `CardDefinition` holds a frozen
tree of triggers, conditions, targets and effects, and the engine interprets
it: `freeze()` makes definitions immutable at load, and the loader's own
docstring is "nothing executable is ever loaded". The engine contains **no card
identifiers at all** outside one demo constant in the CLI — grepped and
confirmed. There is no card whose behaviour is Python.

**At authoring time**, the split is a second file. `content/*/_abilities.json`
holds hand-written behaviour keyed by card id, and `tools/import_cards.py`
merges it into the card files when content is imported. Printed data comes from
the database; rules come from a human. That is exactly the separation a card
template would need, and it exists — as a build tool, not as a runtime feature.

### What the building blocks actually are

Read out of the live engine rather than from a document, because
`engine_vocabulary()` is what content is validated against:

- **70 effects** — `gain_coins`, `deal_damage`, `draw_loot`, `move_cards`,
  `take_card`, `roll_dice`, `heal`, `kill`, `steal_treasure`, `add_modifier`,
  `add_counter`, `attach_curse`, `take_extra_turn`, and the control words
  `if`, `may`, `choose`, `repeat`, `for_each`, `sequence`, `watch_for`;
- **44 conditions**, **46 targets**, **66 triggers**.

That is a real language, and it is the same one the 352 implemented official
cards are written in. A card template layer would generate JSON in it, not
parse text into it.

### Where the boundary should be drawn

A custom card is content. It goes in a directory with a manifest, it is
validated by the same pipeline as everything else, and it is refused by name
when it is wrong. **A scenario should reference custom content by expansion id
and never contain card definitions itself.** A scenario that could define cards
would be a second content pipeline with no validation report, no manifest, no
dependency check and no version.

The one thing that genuinely needs designing later is **identity**: two people's
`my_set` collide, which is exactly what the manifest was introduced to prevent.
That is a naming problem, not an engine problem.

---

## 5. Stages after Core Stable

Not a schedule. Each stage is worth doing only when the one before it has been
used enough to say what is wrong with it.

### Stage 1 — Custom Scenario

**Goal.** A JSON file describes a starting position; Watch, Study and Replay
all honour it.

**What it gives.** The first experiment somebody can run that FSME cannot run
today: base game only, or no shop, or a fixed pair of characters, or the same
seed with one card removed. It also fixes, in one field, the fact that every
measurement so far was taken on a table holding all 24 sets at once.

**Risks.**
- *Replay divergence.* A journal that does not name its scenario replays into a
  different game. The digest catches it and cannot explain it. This is the one
  thing that must be settled before anything ships, not after.
- *Starting resources need new state.* `coins` and `loot` per seat are read from
  module constants inside a command. Moving them onto `GameState` is a small
  change to `StartGameHandler`, and it is a change to the rules package — the
  only one this stage needs.
- *Every number moves again.* A scenario that changes the deck changes the deal.
  Numbers measured under different scenarios are not comparable, and reports
  will need to say which scenario they came from.
- *Scope.* "Set the starting position" and "set the starting board" are one
  word apart. The second is the save format. The line has to be held.

### Stage 2 — Scenario Library

**Goal.** Scenarios are files that can be kept, named, listed, and referred to
by a report.

**What it gives.** An experiment becomes repeatable by somebody else. A study
result cites the scenario it was run under; a card test says what table it was
tested on.

**Risks.**
- *Versioning.* A scenario edited after a study was run silently invalidates the
  study. Scenarios need identity and a hash, the same way content does.
- *A library is a small database.* Listing, naming and finding are the beginning
  of a feature that has no natural end.

### Stage 3 — Laboratory UI

**Goal.** Build and run a scenario from the browser page instead of by editing
JSON.

**What it gives.** The people most likely to have an interesting question are
the least likely to want to write JSON.

**Risks.**
- *The largest scope risk in this document.* The page is currently one local
  game for one person, and it is not the product. A UI that builds scenarios is
  a form; a UI that edits games is a game client, which FSME has said it is not.
- *Two sources of truth.* The moment the page can express something the file
  cannot, the file stops being the record.

### Stage 4 — Custom Content / Card Templates

**Goal.** Help somebody write a card without knowing the effect DSL by heart.

**What it gives.** Little that is new in kind — custom cards already load and
play — and a great deal in reach.

**Risks.**
- *A text parser.* "Gain 3¢" is easy and "when this deals combat damage, cancel
  everything that hasn't resolved and end the turn" is not. A template picker
  over the 70 existing effects is a different and much smaller thing than a
  parser, and the difference should be decided deliberately.
- *Identity.* Two people's `my_set` collide. Namespacing is a design decision
  that gets much more expensive after people have made sets.
- *Measurement.* A study over custom cards measures a game nobody else has. That
  is the point, and every report will have to say so.

---

## 6. What must not move

- **The rules.** A scenario configures a game; it does not change what a game
  does. `souls_to_win` is a parameter because the rules already made it one.
- **The journal as the record.** Anything a scenario changes has to be in the
  journal, or the journal stops being a complete account.
- **`Game.from_content` as the one door.** Its value is that there is exactly
  one. A second way to build a game is a second thing that can be wrong.
- **The core/lab split.** Scenarios describe games, so the format and its
  loading belong in the core beside the content pipeline. What to *do* with
  many games stays in `fsme.lab`.
- **Determinism.** A scenario plus a seed must name one game, the way a seed
  does now. Every field added is a field the deal depends on.
