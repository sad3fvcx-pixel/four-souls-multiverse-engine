# Partially described mappings — is the fourth state needed?

Architecture analysis. Nothing in `src/`, `tests/` or `content/` was changed,
nothing was committed. Measured at `f2c028e`. Every finding below is measured;
scratch prototypes were built, measured and removed.

`when`, `promise`, step-local bindings, the guided walk, `DRAWS`, runtime
semantics and shipped content were not touched. Neither `REWARDS_PLAN.md` nor
`REWARDS_PRESERVATION_PLAN.md` was modified.

**Short answer to the stage's central question: the fourth state is not needed,
because the thing that would need it does not exist.** The reasoning is
measured, and the most surprising part is §2.


## 1. Is the problem general?

**No. There is exactly one structure in the language with the failing
combination, and it is `rewards`.**

Every mapping a card may write, measured — three fields on the three card
dataclasses, and five published parameters whose kind is a set of named values:

| mapping | runtime key space | what the runtime does with an unknown key | is there a subset to describe? |
|---|---|---|---|
| `ability.cost` | **closed**, 5 | **refuses** — `unknown cost 'eggs'` | yes, and it is described |
| `promise.changes` | outer open, **inner closed** | **refuses** the inner key | yes, and it is described |
| `promise.when` | open | keeps — nothing is read by name | **no** — the engine names nothing |
| `card.metadata` | open | never read at all | **no** — the engine names nothing |
| **`card.rewards`** | **open by design** | **keeps and ignores**, and says why | **yes — three names** |

The failing combination needs all three columns: an open key space, a subset
the Constructor could describe, and a runtime that keeps what it ignores.
`when` and `metadata` fail the third column — there is nothing to describe, so
they are correctly opaque. `cost` and `changes` fail the second — the runtime
refuses what a description would omit, which is exactly what makes describing
them safe.

**The rule underneath all of it**, and it is the one worth carrying forward:

> Describing a mapping is safe exactly when the runtime refuses what the
> description omits.

`cost` and `changes` obey it. `rewards` is the single case that does not.


## 2. `_NESTED_SHAPES` is a whitelist, and three quarters of it is dead

This is the finding that decides the stage.

```python
_NESTED_SHAPES = (COST, NAMED_COUNT, WORKED_OUT, MODE)
"""
The named shapes a field may hold one of, as opposed to a target.
"""
```

Its own docstring makes no claim about key closure — it distinguishes nested
shapes from targets, which is a statement about *which writer path*, not about
semantics.

Measured, across every published parameter in the language, which of the four
is ever reached through `parameter.shaped_like` — the only way the branch
fires:

| entry | carried on `shaped_like` by | reached? |
|---|---|---|
| `cost` | `ability.cost` — **one parameter** | **yes** |
| `named_count` | nothing; offered only via `also` on `cost.counters` | **no** |
| `worked_out` | nothing; offered only via `also`, on 70 parameters | **no** |
| `mode` | nothing; reached via `a_list_of` on `choose.modes` | **no** |

**The branch that reconstructs a described mapping fires for exactly one
parameter in the whole language: `ability.cost`.** And `cost` is precisely the
case where the runtime refuses unknown keys, so reconstruction can only discard
what could never have been played.

The four behaved four different ways when given an unknown key, which is how
the deadness showed:

| shape | checker on the card as written | the key after a rewrite |
|---|---|---|
| `cost` | refuses it | **dropped** — the branch fires |
| `named_count` | refuses it | kept — the branch never fires |
| `worked_out` | refuses it | kept — the branch never fires |
| `mode` | **clean** | **the reader refuses the card**: *"This mode says 'eggs', which the engine does not describe."* |

So `_NESTED_SHAPES` is **an implementation whitelist, not a semantic concept**.
It has one live entry, and that entry happens to be safe.

(The `mode` row is a separate inconsistency, noted and not pursued: the checker
accepts a card the reader will not open. Out of this stage's scope.)


## 3. Is there an existing preservation concept?

**No. Stated explicitly, as the stage asks.**

Searched for opaque data, unknown fields, passthrough, extra keys, partially
described mappings, preserved originals, raw/advanced fields, lossless editing.
What exists:

- **`PASSTHROUGH`** (`content/vocabulary.py:808`) — a *target* that hands back
  whatever it was given. Nothing to do with data preservation.
- **`role = STRUCTURE`** — *"nested data whose inside this layer does not
  describe"*. That is the opaque state, state 2, and it is the only thing that
  preserves anything.
- **`OPENED`** (`author.py:55`) — which file a card came from, carried back
  untouched. About identity, not content.

The three observable behaviours are the three the stage named, and the only
preservation among them is *being undescribed*.


## 4. The options, measured rather than argued

### A — keep open mappings opaque

What the tree does today. `rewards` is a JSON box; every key is visible,
editable and preserved; round-trip is exact for all 255 cards carrying rewards.

Cost: no structured editing for three known numbers. That is the whole cost.

### B — an explicit partial-mapping shape

A declaration saying *"I describe these keys and keep the rest."* What it would
have to mean, path by path — and §5 is why this list is short:

- **reader**: nothing. It already passes a mapping through raw (measured
  below).
- **author state**: nothing. It already holds the whole mapping.
- **writer**: everything. `_written_node` would consult the declaration instead
  of rebuilding unconditionally.
- **checker**: nothing. It already accepts unknown reward keys.
- **UI**: nothing structural — it already preserves through an edit.
- **round-trip**: the guarantee it would restore.

### C — merge unknown keys generically in the writer

Prototyped in scratch: rebuild what the shape names, then copy back what it
does not. Measured on every axis the stage listed:

| case | written back | stable second rewrite |
|---|---|---|
| `{"loot": 1}` | `{"loot": 1}` | **yes** |
| `{"loot": 1, "eggs": 2}` | `{"loot": 1, "eggs": 2}` | **yes** |
| `{"eggs": 2}` | `{"eggs": 2}` | **yes** |
| `{"loot": 1, "future_reward": 7, "cents": 3}` | `{"cents": 3, "loot": 1, "future_reward": 7}` | **yes** |

| operation | result |
|---|---|
| changing a known key | `{"loot": 4, "future_reward": 7}` — unknown survives |
| deleting a known key | `{"future_reward": 7}` — works |
| deleting the unknown key | `null` — works, *from state* |
| ordering | described first in shape order, unknown appended — deterministic |
| key collisions | impossible: one namespace, and the merge only fills what the shape does not name and the rebuild did not produce |

**C is safe on every axis measured.** Two honest qualifications:

1. **The unknown key is deletable only in principle.** The deletions above were
   made by editing author state directly. A person has no control for a key the
   form does not draw, so C fixes silent loss and leaves the key invisible and
   unmanageable — better than deletion, not good.
2. **C applied generically changes `cost`.** It is the one live case, so the
   blast radius is a single parameter: `{"tap": true, "eggs": 2}` would keep
   `eggs` instead of dropping it. The checker refuses that card either way, so
   the author is told rather than silently edited — arguably better, and still
   a behaviour change to an existing shape.

### D — an existing mechanism

**None.** §3. Nothing in the repository expresses this, and inventing one on
the strength of a single hypothetical card would be the abstraction this stage
was told not to invent.


## 5. Where preservation belongs — the writer, and locally

> *Is "unknown key preservation" a property of the runtime model, the
> Constructor model, or the writer?*

**The writer, and it can be specified locally by a shape.** Measured on both
sides of the described/undescribed line:

```
author state for rewards (undescribed)              : {"loot": 1, "future_reward": 7}
author state for cost    (described)                : {"tap": true, "coins": 2}
author state for a cost carrying an unknown key     : {"tap": true, "eggs": 2}
```

The reader passes a mapping through **raw in every case**, described or not,
unknown key or not. Author state holds the whole mapping. Nothing is lost in
reading, and nothing is lost in state.

**It is lost in exactly one place**: `_written_node`, which rebuilds a nested
node out of `shape.params` and therefore writes precisely what the shape names.

So the general author-state representation would not change. That is a real
constraint on any future design and it makes B small — a declaration the writer
reads, not a new kind of state.

(The one path that *does* lose information earlier is `_read_inside`, used for
nodes reached through `a_list_of` — it raises on an unknown key rather than
keeping it. That is the `mode` row in §2, and it is a different mechanism from
the mapping path.)


## 6. Does this belong in v0.9?

The criterion is:

> every supported card should round-trip without changing author meaning; cards
> requiring a new semantic concept remain refused.

**v0.9 already meets it, and the way to keep meeting it is to do nothing.**

All 255 cards carrying rewards round-trip exactly today, because `rewards` is
opaque. No card is refused for wanting a concept the language lacks. The only
thing that would put the criterion at risk is describing `rewards` — which is
how this stage started.

So: **not a v0.9 requirement, and not merely optional either — it is a change
that would make v0.9's guarantee harder to hold, in exchange for three number
boxes.** Judged on semantic safety rather than editable-card count, the answer
is not close.


## 7. Recommendation for `rewards`

**Keep it opaque.** Not "defer until a general mechanism exists" — defer
implies the mechanism is wanted and merely early. On the measurement, it is not
wanted:

- the failing combination exists in **one** place (§1);
- the machinery that would fail is **one live branch** guarding **one
  parameter** (§2);
- nothing in the language expresses partial description, and nothing else needs
  it (§3);
- the gain is three number boxes on a field 255 cards already write correctly;
- the cost is a data-loss class the architecture currently does not have.

The JSON box is honest about what it holds. That is worth more here than a form
that is prettier about three keys and silent about a fourth.


## 8. The smallest future stage, if it is ever wanted

**Not justified today.** Recorded so a future decision starts from measurement
rather than from scratch, and gated on somebody actually wanting structured
`rewards`.

**Semantic contract.** A shape may say it names *some* of a mapping's keys.
Where it does, the writer writes what it names and copies back what it does
not. Where it does not, nothing changes. The claim is about the shape, not the
renderer, and the model still says nothing about what the unnamed keys mean.

**Affected model concepts.** One new field on `ParamShape` or `NodeShape`,
alongside `a_list_of` / `shaped_like` / `each_shaped_like` — all three of which
mean the shape is exhaustive, which is why none of them fits.

**Affected paths.** `_written_node`'s `_NESTED_SHAPES` branch, and
`_NESTED_SHAPES` itself, whose meaning would have to become explicit — three of
its four entries are dead and its docstring describes a different distinction
from the one it is being asked to carry.

**Required tests.** An unknown key survives a rewrite; survives an edit to a
known key; is deletable by whatever control is provided; a second rewrite is
stable; `cost` behaves exactly as it does today, or the change to it is
deliberate and stated.

**Required browser test.** The case this whole line of analysis came from:
open a card with an unknown key, change a known one, save, and read the file
back off disk.

**Compatibility.** No card JSON changes; no runtime changes; `_pay_rewards`
untouched; the 255 shipped cards byte-identical.

**Explicit non-goals.** Not a general refactor of `_NESTED_SHAPES`. Not
`metadata`, which has nothing to describe. Not `when`, which has nothing to
describe. Not a control for keys the engine does not understand — if one is
wanted, that is a separate question, and without it the key stays invisible.


## 9. Answers to the stage's six closing questions

1. **Measured findings**: `_NESTED_SHAPES` has one live entry of four;
   preservation is lost only in `_written_node`; the reader and author state
   keep everything; option C is stable and safe on every axis, at the price of
   changing `cost` and leaving unknown keys unmanageable.
2. **Is the problem general?** No — one structure, `rewards`, and one live
   branch. The *mechanism* would fail the same way for a future open-key
   shape, but no such shape exists.
3. **Is a new semantic concept required?** Not for anything that exists. It
   would be required only to make `rewards` structured, which §7 recommends
   against.
4. **`rewards`**: keep opaque.
5. **Smallest future stage**: §8, recorded and not justified today.
6. Stopping here.
