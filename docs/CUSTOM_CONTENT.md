# Custom content: what exists, what is missing, what to build

An architectural study, written before any code. The question is narrow: **how
should somebody add their own cards so that the whole chain stays
reproducible?**

```
custom expansion → scenario → experiment → journal → analysis
```

Everything below that says "works" or "does not work" was run against the
engine, not read off it.

---

## 1. The pipeline as it stands

### It is already an extension API, and that is not an accident

A directory anywhere under the content root with a `manifest.json` in it is an
expansion. `ContentLoader.load_root` walks every such directory in sorted
order, reads every `*.json` that is not the manifest and does not begin with an
underscore, validates the lot, and refuses the whole batch if anything is
wrong.

Tested rather than assumed. A hand-written two-card set beside `base_game`:

- the good card loaded, was shuffled into the loot deck of an ordinary deal,
  was played, and paid out — **288 cards, coins 3 → 10**;
- a card naming an effect that does not exist was refused before any game
  existed, by name and by file:
  `[semantic] my_set/cards/loot.json: my_set-loot-a_thing_that_cannot_work:
  ability 0: unknown effect 'summon_a_dragon'`.

So the answer to "what is already a ready extension API" is: **the content
directory, the manifest, the card schema, and the engine vocabulary the schema
is checked against.** Those four are the contract. Everything else —
`ContentLoader`, `ValidationReport`, `Expansion`, the merge tool — is how it is
implemented, and none of it needs to be public for somebody to ship a set.

### Where the line between data and logic runs

Not between two files. **Inside the card.**

A `CardDefinition` is frozen at load (`freeze()` turns every nested mapping
into a `MappingProxyType`), and an ability is a tree of triggers, conditions,
targets and effects that the engine *interprets*. The loader's own docstring is
the rule: "nothing executable is ever loaded". Confirmed by grep — **the engine
contains no card identifiers at all** outside one demo constant in the command
line. There is no card whose behaviour is Python.

So:

| | lives where | who writes it |
|---|---|---|
| name, type, printed numbers, rewards, copies, card text | fields on the card | imported from a database, or typed |
| abilities, statics, ability costs, tags | fields on the same card | a person, by hand |
| what `gain_coins` *does* | `fsme/effects/builtin/` | the engine |

The DSL is the boundary. A card names effects; the engine owns them.

### `_abilities.json` is a build tool, not a format

The official content is generated from a card database, and re-running that
import must not destroy hand-written rules. So printed data is regenerated and
abilities live beside it in `content/*/_abilities.json`, merged in by
`tools/import_cards.py --refresh`. Files beginning with `_` are skipped at
load; the runtime never sees it.

**This is the answer to whether a custom expansion should be `cards.json` +
`abilities.json`: no.** That split solves a problem a custom set does not
have. Nobody is regenerating a custom author's printed data from a database, so
there is nothing for the second file to protect — and two files that must agree
is worse than one that cannot disagree.

---

## 2. The two real gaps

Everything above works. These do not, and they are what the next stage is
actually for.

### Gap 1 — validation checks vocabulary, not arguments

The pipeline promises that invalid content never reaches a game. It keeps that
promise for *names* and not for *values*. Two custom cards, both of which
loaded cleanly:

```
{"effect": "gain_coins",   "amount": "lots"}
{"effect": "shuffle_deck", "deck": "spaghetti"}
```

`loaded: 289 cards — validation raised nothing`. Then, mid-game:

```
gain_coins  → TypeError: '<' not supported between instances of 'str' and 'int'
shuffle_deck → AbilityResolutionError: effect 'shuffle_deck' failed:
               unknown deck 'spaghetti'; the decks are loot, treasure, monster, room
```

The first is a naked Python error with no card, no file and no line. The second
at least names the effect. Both arrive when somebody plays the card, which for
a rare card in a thousand-game study means arriving on game 400.

For official content this barely shows: a human wrote each ability and there is
a test per card. For custom content it is *the* problem. An author's first
experience of a typo should be a sentence naming their file, not a traceback
out of the interpreter — and today the difference between those two outcomes is
whether the mistake was in a name or in a number.

**This is the single most valuable thing to build**, and it is not a card
editor. Effects are registered with a signature the registry could read; the
same vocabulary pass that checks `gain_coins` exists could check that its
arguments are the shape `gain_coins` takes.

### Gap 2 — a card-id collision escapes the report and lands mid-play

Two expansions, `set_a` and `set_b`, each defining a card called
`shared-loot-collision`:

```
LOADED — the pipeline did not object: 3 expansions
but the registry did: DuplicateCardError - card 'shared-loot-collision' is already registered
```

Duplicate ids are caught *within* one expansion, with a file name and a report
entry. Across expansions they are not: `CardRegistry` catches it, correctly,
but it is built by `Game.from_content`, so the error arrives with no file, no
expansion, no report and no way to tell which of the two sets to blame.

Two people naming a card the same way is the ordinary case for custom content,
not the exotic one.

---

## 3. The recommended format

```
my_expansion/
    manifest.json
    cards/
        loot.json
        treasure.json
```

Card files may be laid out however the author likes — the loader walks the
directory — and abilities go inside the cards.

### Each question, answered

**A manifest: yes, required.** It is what makes a folder a set rather than a
folder. Without one the engine would have to infer identity from a directory
name, and two people's `custom` folder would collide the moment they were
shared. It is already required and already validated.

**A version: yes, and it is a claim rather than a proof.** `content_version` in
a journal is built from manifest versions — `base_game@1.0.0,my_set@0.2.0` —
which is exactly as trustworthy as the author who typed it. That is worth
having and is not enough on its own; see identity below.

**An author: optional, and metadata.** It says who to ask, it changes nothing,
and it belongs beside `description` in the manifest.

**An expansion id: yes, and it is the namespace.** Already required, already
unique across a library, already checked against every card's `expansion`
field.

**Dependencies: the mechanism exists and is unused.** `Manifest.requires` is
declared, `check_dependencies()` enforces it, `ContentLibrary.only()` calls it,
and **no shipped expansion declares one**. Leave it. A set that genuinely needs
another can say so; nothing needs building.

**Name conflicts: two levels, one of which is missing.**

- *expansion ids* collide loudly and correctly — `_register` reports
  `expansion 'x' is defined twice` with the directory;
- *card ids* collide silently until a game is dealt. That is Gap 2, and fixing
  it is a check in the loader, in the report, naming both files.

For new sets the convention that makes collisions structurally impossible is
**prefix every card id with the expansion id**. It cannot be made a rule
retroactively — `loot_deck-1-base_game-a_penny` carries its set in the middle,
not at the front, and 1045 cards are spelled that way — so: recommend it in
documentation, enforce global uniqueness in the loader, and do not migrate
anything.

---

## 4. Identity: how a journal knows it was *this* set of cards

Three different claims, and they are not interchangeable.

| | what it is | what it proves | cost |
|---|---|---|---|
| **expansion id** | the namespace | which set was asked for | free, exists |
| **manifest version** | what the author says they shipped | nothing, unless the author is careful | free, exists |
| **content digest** | a hash over every definition the game was dealt from | the cards were byte-for-byte these cards | 18 ms per library, **does not exist** |

A journal today records `content_version` — `id@version` per set. If somebody
edits a card in their own expansion without bumping the version, the journal
says the same thing about two different games.

What saves it today is the digest chain: replaying such a journal fails at the
first command, because the position fingerprint differs. Verified earlier
against a library with one card removed — it fails at entry 0. So the engine
never *believes* a wrong replay. What it cannot do is say why, and "left the
game in a different state" is a poor answer to give somebody whose real problem
is that they edited a card yesterday.

**Recommendation: add a content digest beside `content_version`, and keep both.**
Measured, not estimated: a hash over 1045 definitions — ids, types, printed
numbers, and every ability tree — takes **18 ms**, is stable across reloads, and
moves when a single card is removed. It is computed once per library, and a
study worker loads its library once, so it is 18 ms per worker rather than per
game.

The version stays because it is the human-readable half. The digest is the half
a machine can check.

**Snapshot or reference?** Reference. The scenario question was settled the
other way — a journal carries the whole scenario inside it, because a scenario
is a few hundred bytes and an experiment must survive its file being deleted.
Content is not comparable: 1045 definitions is megabytes, it would dwarf the
journal it travelled in, and the cards are not the experiment. A journal should
say precisely *which* content, and be able to prove it when the content is put
in front of it. That is a digest, not a copy.

This is the one place where the custom-content story is weaker than the
scenario story, and it should be said plainly: **a scenario is reproducible
from its journal alone; an experiment using custom cards is reproducible from
its journal and the expansion it names.** Anything else means putting a card
database inside every journal.

---

## 5. What the DSL can already express

### The numbers

Read out of the live engine by `engine_vocabulary()`, which is what content is
validated against:

**70 effects · 44 conditions · 46 targets · 66 triggers.**

Of the 70 effects, **48 are used by shipped cards and 22 by none**. The
vocabulary is wider than the content, not narrower.

### The coverage table

| Mechanic | Supported | Evidence |
|---|---|---|
| Coins, damage, healing, killing | yes | `gain_coins`, `lose_coins`, `set_coins`, `transfer_coins`, `deal_damage` ×79, `heal`, `kill` ×12 |
| Loot: draw, discard, pass, play | yes | `draw_loot`, `discard_loot`, `discard_cards`, `pass_hands` |
| Treasure: gain, destroy, steal, give | yes | `gain_treasure`, `destroy_treasure` ×17, `steal_treasure`, `give_treasure` |
| Souls | yes | `gain_soul`, `lose_soul`, `steal_soul`, `claim_soul` |
| Dice | yes | `roll_dice`, `modify_roll`, `set_roll`, `reroll`, `flip_roll` |
| Deck order — top, bottom, N from the top | yes | `move_cards` ×48, `depth_from` |
| Search, reveal, shuffle | yes | `take_card` ×15, `reveal_cards` ×16, `reveal_hand`, `shuffle_deck` |
| Counters on cards | yes | `add_counter` ×17 |
| Temporary and permanent bonuses | yes | `add_modifier` ×60, statics ×38 |
| **Choice** | yes | `choose` ×22, `may` ×33 |
| **Conditions** | yes | `if` ×108, 44 conditions, `and`/`or`/`not` |
| **Repetition** | yes | `for_each` ×2, `repeat` — the second exists and no card uses it |
| **Delayed effects** | yes | `watch_for` ×7, `promise` ×4, and `state.watchers` outlives the card |
| **Replacement effects** | yes | 25 abilities, `modify_event`, `cancel_event`, `prevent_damage` |
| **Triggered abilities** | yes | 66 event types; `on_activate` ×109, `on_play` ×81, `monster_killed` ×40 |
| Ability costs | yes | `coins` ×7, `counters` ×7, `tap`, `hp`, `discard` |
| Scope — self, controller, anybody | yes | `self` ×69, `controller` ×58, `any` ×55 |
| Abilities from outside play | partly | `zone` exists; one card uses `monster_discard` |
| Copying | partly | `copy_ability`, `copy_card`, `copy_effect` — but not the card currently being played |
| A cost that requires a choice | **no** | blocks *Contract from Below* |
| A replacement that asks a question | **no** | blocks *Sacred Heart* |
| Redirecting somebody else's death penalty | **no** | blocks *Shadow* |
| The `Indomitable` keyword | **no** | not written down in any specification |

### The finding that matters

**The DSL is not the bottleneck.** The base game — the set that defines the
mechanics — is **265 of 287 cards implemented, 17 with no rules printed on
them, and 5 left**. Every one of those five is blocked by a named engine
capability recorded in `PROJECT_PLAN.md` §11.5, not by missing vocabulary:

```
Blank Card           copying the card currently being played
Contract from Below  an ability cost that requires a choice
Sacred Heart         a replacement ability that can ask a question
Shadow               the death penalty is paid by whoever died
The D10              (not yet written up)
```

The 667 outstanding official cards are whole expansions nobody has started —
Requiem 246, Warp Zone 99, Four Souls+ 90, Gold Box 64 — and are transcription
effort, not engine capability.

**So a custom author is not going to run out of DSL.** They are going to run
out of patience with error messages, which is Gap 1.

---

## 6. Templates

The idea is worth having, and the shape it should take is not the obvious one.

**Not a parser.** "Gain 3¢" is easy and *"when this deals combat damage, cancel
everything that hasn't resolved and end the turn"* is not, and a parser that
handles the first and fails the second is worse than none: it teaches people to
expect something it cannot do.

**Not a UI.** That is a separate stage with a separate risk, and a template
layer that only exists behind a form cannot be used by anyone scripting a set.

**A library of worked examples, shipped as data, is the right first form.**
Concretely: a folder of small, complete, *loadable* card files, each one a
mechanic — a coin card, a damage card, a card with a choice, a card with a
condition, a card that waits for an event, a card with a cost, a passive
static. They validate in CI like everything else, so they cannot rot. Somebody
writing a set copies the nearest one and edits it.

That is a generator in the only sense that matters — it generates DSL by being
DSL — and it costs a folder plus a test that loads it. If a form is ever built
on top, it builds on these, and if it is not, the examples are still the
documentation that the effect registry cannot be.

**What would make templates genuinely more than examples** is Gap 1: once an
effect can say what arguments it takes, the same information documents it, and
a list of effects with their parameters is most of what a template picker
needs. One piece of work, two payoffs. That is an argument for doing the
validation first and the templates second, and never the other way round.

---

## 7. Test plan

The seven asked for, plus what the analysis says is missing from them.

| | Test | Passes today? |
|---|---|---|
| 1 | a custom expansion loads | **yes** — proved |
| 2 | its card reaches the right deck | **yes** — proved |
| 3 | its card can be played and does what it says | **yes** — proved |
| 4 | the effect survives a replay | untested; should hold — the DSL is the same interpreter |
| 5 | same expansion + seed → same journal | untested; should hold |
| 6 | editing a card moves the content digest | **no** — there is no content digest |
| 7 | two expansions with conflicting ids are refused | **partly** — expansion ids yes, card ids only when a game is dealt |

Five more the analysis says are worth as much:

8. **an effect given the wrong kind of argument is refused at load**, naming
   the card and the file — the whole of Gap 1;
9. **an effect given an argument out of range** — a negative count, an unknown
   deck — is refused the same way;
10. **a scenario naming a custom expansion replays from its journal**, with the
    expansion present: the chain end to end;
11. **the same journal against edited content fails loudly and says the content
    differs**, rather than only that the position does;
12. **the worked examples all load**, so the templates cannot rot.

All of them must build their content in `tmp_path`. A test in this project has
written into `content/` before.

---

## 8. Staging, and what not to do

**Stage A — argument validation.** The effect registry learns what each effect
takes; the semantic pass checks it; a bad card is refused by name and file
before any game exists. Nothing about the format changes, no migration, and
every existing card is a test case that must still pass. *This is the whole of
what makes custom content usable, and it is worth doing alone.*

**Stage B — identity.** A content digest beside `content_version` in the
journal, and a replay that diverges says whether the content differs. Cheap:
18 ms per library, measured. Journal format is already 2 and the field is
additive; whether that needs a 3 is a decision to take then, on the same
grounds as last time — an older build that ignores a digest is not misled by
it, so probably not.

**Stage C — card-id uniqueness in the loader.** A report entry naming both
files instead of a `DuplicateCardError` from nowhere. Small, and only worth
doing once B exists to give it a reason.

**Stage D — worked examples.** A folder of one-mechanic cards, loaded by a
test. Best after A, because A gives them their parameter documentation.

### What not to do

- **A text parser.** Named in the constraints and correct: the second half of
  the coverage table is why.
- **A card editor or any UI.** Separate stage, separate risk, and it would
  build on a validation layer that does not exist yet.
- **Putting content in the journal.** A scenario is small and the experiment;
  content is large and is not. Naming it and proving it is the job.
- **Making the card schema richer to accommodate custom sets.** Every field
  added is a field the engine has to keep reading forever. The five blocked
  base-game cards need engine capabilities, not schema.
- **Migrating existing card ids to a prefix rule.** 1045 cards, no benefit that
  a loader check does not deliver for free.
- **Treating `_abilities.json` as a public format.** It is scaffolding for the
  official import and would be a second file to keep in sync for everybody
  else.
