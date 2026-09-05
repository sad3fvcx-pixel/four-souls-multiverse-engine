# Scenario v1: what to build, and in what order

The second architectural pass. [SCENARIO_LAYER.md](SCENARIO_LAYER.md) asked
where a scenario layer would fit; this one checks the proposed format field by
field against the running engine and turns it into a plan.

Still no code. Everything below that says "works" or "does not work" was run.

---

## 1. The format, checked field by field

### Supported today, no engine change

| Field | How it already works |
|---|---|
| `seed` | `new_game(seed=)` → `Game.from_content(seed=)` |
| `interactive_priority` | `Game.from_content(interactive_priority=)` |
| `content.expansions` | build a `ContentLibrary`, `add()` the wanted expansions, `check_dependencies()`. Verified: base game alone is 287 cards, 1 expansion |
| `content.exclude_cards` | `ContentLibrary.without(ids)` — the call `fsme test-card` already runs on |
| `players[].name` | `new_game(players=[names])` |

### Supported by `new_game`, unreachable from outside

`souls_to_win`, `monster_slots`, `shop_slots` are parameters of `new_game()`
that `Game.from_content` does not forward. Opening that is one line each.

All three were played through whole games to see whether they survive:

```
default          finished  turn  28   shop 2  monsters 2
shop_slots=0     finished  turn  62   shop 0  monsters 2
shop_slots=4     finished  turn  60   shop 4  monsters 2
monster_slots=1  finished  turn  36   shop 2  monsters 1
monster_slots=4  finished  turn  32   shop 2  monsters 4
souls_to_win=1   finished  turn   3   shop 2  monsters 2
souls_to_win=8   finished  turn  54   shop 2  monsters 2
1 player         finished  turn  68
4 players        finished  turn  49
```

**One value does not hold: `monster_slots: 0`.** The board starts empty and
stays empty — until somebody attacks the monster deck. `rules.slots.place()`
puts a monster "into a new slot if the row is full", so the revealed monster
creates a slot and the game runs with one from then on. Traced directly:

```
after new_game : slots 0   active 0
after start    : slots 0   active 0
attack the deck: accepted
after attack   : slots 1   active 1
```

That is defensible engine behaviour — a monster has to go somewhere — but it
means `0` is not a configuration the engine holds. **v1 must reject
`monster_slots < 1`.** `shop_slots: 0` has no such problem and is a genuinely
interesting experiment.

### Needs new state, and only these two

`players[].coins` and `players[].loot` are dealt by the `start_game` *command*
(`StartGameHandler.execute`) from module constants in `rules/constants.py`.

They cannot be set by writing the constants. Those are imported by name at
import time, so setting one sets it for **every game in the process**, which in
a study worker is the other 999 games. The pattern to follow is already in the
engine and already documented in its own docstring — `GameState.monster_slots`:

> Cards expand both, so the number belongs to the game rather than to the
> rules: a constant cannot be changed mid-game and a game that was expanded
> has to reload expanded.

So: **two new fields on `GameState`**, `starting_coins` and `starting_hand`,
defaulting to the constants, read by `StartGameHandler` instead of the imports.
Per-game, saved with the game, and inert once the game has started.

### Needs a seam in setup — verified working

`players[].character` and `players[].starting_item` have no seam today:
`setup._seat_players` shuffles the character pool and assigns by seat, and
`_give_starting_item` reads the character's printed metadata.

A prototype of the seam was written in a scratch process and run:

```
pinned:   [characters-base_game-isaac, characters-base_game-cain]
seat 0 starting item: starting_items-base_game-the_d6
finished: True
scenario + seed run twice, journals identical: True
same seed without the scenario: [requiem-eden, alt_art-the_forgotten], a different game
```

**The rule that made it deterministic is worth stating as a requirement:
`rng.shuffle(characters)` still happens, in the same place, whatever the
scenario pinned.** The pinned characters are then lifted out of the shuffled
pool and the rest fill the remaining seats in order. Skipping the shuffle when
every seat is pinned would move every later RNG call and change the whole deal
for no reason a reader could see.

### Must not be in v1

**`content.root`.** A filesystem path inside a data file that people will
share. Somebody else's absolute path is broken at best and a traversal at
worst. **Where the content lives is where the tool is pointed (`--content`),
not what the data claims.** Keep `expansions` and `exclude_cards`; drop `root`.

**`players: []` as written.** An empty list is ambiguous — no players, or the
default table? Absent means "deal as usual"; a present list sets both the count
and the per-seat configuration; `[]` is refused with a sentence saying to leave
the key out.

**Anything about the board.** A wounded monster, a card already in a discard, a
turn already in progress. That is the save format, and a scenario that could
express it would be a worse save file.

**Anything about a run.** How many games, how many cores, which seats a bot
plays. `--bot-seats` and `--games` already say those, and they are properties
of the experiment, not of the position.

**Effects, rules, card definitions.** The moment a scenario can say "damage is
doubled", the rules live in two places.

### `seed` is a default, not part of the scenario's identity

A study runs one scenario over a thousand seeds. If the seed were part of the
scenario, that run would be meaningless. So: the scenario's `seed` is what a
single game uses when nothing else says otherwise, an explicit `--seed` beats
it, and a multi-game run overrides it per game. The journal already records
`seed` in its own field; the scenario recorded beside it should be the one
*without* the seed folded in.

The identity is **(scenario, seed)** — two fields, not one.

### The format, after the checks

```json
{
  "format": "fsme-scenario",
  "version": 1,

  "name": "Base game, no shop",
  "description": "Does the shop matter? Play without one and see.",

  "seed": 1234,
  "interactive_priority": false,

  "content": {
    "expansions": ["base_game"],
    "exclude_cards": []
  },

  "table": {
    "souls_to_win": 4,
    "monster_slots": 2,
    "shop_slots": 0
  },

  "players": [
    { "name": "Ann",
      "character": "characters-base_game-isaac",
      "starting_item": "starting_items-base_game-the_d6",
      "coins": 3,
      "loot": 3 },
    { "name": "Bo" }
  ]
}
```

Every key optional. `{"format": "fsme-scenario", "version": 1}` is the game
FSME plays today.

---

## 2. Integration: the minimal path

```
scenario.json
     │  read and validated once, into a frozen dataclass
     ▼
Game.from_content(library, players, seed=, scenario=None)
     │  forwards souls_to_win / monster_slots / shop_slots / seats to new_game()
     │
     ├── Session(scenario=)        → Watch
     ├── play_one(scenario=)       → Study, simulate, test-card
     ├── replay_journal(...)       → Replay — reads the scenario out of the journal
     └── risks(...)                → report — same
```

`Scenario` is **a frozen dataclass of plain data in `fsme/scenario/`**, not a
game object. It has no behaviour, never enters `GameState`, is consumed
entirely during setup, and imports nothing from `fsme.rules` or `fsme.game` —
so `rules.setup` can read it without a cycle. That is what "no separate game
object inside Core" has to mean in practice.

`library` is still built by the caller. The scenario says *which expansions*;
turning that into a `ContentLibrary` is one helper beside the content package,
because `pool.py` hands workers a **root path and plain data**, never a loaded
library.

Two existing behaviours the scenario must respect rather than change:

- `Session._new_game()` submits `start_game` through the keeper, so the deal is
  the journal's first entry. A scenario changes what that deal produces and
  nothing about the shape of the record;
- `replay_journal` deals the game itself only when the journal does not record
  a deal (`_deals_itself`). `risks()` in `lab/analysis/risk.py` calls `start()`
  unconditionally instead — on a Watch journal it therefore refuses at the
  first command and reports `faithful=False, weighed=0`, which is safe but
  useless. Verified. When that path learns about scenarios it should adopt
  `replay_journal`'s reading at the same time.

---

## 3. Reproducibility: how (scenario, seed) names one game

### What already guarantees it

The digest chain. A journal records a fingerprint of the position after every
command, and replay compares each one. Replaying a journal against a library
with a single card removed fails at **entry 0** — verified, not assumed. It
fails safe today and would fail safe under scenarios.

What it cannot do is say *why*. The message is "left the game in a different
state", not "you replayed this against different content".

So the question is not "is divergence caught" but "can replay reconstruct the
table without help, and can a mismatch be explained".

### The recommendation: A **and** B, with the scenario inlined

Not a choice between them. Three parts, and each does something the others
cannot.

**1 — Inline the resolved scenario in the journal.** Not an id, not only a
hash: the whole normalised scenario, defaults filled in. This is what makes a
journal self-contained, and it is what the required test 6 — *"save journal →
replay must not depend on the original scenario"* — actually demands. A record
that needs an external file which may since have been edited is not a record.
The cost is nothing: a scenario is a few hundred bytes against a journal of
~120 KB.

**2 — Carry a digest of it beside the inlined copy.** Cheap, and it lets two
runs be compared without diffing two trees, and a tampered journal be spotted.

**3 — Bump `JOURNAL_FORMAT_VERSION` to `"2"`, and read `"1"` as "no
scenario".** This is the part option A alone cannot do. An optional field added
without a bump means an older build reads a scenario journal, ignores the
field, replays a default game and reports a divergence it cannot explain —
exactly the failure the whole design exists to prevent. `Journal.from_dict`
already refuses an unknown format with a sentence saying so; a bump turns a
silent wrong answer into a named refusal. Accepting `"1"` as a
scenario-less journal is what keeps that bump affordable: no existing journal
is orphaned, because a journal written before scenarios existed genuinely has
no scenario.

**And, at the same time: stop leaving `content_version` empty.** It has been a
field with no writer since it was added. Filling it with the expansions
actually loaded and their manifest versions — `base_game@1.0.0,requiem@…` — is
cheap and turns a mute divergence into a diagnosable one.

### A side benefit worth naming

`replay_journal` currently *infers* whether a game was played with interactive
priority, and says in its own docstring that this is inference and where to
look when it is wrong. A journal that records a scenario records
`interactive_priority` with it. **The inference can stop being an inference** —
a documented limitation closed as a side effect rather than as a project.

### The save format needs no bump

`starting_coins` and `starting_hand` only matter before `start_game`, and a
save is taken from a game in progress. Read them with a default when absent and
old saves keep loading. This is the opposite call from the journal, and for the
opposite reason: in a save the fields are inert, in a journal they decide the
deal.

---

## 4. Custom content

### What already works — tested, not assumed

A directory under the content root with a `manifest.json` and card files is
loaded as an expansion. A hand-written two-card set was put beside `base_game`:

- the good card loaded, was shuffled into the loot deck of an ordinary deal,
  was played and paid out — **288 cards, coins 3 → 10**;
- a card naming an effect that does not exist was refused before any game
  existed, by name and by file:
  `[semantic] my_set/cards/loot.json: my_set-loot-a_thing_that_cannot_work:
  ability 0: unknown effect 'summon_a_dragon'`.

So the proposed

```json
"content": { "expansions": ["base_game", "my_expansion"] }
```

**works with no Core change at all**, as soon as `expansions` is honoured. The
building blocks are 70 effects, 44 conditions, 46 targets and 66 triggers, read
out of the live engine by `engine_vocabulary()` — the same language the 352
implemented official cards are written in.

### What is missing

- **selection.** Nothing can say "these expansions and no others" — that is the
  `content.expansions` field, and it is the whole of the gap;
- **dependency checking on a subset.** `check_dependencies()` exists and must be
  called after building a sub-library, or a scenario can select a set whose
  requirement it left out. No expansion declares one today, so this is a guard
  for later rather than a bug now;
- **`cards.json` + `abilities.json` as *runtime* files.** The split exists, but
  as a build tool: `content/*/_abilities.json` is merged into the card files by
  `tools/import_cards.py`, and files starting with `_` are skipped at load. A
  set shipped as two files would need either the merge run first, or the loader
  taught to merge — and that is a content-pipeline change, not a scenario one;
- **identity.** Two people's `my_set` collide. That is what manifests were
  introduced to prevent and it is a naming decision, not an engine problem.

### What stays outside Scenario

A scenario references content **by expansion id and never contains card
definitions**. A scenario that could define cards would be a second content
pipeline with no validation report, no manifest, no dependency check and no
version — and the first one refuses bad cards by name, which is the property
worth keeping.

---

## 5. CLI

`--scenario FILE` on the four commands that build games, and nothing new:

```
fsme serve   --scenario example.json     # Watch — the page
fsme study   --scenario example.json     # many games, one scenario
fsme simulate --scenario example.json
fsme play    --scenario example.json     # one game, no page
```

`fsme replay journal.json` and `fsme report journal.json` take **no** scenario
flag. They read it out of the journal, which is the point of inlining it.

Two notes on the naming:

- **there is no `fsme watch`.** The Watch page is `fsme serve`. Adding a
  `watch` alias would be a new command, which was ruled out; the flag goes on
  `serve`;
- ten commands share `--content/--seed/--players` through one `shared()`
  helper. `--scenario` must **not** go there: on `cards` and `show` it means
  nothing, and a flag that is accepted and ignored is worse than one that is
  absent.

Precedence has to be decided once and written down. The proposal: an explicit
`--seed`/`--players` beats the scenario; the scenario beats the defaults; a
multi-game run always overrides the seed per game. A `--content` that
contradicts a scenario's expansions is not a conflict — the scenario names sets
within the root the flag points at.

---

## 6. The tests, written before the code

The seven required, each with what it actually proves and how it fails today.

**1 — an empty scenario is an ordinary game.** `{"format": ..., "version": 1}`
against seed N produces a journal identical, field by field, to the same seed
with no scenario at all. *This is the test that protects Core Stable*: it is
the whole regression suite's guarantee that the new argument changed nothing
when it is not used.

**2 — a named character is dealt.** Pin seat 0's character; assert that seat
has it, and that the shuffle still ran (seat 1 is not the first character in
content order). Fails today: no seam.

**3 — a named starting item is dealt.** Pin an item that is not the character's
printed one; assert the character's own item is *not* also in play. Fails
today: no seam.

**4 — a scenario with a custom deck plays.** `expansions: ["base_game"]` plus a
temporary hand-written set in `tmp_path`; assert the custom card is in the deck
and a base-game card that was excluded is not. Fails today: `expansions` is not
honoured. **The content root must be `tmp_path`** — a test that writes into
`content/` has happened in this project before.

**5 — (scenario, seed) names one game.** The same scenario and seed run three
times, journals compared entry by entry including digests and every event
field. Then run on all three paths — simulation, Session, replay — because a
seed names one game *per path* and a scenario must not change that.

**6 — a saved journal replays without the scenario file.** Write the journal,
then delete the scenario file *and* write a different scenario under the same
name; replay from the journal alone and assert it is faithful. This is the test
that forces inlining, and it is the one that would catch a design that stored
only an id.

**7 — a foreign scenario is refused by name.** Following `journal/file.py`,
which refuses six different ways with six different sentences: not JSON; not a
scenario (`format` missing or wrong); a `version` this build cannot read; an
unknown expansion; an unknown character or item id; `players: []`.

Five more that the audit says are worth as much as those seven:

**8 — `monster_slots: 0` is refused**, with a sentence saying why, rather than
silently becoming 1 at the first attack on the monster deck.

**9 — a scenario does not leak between games.** Play two games in one process,
the first with a scenario setting `starting_coins`, the second without; assert
the second is an ordinary game. This is the test that would have caught writing
the constants module instead of `GameState`.

**10 — a scenario naming an expansion that is not there is refused**, and one
naming a set whose `requires` is unmet is refused.

**11 — a version-1 journal still loads**, and replays, with no scenario. The
bump must not orphan a single existing journal.

**12 — the whole thousand-game invariant run under a non-default scenario.**
Cards conserved, games finish, economy balances. A scenario changes the table,
and the table is what the invariants are about.

---

## 7. The plan

### Files, in the order they should change

**Step 1 — the format, alone and inert.** Nothing else in the engine knows it
exists yet.
- `src/fsme/scenario/__init__.py`, `src/fsme/scenario/scenario.py` — a frozen
  dataclass, `from_dict`/`to_dict`, `read(path)`, and validation with one
  sentence per way of being wrong. Imports nothing from `rules` or `game`.
- `tests/test_scenario.py` — test 7 and test 8. All of it is testable with no
  game at all.

**Step 2 — the two new state fields.** Small, self-contained, no scenario in
sight.
- `src/fsme/state/game_state.py` — `starting_coins`, `starting_hand`.
- `src/fsme/rules/turn.py` — `StartGameHandler` reads state, not constants.
- `src/fsme/serialization/game_save.py` — write them; read with a default; no
  format bump.
- tests: an ordinary game is unchanged; a state built with other values deals
  them.

**Step 3 — the setup seam.**
- `src/fsme/rules/setup.py` — `new_game(..., scenario=None)`; `_seat_players`
  honours pinned characters and items **after the shuffle**.
- `src/fsme/game/game.py` — `from_content(..., scenario=None)`, forwarding the
  three table parameters it currently drops.
- `src/fsme/content/library.py` — a helper that builds a sub-library from
  expansion ids and calls `check_dependencies()`.
- tests 1, 2, 3, 4, 9, 10.

**Step 4 — the journal.** The step that cannot be got wrong twice.
- `src/fsme/journal/entry.py` — `Journal.scenario`, `scenario_digest`; format
  `"2"`; `"1"` read as scenario-less.
- `src/fsme/journal/keeper.py` — take the scenario and the content version and
  record them.
- `src/fsme/journal/replay.py` — rebuild from the recorded scenario; stop
  inferring `interactive_priority` when the scenario says.
- `src/fsme/journal/file.py` — the envelope needs no change; its version is
  about the wrapper, not the journal.
- tests 5, 6, 11.

**Step 5 — the callers.**
- `src/fsme/api/session.py` — `scenario=` pass-through; revisit the 2–4 player
  cap.
- `src/fsme/lab/simulation/runner.py` — `play_one(scenario=)`.
- `src/fsme/lab/simulation/pool.py` — `_prepare(root, drop, scenario)`, plain
  data across the process boundary.
- `src/fsme/lab/analysis/risk.py` — read the journal's scenario, and adopt
  `_deals_itself` while there.
- test 12.

**Step 6 — the command line and the documents.**
- `src/fsme/cli/main.py` — `--scenario` on `serve`, `play`, `simulate`,
  `study`; precedence written into the help text.
- `docs/SCENARIO_LAYER.md`, `docs/CORE_STABLE.md`, `CHANGELOG.md`, and an
  example scenario somewhere a person will find it.

### Risks

**Every scenario is a new deal, and numbers do not cross.** A study under one
scenario cannot be compared with a study under another, and reports will have
to say which one they came from. This is not a defect; it is the thing the
layer is for, and it will still surprise somebody.

**The journal bump is the one irreversible step.** Everything else can be
softened later. Reading `"1"` as scenario-less is what makes it safe, and it
has to be in the same commit as the bump.

**`starting_coins` in the wrong place would be invisible.** Written into
`rules/constants.py` it would work in every test — tests run one game per
process — and corrupt every study, which runs a thousand. Test 9 exists for
exactly this and should be written before the field is.

**Scope creep has one specific shape here**, and it is the word "starting". A
starting *position* is a save; a starting *configuration* is a scenario. Every
request to add "just one more thing the game starts with" is a request to
reinvent the save format inside the scenario format.

**The two shapes of journal are still two.** A scenario does not fix that, and
`risks()` shows what it costs. Do not let the scenario work quietly become the
journal-unification work; they are separate, and the second moves every number
ever measured.

### Deliberately not in v1

Board state · scripted opponents · run parameters · rules and effects · card
definitions · `content.root` · a scenario editor · a text parser · scenario
inheritance or includes · per-card quantities in a deck · anything that would
make a scenario capable of describing something the engine cannot already do.
