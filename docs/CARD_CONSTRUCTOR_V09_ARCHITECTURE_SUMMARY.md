# Card Constructor v0.9 — what was proven, and where the edges are

A consolidation of twelve analyses and the six implementation stages they led
to. It rewrites nothing and overturns nothing: where two source documents
disagree, the later measurement stands and the disagreement is recorded rather
than tidied away.

Measured at `f2c028e`. Every figure below was re-measured against the tree as
it now stands, not carried over from the stage that first found it.

```
cards            1045 readable   352 with rules   352 stable   352 checker-clean
card kinds       12 declared     12 offered
effects          63              refused by the guided walk: none
structures       choose for_each if may repeat sequence stop
                 mode worked_out named_count change
```

## Source material

| document | landed in |
|---|---|
| `COVERAGE_MAP` | `ae595fb` |
| `CARD_KINDS_PLAN`, `CARD_TYPE_MODEL_PLAN`, `CARD_TYPE_MIGRATION_PLAN` | `ae595fb` |
| `PROMISE_PLAN` | `10fc0ed` |
| `PROMISE_MAP_PLAN` | `17c0214` |
| `GUIDED_WALK_PLAN`, `DRAWS_PLAN`, `WHEN_PLAN` | uncommitted |
| `REWARDS_PLAN`, `REWARDS_PRESERVATION_PLAN`, `OPEN_MAPPING_PLAN` | uncommitted |

Implementation: `4c900f1` (card types), `08b89a8` (change operations),
`c8bc2e8` (named change maps), `bff6cd0` (guided walk), `f2c028e` (renderer
coverage invariant).


## 1. The architectural principles v0.9 proved

Not features. These are the rules that decided every stage, each stated with
the measurement that established it.

### 1.1 A fact belongs to the layer that owns it, and to one place there

*Measured:* `CARD_KINDS` was a hand-written six beside a correct twelve that
`runtime/vocabulary.py` already published **in the same HTTP response**. The
editor drew all twelve; only the opening screen drew six.

The rule has a second half that the same stage proved, and it is the half that
is easy to miss: **the layer that owns the fact is not always the model.**
`DRAWS` looks like the same mistake and is not — `shown` is the model's answer
to what kind of question a field is, and `DRAWS` is the page's answer to which
of those it has a control for. A different client would answer the second
differently while reading the same model. Publishing it from the model would be
the model claiming to know what its readers can draw.

**Corollary, proven twice:** where a fact is genuinely the page's, the
protection is a test, not a migration. `f2c028e` asserts that the two still
meet without either owning the other.

### 1.2 Describing a structure is safe exactly when the runtime refuses what the description omits

The single most load-bearing rule found, and the one that decided four separate
questions.

| structure | runtime, given a key the description omits | safe to describe? |
|---|---|---|
| `ability.cost` | refuses — `unknown cost 'eggs'` | yes, and it is |
| `promise.changes` (inner) | refuses — `a change is one of …` | yes, and it is |
| `card.rewards` | **keeps and ignores, on purpose** | **no** |

*Measured:* describing `rewards` and letting the writer honour it lost
`future_reward` from a real card, on disk, with `saved: True` and nothing said.

The rule explains why `promise` was publishable and `rewards` is not, without
either answer being about `promise` or `rewards`.

### 1.3 A declaration without the reader that honours it is worse than no declaration

*Measured, in the `watch_for` stage:* `a_list_of` was declared without the
reader, and two cards were silently emptied — `conditions: []`, `effects: []`,
then the keys vanished — and `check_card` passed the emptied cards.

Every stage since has landed declaration and reader together. It is also why
the `REWARDS_PLAN` prototype's apparent success was a false positive: the
writer was ignoring the declaration it had just been given.

### 1.4 Round-trip safety is the metric; editable-card count is not

*Measured:* the coverage map put all 164 constructs the engine declares through
reader → writer → reader. All 164 held, none refused, none unstable, none
changed meaning. That number decided that no representation gap remained, and
every stage after it was about publication rather than capability.

Where the two metrics pulled apart, safety won: `rewards` would add structured
editing to 255 cards and is refused because it can lose a key on one.

### 1.5 An open structure must not be partially described without preservation semantics

*Measured:* the Constructor has three states — refuse, keep-because-undescribed,
drop-because-described — and no fourth. Preservation exists only as an absence
of description.

### 1.6 Measure before deciding, and let the measurement overturn the plan

This is a process rule and it earned its place. Four approved directions were
reversed by measurement mid-stage:

- the step-binding placement rule was wrong, and the stage stopped rather than
  improvise;
- `names_several: bool` became `names_at_least: int` when `values_equal` needed
  two;
- `REWARDS_PLAN` recommended implementing and `REWARDS_PRESERVATION_PLAN`
  overturned it with a data-loss measurement;
- `putable` turned out not to be the only gate on the guided walk.


## 2. The Constructor model, concept by concept

### Published safely, unchanged

| concept | state |
|---|---|
| **`store`** | published from `EffectSpec.stores` — the effect's own statement that it produces a value. Not a list kept anywhere. |
| **`watch_for`** | `a_list_of` + `holding=`; declaration and reader landed together after the silent-emptying measurement. |
| **`change`** | the six operations, built by walking `CHANGES` in the applier's order. `cap`, `floor` and `flip` had appeared in no published shape, and three of the four shipped promises use one. |

### Published after migration

| concept | problem | what changed | unresolved |
|---|---|---|---|
| **`CardType`** | a hand-written six beside a published twelve; six kinds unreachable when creating a card, and reachable-but-raw when editing (`Your bonus_soul`) | `TYPE_LABELS` moved into `cards/types.py`; `catalogue()["kinds"]` derived; `CARD_KINDS` deleted | none. `starting_item` also regained the `used_by` shortcut the engine always declared and the desk discarded |
| **`promise.changes`** | a JSON textarea; no word for a map of a described kind | `each_shaped_like` — several nodes of one kind, each under a name the card chooses | none for `changes` |
| **guided walk** | two gates that disagreed by accident; `promise` and `watch_for` offered nothing | `asks()` — one predicate both gates share; a required answer is asked wherever the shape puts it | a step **inside** `watch_for.effects` cannot be aimed — pre-existing, §5.1 |
| **`DRAWS`** | ten enumerations of eight words; two had already drifted and passed | three assertions; the drifted copies now read the page's own list | none |

### Intentionally left opaque

| concept | why |
|---|---|
| **`promise.when`** | `A_MAPPING`'s claim that the inside cannot be judged is **true** here, in both halves: the names are event fields (open — `compost` changes one nothing proposes) and the values are whatever the event carries. One shipped card, everything round-trips. |
| **`card.rewards`** | open key space **by design** — *"so a future reward type does not invalidate existing content"*. Describing it loses what it omits. 255 cards round-trip exactly today. |
| **`card.metadata`** | the engine never reads it. There is nothing to describe. |

### Requires a future concept

| concept | what is missing |
|---|---|
| **partially described mappings** | a way for a shape to say *"I name these and keep the rest"*. `a_list_of`, `shaped_like` and `each_shaped_like` all mean the shape is exhaustive. Needed only if structured `rewards` is ever wanted. |
| **step-local bindings** | landed as Variant B and works; the placement question inside a `watch_for` body is open — §5.1. |


## 3. Rejected approaches, and the measurement that killed each

| approach | why it looked reasonable | what disproved it |
|---|---|---|
| **`a_list_of` for a named map** | `changes` holds several of a described kind, and `a_list_of` is how the language says that | `UnreadableCard: 'changes' should be a list and is not` — both shipped cards refused |
| **`shaped_like` for a named map** | `ability.cost` is a mapping that says what shape it is | it means *the mapping **is** one node*. Rendered live: the page asked the six operation questions at the top level with **no box for the field name**, and removed the textarea that could express the card. `compost` became unwritable, silently |
| **`shaped_like` for `rewards`** | the same mapping-of-numbers shape as `cost` | end to end, on disk: `{"loot":1,"future_reward":7}` → edit `loot` → `{"loot": 4}` saved, reported successful, nothing said |
| **deriving event fields from the engine** | only six events are ever proposed, carrying eleven fields — a small, static set | `source` on `before_loot_draw` is proposed by nobody and appeared in **0 of 105,936** events across 30 played games. It exists only once a replacement writes it. Any derivation loses `compost` |
| **making `DRAWS` model-owned** | it looked like `CARD_KINDS` | the model does not know what controls a client has, and should not. Measured instead: 0 of 168 shapes undrawable, the guard filters nothing, and both options render identically |
| **treating `when` as a condition** | `watch_for` answers a similar question with real conditions | a watcher **builds an ability**; a promise builds nothing. `_event_value` returns False without a context, and `_keep_promises` has none. Adopting it is a runtime change, not a declaration |
| **widening `putable` alone** | it was the obvious gate | `finishable` would go true while `questions` still skipped the field — the walk would offer an action and never finish it |


## 4. The v0.9 safety invariant

> **A card the Constructor accepts must round-trip without changing its
> author-visible meaning, and a card it cannot represent must be refused rather
> than altered.**

Held for **352 of 352** cards with rules, and for all 164 constructs the engine
declares.

**"Meaning" includes:** every effect, condition, target and control node, with
its parameters; where each name is bound and when the player is asked for it
(an ability's list resolves before any step runs, a step's own when that step
runs); the names an author chose; the order of every list; and every key of
every mapping a card writes.

**Acceptable loss** — normalisation that changes the file and not the card:
the `id`, rewritten from set, type and name for every card; a short spelling
written long; an empty body omitted where the builder would omit it.

**Not acceptable, and the line the rewards analysis drew:** a key the card
wrote and the engine keeps, removed because a form did not draw it. That is a
change of meaning even though nothing in the engine reads the key.

**Intentionally unsupported:** the three effects that edit the event their
ability is handed (`cancel_event`, `modify_event`, `prevent_damage`) — a fact
about them, since the walk makes an ordinary ability and an ordinary ability is
not handed one; and the 693 cards with no rules at all, held back by a
deliberate authoring nudge in `check_card`.


## 5. Remaining risks, measured

### 5.1 Step-local binding placement inside a watched body

*Why it exists:* `watch_for.effects` is in `BRANCHES`, so a name bound outside
is not visible inside. A step in there that picks its own target has its
binding placed on the ability, and the checker refuses the card with the rule
stated.

*Measured:* pre-existing in `build_card`, independent of the walk stage, and
reachable through the expert editor today.

*Blocks v0.9?* **No.** No shipped card is affected; the checker refuses rather
than corrupting.

*Future stage:* where a step-local binding is written when the step is inside a
branch that is itself a body.

### 5.2 Open-mapping preservation

*Why it exists:* `_written_node` rebuilds a nested node from `shape.params`.

*Measured:* `_NESTED_SHAPES` has four entries and **three are dead** — the
branch fires for exactly one parameter in the whole language, `ability.cost`,
which is the one case where the runtime refuses unknown keys.

*Blocks v0.9?* **No.** The only structure that would fail is `rewards`, and it
is not described.

*Future stage:* `OPEN_MAPPING_PLAN` §8 — gated on wanting structured `rewards`.

### 5.3 Guided walk coverage

*Measured:* refuses nothing but the three replacement effects. `promise` and
`watch_for` are reachable and finishable.

*Blocks v0.9?* **No.**

*Remaining:* the walk cannot aim a step inside a body — §5.1, the same
question.

### 5.4 Promise event-field modelling

*Why it exists:* `promise.event` offers all 66 triggers where six can be
promised against, and a field name is free text.

*Measured:* the six proposed events carry eleven fields between them — and
`source` is in none of them. Any published list would be wrong.

*Blocks v0.9?* **No.** Every promise round-trips.

*Future stage:* only with a way to state a field that exists solely because a
replacement writes it.


## 6. Future work required, versus deliberately not implemented

### Future work required — the architecture cannot express the concept

- **Partially described mappings.** Needed only if structured `rewards` is
  wanted. No existing declaration says it, and all three nesting words mean the
  opposite.
- **Step-local binding placement inside a body.** The engine has the behaviour
  and the writer places the binding where the checker will not accept it.

### Deliberately not implemented — analysis proved it unsafe or unneeded

- **Structured `rewards`.** Unsafe: measured data loss on a real save.
- **A `when` editor.** Unnecessary: one card, everything round-trips, the
  model's description is correct and complete, the gain is cosmetic.
- **Open-mapping mechanism, now.** Unneeded: one failing structure, one live
  branch, one parameter.
- **`DRAWS` changes.** Unneeded: the fact is correctly located; only the
  copies were wrong, and they are fixed.
- **Further guided-walk work.** Unneeded for coverage; what remains is §5.1,
  which is a different question.


## 7. Verdict

**1. Is the architecture fundamentally sound?**

Yes, on the strongest evidence available: 164 of 164 constructs round-trip
without changing meaning, 352 of 352 rules-carrying cards are stable and
checker-clean, and 1000 replayed games are identical to the baseline after
every stage. No stage found a representation gap. Every stage that found
something found a *publication* gap, a *copy*, or a *routing* mistake — and
each was fixed by removing something rather than adding a mechanism.

**2. Are the remaining problems missing concepts or implementation bugs?**

One of each, and they are small. **Missing concept:** a shape that names some
keys and keeps the rest — required only by a feature that is not wanted.
**Implementation bug:** step-local binding placement inside a body, which
refuses loudly rather than corrupting.

Two smaller inconsistencies were found and left, both recorded: a `mode`
carrying an unknown key passes the checker and the reader will not open it; and
the card shape's docstring claims unknown top-level fields are kept, which is
true of the checker and false of the reader.

**3. Is v0.9 blocked by any proven semantic gap?**

**No.** The invariant in §4 holds for every card the Constructor accepts. The
one structure that could break it is not described, and the analysis
recommending that it stay that way is the reason.

**4. What is the highest-risk next stage?**

**Anything that describes an open structure** — `rewards` first among them. It
is the only line of work measured to lose author-visible content, it does so
silently, and it reports success while doing it. The risk is not difficulty; it
is that the failure is invisible at every layer except the file on disk.

The second-highest is step-local binding placement, because it touches the
name-visibility model — the one part of the language where placement is
semantic rather than cosmetic, established when the binding stages measured
that an ability's targets resolve before any step runs and a step's own resolve
when that step runs.

Neither is recommended here. Both are recorded so that whoever takes one starts
from measurement.
