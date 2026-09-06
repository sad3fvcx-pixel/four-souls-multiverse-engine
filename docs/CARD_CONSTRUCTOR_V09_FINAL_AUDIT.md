# Card Constructor v0.9 — final semantic audit

Audit only. Nothing in `src/`, `tests/` or `content/` was changed, nothing was
committed, nothing was pushed. Measured at HEAD `6d68f96`. Every number below
was measured against the tree as it now stands; none is carried over from an
earlier document, and where an earlier document is contradicted this one says
so and shows the measurement.

`rewards`, `when`, open mappings, `promise`, `DRAWS`, the Guided Walk
implementation and the step-binding implementation were read, not modified.
`setAim` was out of scope. Scratch corpora and probe sets were built outside
the repository, measured, and removed.

**The audit found one real v0.9 blocker.** It is stated in §4 and §6 and
classified in §11. Everything else measured clean.


## 1. Baseline

Measured from the repository, not from the previous summary.

| | measured | previous summary | why it differs |
|---|---|---|---|
| card definitions | **1045** | 1045 | — |
| cards containing rules | **352** | 352 | — |
| readable | **1045 / 1045** | 1045 | — |
| stable (second write == first) | **1045 / 1045** | 352 stable of the rule cards | the earlier figure counted only rule-bearing cards; all 1045 are stable |
| checker-clean | **352 / 352 rule cards** | 352 | the other 693 carry no rules and the checker says so deliberately |
| editable (opens **and** saves) | **1014 / 1045** | not previously measured | §1.1 |
| refused at read | **0** | 0 | — |
| view-only (reads, will not save) | **31** | not previously measured | §1.1 |

Published constructs, read off the catalogue:

| | count |
|---|---|
| card types | 12 (`TYPE_LABELS` also 12) |
| effects | 70, of which 7 are control nodes with no parameter shape |
| conditions | 44 |
| targets | 46 |
| triggers | 66 |
| node shapes | 15 |

Sets discovered: 24. The corpus loader used here is the engine's own
`ContentLoader._expansion_directories`, so the `_abilities.json` sidecars are
skipped exactly as the engine skips them.

### 1.1 The 31 view-only cards

`content/custom/engine_demo` ships 31 cards (23 rule-bearing) whose identifiers
contain a dot — `engine_demo.the_tinkerer`. `A_PLAIN_NAME` is
`[a-z0-9][a-z0-9_-]*`, and `build_card` runs every identifier arriving through
`OPENED` past it, because an identifier becomes a file name.

Reproduced on the real desk API, with the set copied into an author's own sets
directory:

```
opened OK, marker: engine_demo.the_tinkerer
SAVE REFUSED -> AuthorError: 'engine_demo.the_tinkerer' is not the name of a card.
```

This is a **loud refusal**: nothing is written, and what is on disk is what was
there before. It is also unreachable in ordinary use — the Constructor only
opens cards from `sets_directory()`, never from `content/`, and every
identifier it mints is a plain name. A card can only carry a dotted identifier
by being imported from outside. Classified **D** in §11, with an **E**
component: the message says "is not the name of a card" about an identifier the
author never typed.


## 2. Exhaustive construct round-trip

Every published construct, exercised by a synthesised minimal card and driven
through readable → represented → writable → checker-clean → stable. Not a
sample: every name in the catalogue.

| category | readable | represented | writable | checker-clean | stable |
|---|---|---|---|---|---|
| effects (excl. control nodes) | 63/63 | 63/63 | 63/63 | **63/63** | 63/63 |
| control nodes | 7/7 | 7/7 | 7/7 | **7/7** | 7/7 |
| conditions | 44/44 | 44/44 | 44/44 | **44/44** | 44/44 |
| targets | 46/46 | 46/46 | 46/46 | **46/46** | 46/46 |
| triggers | 66/66 | 66/66 | 66/66 | **66/66** | 66/66 |
| card-level structures | 8/8 | 8/8 | 8/8 | **8/8** | 8/8 |
| **total** | **234/234** | **234/234** | **234/234** | **234/234** | **234/234** |

The card-level structures are `ability.cost`, `statics`, `rewards`, `souls`,
`tags`, `metadata`, `health`/`attack`/`roll`, and `promise` with `when`.

A first pass reported 13 constructs as not clean. Every one of the 13 was the
synthesiser producing an under-specified node — an empty `may`, a replacement
effect under a trigger that is not a replacement, `values_equal` given one name
instead of two — and in every case the checker's refusal was correct. The
figures above are from the corrected synthesiser, which gives each construct a
genuinely valid minimal card.


## 3. Exhaustive shipped-card round-trip

All 1045 cards through original → reader → author state → writer → checker →
second read/write. Nothing sampled.

- readable **1045/1045**, no card half-read
- writable **1014/1045** (the 31 of §1.1)
- stable **1045/1045** — the second write equals the first for every card
- checker-clean **352/352** of the rule-bearing cards

A field-level diff of original against written flags 1045 cards, which is
expected and is not a result: reading is canonicalising by design — short
spellings are written long, bindings are named. A structural diff cannot
distinguish that from a change of meaning, so it was not used as the oracle.

**The oracle used instead was the engine.** The whole corpus was rewritten
through the Constructor into a separate content root and replayed.

| corpus | games differing from control |
|---|---|
| control — an untouched copy of `content/` | **0 / 200** |
| whole corpus rewritten through the Constructor | **58 / 200** |

The control being clean establishes that the harness and the baseline are sound
at this HEAD. The 58 are §4.


## 4. Silent data loss

This is the finding.

### 4.1 The blocker — an inline target is hoisted into `ability.targets`

When a card writes a target inline on an effect, the reader lifts it into a
binding at `ability.targets` and points the effect at the bound name. The
timing invariant the step-binding stage established is that `ability.targets`
resolve **before** any effect runs, whereas a step's own `targets` resolve when
that step runs. Hoisting therefore moves *when* the target is chosen.

Measured, on a card that ships today — `loot_deck-pills_runes-base_game-pills-v2`:

```
original : {"if": [{"dice_greater": 4}],
            "then": [{"effect": "discard_cards", "target": "target_loot"}]}

written  : "targets": [{"target_loot": {"as": "chosen_1"}}]        <- ability level
           {"if": [{"dice_greater": {"value": 4}}],
            "then": [{"effect": "discard_cards", "target": "chosen_1"}]}
```

The card printed "on a 5–6, discard a loot card". After a round trip it asks
for the loot card **every time it is played**, including on a 1–4 where nothing
is discarded.

End to end through the real desk, opening the card and saving it **with no edit
at all**:

```
saved: True   problems: []
```

and the file on disk now carries the ability-level `targets`. Accepted, saved
successfully, meaning changed on disk, nothing said.

**Isolation.** Rewriting only that one card changes 22 of 150 games. Rewriting
it identically but undoing *only* the hoist changes 0 of 150. So every other
canonicalisation the Constructor performs — `roll_dice: 6` to
`effect`/`sides`, `dice_less: 3` to `{"value": 3}`, `draw_loot: 1` to `count` —
is meaning-preserving, and the hoist is not.

**Scale.** Across the whole corpus:

| corpus | games differing |
|---|---|
| rewritten, hoist left in | 58 / 200 |
| rewritten, every hoist undone | **0 / 200** |
| rewritten, only branch hoists undone | 5 / 200 |

Undoing every hoist restores exact behavioural identity. So the hoist is the
**sole** cause of every behavioural difference the Constructor introduces
across 1045 cards.

**Which hoists matter.** The dominant case is a target written inside a
conditional or optional branch — `then`, `else`, `may`, a `choose` mode,
`sequence`, `repeat`. 42 shipped cards write one:

| branch | abilities |
|---|---|
| `then` | 38 |
| `choose` | 10 |
| `may` | 8 |
| `effects` | 1 |
| `else` | 1 |

Undoing only those leaves 5 games differing, so the branch case is the large
majority but **not the whole of it**. The residual bisected to a single card,
`treasure_deck-one_use_items-base_game-mom_s_shovel`, whose diverging ability
hoists a `target: "self"` written at a step's own top level, not in a branch.
Undoing that one ability's hoist removes the divergence. **A top-level hoist
can change play too**, so the defect is the hoist itself, not only the branch
case.

Every hoisting scope was measured directly:

| where the target is written | binding placed at | resolves |
|---|---|---|
| `may` body | ability level | up front |
| `if` → `then` | ability level | up front |
| `if` → `else` | ability level | up front |
| a `choose` mode | ability level | up front |
| `sequence` body | ability level | up front |
| `repeat` body | ability level | up front |
| `watch_for` body | **inside the body** | when the body runs |
| the ability's own top level | ability level | up front |

`watch_for` is correct — that is what `6d68f96` fixed, and this audit confirms
it still holds. The row above it is the same class of error one scope out:
`BRANCHES` members get the treatment `NEW_SCOPE` members no longer get.

Confirmed in the browser on ten representative real cards. Six of the ten
gained ability-level targets on a no-op open-and-save; all ten saved clean;
no page errors. §10.

### 4.2 An unknown cost key is dropped silently

Second silent case, and much smaller. Driven end to end:

```
opened, author state : {"tap": true, "eggs": 2}
save result          : saved: True, problems: []
ON DISK              : {"tap": true}
```

`eggs` is gone and nothing was said. It is harmless in the sense that matters:
the runtime refuses such a cost outright — `unknown cost 'eggs'` — so no
playable card can lose anything this way, and the checker refuses the card as
written before it is ever opened. Classified **D**.

### 4.3 Everything else preserves

Systematically, across mappings, lists, named structures, optional fields,
nested structures, bindings, control nodes, card-level fields, open structures,
unknown keys, and empty or `None` values:

| case | kept? | checker on the written card |
|---|---|---|
| `rewards` with an unknown key | **yes** | clean |
| `rewards` holding *only* an unknown key | **yes** | clean |
| `metadata` with an unknown key | **yes** | clean |
| `promise.when` with an unknown key | **yes** | clean |
| `promise.changes` with an unknown **field name** | **yes** | clean |
| `promise.changes` with an unknown **operation** | no | refused — §5 |
| `ability.cost` with an unknown key | **no** | clean — §4.2 |
| `tags` with an unknown tag | **yes** | clean |
| `ability.scope` | **yes** | clean |
| empty `rewards` / empty `metadata` / empty `targets` | **yes** | clean |
| zero-valued numbers, `souls: 0` | **yes** | clean |
| a `None` inside `metadata` | **yes** | clean |

So the only two places anything is lost are §4.1 and §4.2, and only §4.1
changes the meaning of a card that can actually be played.


## 5. Reader / checker consistency

Every case measured at this HEAD.

**Checker accepts, reader refuses — 2 cases.**

1. **A mode carrying an unknown key.** Checker clean; reader refuses with
   *"This mode says 'eggs', which the engine does not describe."* This is the
   inconsistency `OPEN_MAPPING_PLAN.md` §2 recorded, and it is still here.
   The card is refused loudly at the moment it is opened, so nothing is lost.
   **D.**
2. **An unknown field at the top of a card.** Checker clean; reader refuses
   with *"This card says 'artist_note', which the engine does not describe."*
   `REWARDS_PRESERVATION_PLAN.md` §1 predicted exactly this and it is
   confirmed. The card shape's own docstring says such a field "is kept",
   which is true of the checker and false of the reader. **E** — the
   implementation is coherent, the docstring describes it wrongly.

**Checker rejects, reader accepts — 1 case.**

3. **An unknown `cost` key.** Checker refuses (*"'eggs' is not part of a
   cost"*); the reader accepts and the writer drops it. Harmless, because the
   runtime refuses the same key. This is §4.2 seen from the other side. **D.**

**Checker accepts, runtime refuses — 1 case, and it is new.**

4. **A promise change carrying an unknown operation.** Measured:

   | | result |
   |---|---|
   | checker on the card as written | **CLEAN** |
   | reader | accepts |
   | writer | **drops the whole `changes` mapping** |
   | checker on the written card | refuses — *"'promise' needs 'changes'"* |
   | runtime | `EffectExecutionError: promise cannot change 'value' by {'set': 1}; a change is one of …` |

   Empty `changes` behaves the same way: checker clean, runtime refuses.

   **This contradicts `REWARDS_PRESERVATION_PLAN.md` §5**, which lists
   `promise.changes` as *"refuses the inner key"* and uses that to argue the
   structure was safe to describe. The **runtime** refuses it; the **checker**
   does not. The conclusion that stage drew — that `promise.changes` was safe
   to publish — still stands, because the writer rebuilds from a shape whose
   operations the runtime enforces, so nothing survivable is dropped. But the
   sentence about the checker was wrong, and it is corrected here rather than
   in that document.

   No card is at risk: the loss is caught by the checker on the way out, so
   `save_card` refuses and nothing reaches disk. The cost is a message that
   says a promise has no changes about a card that plainly has some. **D**,
   with an **E** component against the earlier document.


## 6. Writer scope audit

`_Chosen`, `_given`, `_written_node`, `_written_step`, `NEW_SCOPE`,
`BRANCHES`, `BY_BINDING`, `BY_THE_STEP` were read and then measured rather
than reasoned about. The question was whether the writer can still put a
binding somewhere the runtime cannot reach it, or reach it at the wrong time.

- **Unreachable scope: none.** `6d68f96` closed the `NEW_SCOPE` case, and it is
  confirmed closed: a target inside a `watch_for` body is written inside that
  body, the ability keeps no `targets`, and the checker is clean. `promise`
  holds no step list, so it cannot exercise the boundary at all.
- **Wrong-time scope: one, and it is §4.1.** Every `BRANCHES` member —
  `then`, `else`, `may`, `choose`, `modes`, `effects` — plus `sequence` and
  `repeat` has its target hoisted to the ability, where it resolves before the
  branch is known to run. So does a target at a step's own top level.

Sibling bindings, shadowing and escaping bindings were exercised as part of the
1045-card round trip and the 234-construct sweep, and produced no unstable or
misplaced result. Two steps in one body still share what the first bound; a
name bound inside a `NEW_SCOPE` body still does not escape it.

The distinction the writer draws is between `NEW_SCOPE` and everything else.
The distinction the runtime draws is between *resolved with the ability* and
*resolved when the step runs*. Those are not the same line, and §4.1 is the
gap between them. **Recording the observation only — no fix is proposed here,
and none was made.**


## 7. Declaration completeness

The v0.9 problem class is a fact the runtime understands with no published
representation. Searched across the vocabulary, model, parameter and shape
declarations, references, checker and reader/writer.

**No declaration gap affecting a supported card was found.**

The one candidate turned out not to be a declaration gap at all. The promise
change operations *are* published — the `change` node shape carries all six
(`value`, `delta`, `factor`, `cap`, `floor`, `flip`), which is what Stage
Promise 1 landed. The event names are published for both `promise` and
`watch_for`, all 66. What is missing is not a declaration but **enforcement**:
the checker does not hold the published shape against a promise's changes.
That is §5 case 4, and it is a checker gap, not a model gap.

Applying the stage's own criterion — *does the missing fact prevent safe,
semantically faithful authoring of an otherwise supported card?* — the answer
for every construct measured is no.


## 8. Opaque structures

| | why it is opaque | round-trip preserves? | can editing a neighbour destroy it? | runtime contract | does v0.9 need more? |
|---|---|---|---|---|---|
| `rewards` | the runtime keeps unknown keys **by design**, so a shape that named three keys would delete the fourth | **yes** — including a `rewards` holding only an unknown key | **no** — measured: the unknown key survives a rewrite | **open** | **no** |
| `when` | the engine names nothing inside it, so there is no subset to describe | **yes** — an unknown key survives | no | open | no |
| `metadata` | never read by the engine at all | **yes** — an unknown key, and a `None` value, both survive | no | open | no |

All three still satisfy the rule the earlier chain reduced to: *describing a
structure is safe exactly when the runtime refuses what the description omits.*
None of the three qualifies, and none is described. The `rewards` conclusion is
unchanged and is restated as instructed: **do nothing unless structured
rewards are explicitly wanted.**


## 9. Guided Walk

Verified after `bff6cd0` and `6d68f96` by running the page's own `walkable()`
in a real browser against every rule-bearing shipped card — the page's
predicate, not a re-derivation of it.

```
total rule cards : 352
walkable         : 352
not walkable     : 0
threw            : 0
page errors      : []
```

- **Reachable**: every construct any shipped rule card uses.
- **Intentionally editor-only**: structures shown as `advanced` — `rewards`,
  `when`, `metadata` — which the walk does not ask about and the editor shows
  in full.
- **A required structured answer that cannot be asked**: none found.
- **A finishable card incorrectly blocked**: none — 0 of 352.
- **Can the walk cause semantic loss?** Not of its own. It writes through the
  same `build_card` as the editor, so it inherits §4.1 and nothing besides.

**No Guided Walk correctness blocker.**


## 10. Browser verification

Ten representative real shipped cards, served by a real desk from a copy of the
cards in an author's own sets directory. Each opened, inspected, given a
harmless supported edit, saved, and read back off disk. Shipped content was not
touched: the probe set was a copy outside the repository, and it has been
removed.

| case | card | saved | problems | changed on disk |
|---|---|---|---|---|
| cost + ordinary effect | `crystal_ball` | yes | 0 | spelling only |
| choice / nested | `compost` | yes | 0 | no |
| binding | `xii_the_hanged_man` | yes | 0 | spelling only |
| may | `devil_deal` | yes | 0 | **gained ability targets** |
| nested branch | `cursed_chest` | yes | 0 | **gained ability targets** |
| statics | `the_bone` | yes | 0 | **gained ability targets** (2 abilities) |
| card type | `curse_of_the_blind` | yes | 0 | no |
| opaque structure (`rewards`) | `big_spider` | yes | 0 | **gained ability targets**; `rewards` intact |
| conditional target | `pills-v2` | yes | 0 | **gained ability targets** |
| effect + target | `xiii_death` | yes | 0 | **gained ability targets** |

`page errors: []` throughout. No page error, correct placement in the
`watch_for` sense, checker clean everywhere, every result stable. The one thing
that is not correct is the hoist, on six of ten cards, silently — §4.1.


## 11. Classification of findings

| # | finding | class |
|---|---|---|
| 1 | An inline target is hoisted into `ability.targets`, so it resolves before the branch that uses it is known to run. 42 shipped cards write one inside a branch; 58 of 200 replayed games change; open-and-save with no edit is enough to do it; `saved: True`, `problems: []`. | **A — real v0.9 defect** |
| 2 | An unknown `ability.cost` key is dropped on save with nothing said. The runtime refuses such a cost anyway, so no playable card loses anything. | **D** |
| 3 | A promise change with an unknown operation passes the checker, is dropped by the writer, and is then refused by the checker on the way out. The runtime refuses it too, so nothing reaches disk. | **D** |
| 4 | `REWARDS_PRESERVATION_PLAN.md` §5 says the checker refuses an unknown promise-change key. The **runtime** does; the checker does not. | **E** |
| 5 | A `mode` carrying an unknown key passes the checker and the reader refuses to open the card. | **D** |
| 6 | An unknown field at the top of a card passes the checker and the reader refuses to open it; the card shape's docstring says such a field is kept. | **E** |
| 7 | 31 shipped `engine_demo` cards with dotted identifiers open and cannot be saved. Loud refusal, nothing written, and unreachable without importing the set by hand. | **D**, with an **E** for the message |
| 8 | `rewards`, `when` and `metadata` are opaque and every round-trip preserves them. | **C — correct as it stands** |

No finding was classified **B**. Nothing measured requires a new language or
model concept: finding 1 is a placement error inside the existing scope model,
not a missing one.


## 12. Final v0.9 verdict

**Is v0.9 semantically complete for its declared scope? NO.**

One demonstrated blocker, finding 1. Everything else is clean.

| | |
|---|---|
| Supported constructs | **234 / 234** |
| Supported rule cards | **352 / 352** readable, represented, writable and checker-clean |
| Stable | **1045 / 1045** |
| Checker-clean | **352 / 352** rule cards |
| **Silent data-loss cases** | **2** — one that changes a playable card's meaning (finding 1), one that cannot (finding 2) |
| **Known writer placement defects** | **1** — finding 1 |
| Known declaration gaps affecting supported cards | **0** |
| Known reader/checker disagreements | **3** — findings 3, 5, 6 |
| Guided Walk correctness blockers | **0** |

The audit did **not** find a scattering of small problems. It found that
everything the Constructor does to a card is meaning-preserving except one
transform, and that undoing that single transform makes 1045 rewritten cards
behave identically to the originals across 200 replayed games — 0 differing.

That is the whole of it, and it is a blocker: a card can be opened and saved
with no edit at all, be reported saved with no problems, and play differently
afterwards.


## 13. Remaining issues, explicitly non-blocking

None of the following blocks v0.9, and none is proposed as work here.

- **Finding 2** — an unknown `cost` key vanishes silently. Only reachable with
  a key the runtime already refuses.
- **Finding 3** — the checker does not hold the published `change` shape
  against a promise's changes, nor refuse empty `changes`. Caught on save.
- **Finding 5** — a `mode` with an unknown key: checker clean, reader refuses.
  Recorded in `OPEN_MAPPING_PLAN.md` §2 and still true.
- **Finding 6** — the card shape's docstring overstates the reader.
- **Finding 7** — dotted identifiers cannot be saved, and the message blames a
  name the author never typed.
- **Finding 4** — one sentence in `REWARDS_PRESERVATION_PLAN.md` §5 is wrong
  about the checker. That document's conclusion is unaffected and stands.

`REWARDS_PLAN.md`, `REWARDS_PRESERVATION_PLAN.md`, `OPEN_MAPPING_PLAN.md`,
`WHEN_PLAN.md`, `DRAWS_PLAN.md`, `GUIDED_WALK_PLAN.md`,
`STEP_BINDINGS_PLACEMENT_PLAN.md` and `ARCHITECTURE_SUMMARY.md` were read and
not modified.


## 14. Method

- Corpus enumerated with the engine's own `ContentLoader`, so the sidecar
  files it skips are skipped here too.
- Constructs enumerated from `engine_vocabulary()`, not from a list kept here.
- The semantic oracle was the engine: `stress/mass.py` with the content root
  made settable, 200 games at 4 players, records compared with `seconds` and
  `journal_bytes` ignored. A control run against an untouched copy of
  `content/` differed from `stress/mass_baseline.jsonl` in **0 of 200** games,
  which is what makes the other runs readable.
- Divergences were bisected to a single card rather than attributed.
- The Guided Walk was measured by running the page's own predicate in a
  browser, not by re-implementing it.
- Scratch corpora, the probe set and the temporary sets directories were built
  outside the repository and removed. `a.out` was not touched.
