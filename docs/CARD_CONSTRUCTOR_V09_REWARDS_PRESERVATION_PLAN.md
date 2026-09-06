# `rewards` — describing an open map loses what it does not describe

Control analysis before implementation. Nothing in `src/`, `tests/` or
`content/` was changed, nothing was committed. Measured at `f2c028e`. Every
number below is measured; none is predicted.

Runtime execution, `when`, `promise`, step-local bindings, the guided walk and
`DRAWS` were not touched. Scratchpad prototypes were built, measured and
removed.

`docs/CARD_CONSTRUCTOR_V09_REWARDS_PLAN.md` is unmodified. **This document
overturns its §5 conclusion**, and says where that conclusion went wrong.


## 0. What this changes about the previous analysis

The previous stage prototyped a `rewards` node, measured that an unknown key
survived, and concluded the risk had not materialised. **That measurement was
correct and the conclusion drawn from it was wrong**, because the prototype
tested a configuration in which the writer *ignores* the declaration it had
just been given.

The writer honours `shaped_like` only for four node kinds:

```python
_NESTED_SHAPES = (COST, NAMED_COUNT, WORKED_OUT, MODE)
```

`rewards` was not among them, so `_written_node` fell through to the
plain-value branch and copied the mapping verbatim. The page, meanwhile,
honours `shaped_like` unconditionally and drew three boxes. **The preservation
came from the two halves disagreeing**, not from a mechanism.

With `rewards` added to that tuple — the writer doing what the declaration
says — the answer inverts.


## 1. The preservation contract

> *If the runtime accepts an unknown rewards key, must the Constructor
> preserve and allow editing that key even though it has no structured control
> for it?*

**The Constructor makes no such guarantee anywhere, and has no mechanism for
it.** Measured across the three cases that could have provided one:

| case | what the Constructor does |
|---|---|
| an unknown key at the top of a card (`artist_note`) | **refused**: *"This card says 'artist_note', which the engine does not describe."* |
| an unknown key inside an **undescribed** mapping (`metadata`) | **kept**: `{"text": "x", "whatever": [1, 2, 3]}` |
| an unknown key inside a **described** mapping (`cost`) | **dropped, silently**: `{"tap": true, "eggs": 2}` → `{"tap": true}`, checker **clean** |

So the only thing in the Constructor that preserves what it does not describe
is **not describing it**. There is no "described but preserved" state, and no
convention for one.

Two related findings fall out of the same measurement.

**The card shape's docstring overstates the reader.** `_node_shapes` says *"at
the top of a card file an unknown field is kept, because a set may carry an
artist credit or a schema version this engine has never heard of."* That is
true of the **checker** and false of the **reader**, which raises
`UnreadableCard`. Out of scope here; recorded because it was measured while
looking for a preservation mechanism.

**`cost` already behaves the way this stage fears** — and correctly. It drops
`eggs` on rewrite. That is harmless because the runtime refuses the key
outright:

```
KINDS the runtime accepts as a cost: coins, counters, discard, hp, tap
unpayable(... cost={'eggs': 2} ...)  ->  "unknown cost 'eggs'"
```

A card carrying that key could never be played. Dropping it loses nothing.


## 2. Which behaviour publishing would produce

Both configurations were run through the real reader and writer.

**Configuration 1 — the declaration present, `rewards` not in `_NESTED_SHAPES`
(what the previous stage measured):**

| card writes | written back | unknown kept | stable | checker |
|---|---|---|---|---|
| `{"loot": 1}` | `{"loot": 1}` | — | yes | clean |
| `{"loot": 1, "eggs": 2}` | `{"loot": 1, "eggs": 2}` | **yes** | yes | clean |
| `{"eggs": 2}` | `{"eggs": 2}` | **yes** | yes | clean |
| `{"loot": 1, "future_reward": 7, "cents": 3}` | identical | **yes** | yes | clean |

**Configuration 2 — the writer honouring the declaration:**

| card writes | written back | unknown kept | stable | checker |
|---|---|---|---|---|
| `{"loot": 1}` | `{"loot": 1}` | — | yes | clean |
| `{"loot": 1, "eggs": 2}` | `{"loot": 1}` | **no** | yes | **clean** |
| `{"eggs": 2}` | `null` | **no** | yes | **clean** |
| `{"loot": 1, "future_reward": 7, "cents": 3}` | `{"cents": 3, "loot": 1}` | **no** | yes | **clean** |

Note the third row: a card whose only reward is an unknown key loses the
**whole field**. It pays nothing, and the checker calls it clean.

**Answer to Task 2: configuration 1 is B (preserve but hide); configuration 2
is C (structured editing replaces the mapping). Neither is A.** Which one you
get is decided by a four-entry hardcoded tuple in the writer, and nothing in
the declaration says which you are asking for.


## 3. End to end, through the browser and the save path

The critical case, driven through the real page against a real desk serving
configuration 2, then read back **off disk**:

```
state before editing      : {"loot":1,"future_reward":7}
state after changing loot : {"loot":4,"future_reward":7}     ← the page kept it
saved                     : True
card written              : {"loot": 4}
ON DISK                   : {"loot": 4}
```

`saved: True`, no problem reported, and `future_reward` is gone from the file.

**The page preserves and the writer drops.** An author who opened a card to
change one number, changed it, and pressed save has silently deleted a reward
they never saw and were never told about.


## 4. Where preservation would have to live

Not the runtime model: the runtime already keeps unknown keys and says why.

Not the advanced JSON editor: it is what would be replaced.

Not the generic mapping renderer: the page already preserves — measured, the
state kept `future_reward` through the edit. The page is not where it is lost.

**It is the writer**, `_written_node`, which rebuilds a nested node out of the
shape's parameters and therefore writes exactly what the shape describes.
That is correct behaviour for a closed shape and wrong for an open one, and
the shape has no way to say which it is.

**No existing mechanism covers it.** The three candidates measured in §1 are
the only ones, and they are: refuse, keep-because-undescribed, or
drop-because-described.


## 5. Why the answer differs from `cost` and `changes`

| | key set | what the runtime does with an unknown key | can it be described closed? |
|---|---|---|---|
| `ability.cost` | closed, 5 | **refuses** — `unknown cost 'eggs'` | yes, and dropping is harmless |
| `promise.changes` | open names, **closed inner set** | **refuses** the inner key — `a change is one of …` | yes, and Stage Promise 1 did it |
| **`card.rewards`** | **open by design** | **keeps and ignores**, stated in the docstring as the reason | **no — describing it closed contradicts the contract** |

The pattern that made the previous stages safe is exact: *the runtime refuses
what the description omits.* Then a writer that rebuilds from the description
can only drop things the runtime would have rejected anyway.

`rewards` breaks that pattern in the one way that matters. The runtime
deliberately keeps what the description would omit — *"so a future reward type
does not invalidate existing content"* — so a writer that rebuilds from the
description destroys exactly the content that sentence exists to protect.

**So `shaped_like` cannot be used here as it stands.** It would turn an open
runtime structure into a closed authoring structure, which is the thing this
stage was set up to check for.


## 6. `souls`

> *Should `souls` be considered part of this analysis, or remain a separate
> card-level field?*

**Separate, and it needs nothing.** Measured:

- **Runtime**: `_pay_rewards` reads `definition.souls` — a card field — and puts
  it in the same `before_rewards` payload as the three reward keys. The payout
  loop then pays all four. So the four are one structure **at the event**, not
  at the card.
- **Card definition**: `souls: int = 0`, a field of its own. `rewards`' own
  docstring draws the line: *"What defeating this card pays out, **beyond its
  printed souls**."*
- **Validation**: the integer check for card-level numbers covers it; the
  `rewards` value check does not touch it.
- **Shipped content**: **no card writes `souls` inside `rewards`** — 255 cards
  carry rewards, none of them that key.
- **Published**: `kind='a whole number'`, `role='amount'`, `asked='more'`,
  `default=0`. Fully described and editable already.

Nothing is missing, so nothing is owed. Whether the form should show the four
numbers together is a visual question and explicitly not decided here.


## 7. Classification

**Mixed — C now, and only D gets out of it. Not B.**

- **The description itself is A-shaped**: which three names the runtime
  understands, and that the values are whole numbers, are facts the engine
  holds in `_pay_rewards`, the annotation and the validator, and publishes
  nowhere. That half is straightforwardly publishable.
- **B is false as a matter of measurement.** The category assumes a
  preservation mechanism already present in the Constructor. §1 shows there is
  none: the only preservation is being undescribed. Configuration 1 looks like
  B but is two components disagreeing, not a mechanism — and nothing in the
  declaration expresses the intent, so nothing protects it.
- **C is where the tree stands today**, and is the correct answer if nothing
  new is built: `rewards` stays `advanced`, an author sees and can edit every
  key, and no content is at risk.
- **D is what a structured `rewards` requires**: a way for a shape to say *"I
  describe these, and keep what I do not"*. That is one new idea, and it is not
  the same as any of `a_list_of`, `shaped_like` or `each_shaped_like` — all
  three of which mean the shape is exhaustive.

The honest one-line statement: **the previous stage's B was a misreading of a
fall-through; the real choice is C or D.**


## 8. The success criterion

> *A card containing an unknown reward key must not silently lose that key
> merely because the author edits a known reward.*

**Measured false** under a structured `rewards`, end to end, on disk:
`{"loot":1,"future_reward":7}` → edit `loot` → `{"loot": 4}` saved, reported
successful, nothing said.

**The current architecture cannot satisfy the invariant without a new concept.**
The three states available are refuse, keep-because-undescribed, and
drop-because-described. The invariant needs a fourth, and there is not one.

Not solved here, as instructed. What such a concept would have to say, stated
only so the next stage has something concrete to judge: *the parameters named
are the ones this shape knows; a key it does not name belongs to the card and
is written back untouched.* That is a claim about the shape, not about the
renderer, and it would need the writer to honour it — which is the same
`_written_node` branch that drops keys today.


## 9. Recommendation

**Do not implement structured `rewards` as `shaped_like`.** It would trade a
JSON box that shows everything for three boxes that silently delete anything
else, and the runtime's own docstring is the reason that trade is wrong.

Either:

- **leave it as it is** — the C answer, costing nothing and losing nothing; or
- **decide the D question first**, on its own terms, because "a described shape
  that keeps what it does not describe" is not a `rewards` feature. It would
  apply to any open-key structure the engine gains, and `rewards` is simply the
  first one to ask for it.

If D is wanted, it should be its own analysis, and it should start from the
writer — `_written_node` and `_NESTED_SHAPES` — because that is where the loss
happens and where the fourth state would have to exist.

**Priority: low, and lower than it looked.** No card is at risk today, no key
is lost today, and the only thing that changes if nothing is done is that
`rewards` keeps a JSON box that is honest about what it holds.


## 10. Scratchpad

Two prototypes were built, measured and removed: a vocabulary substitution
running the real reader and writer under both configurations, and a desk served
from the patched catalogue for the browser test. The probe set they wrote was
deleted. Nothing under `src/`, `tests/` or `content/` was touched at any point.
