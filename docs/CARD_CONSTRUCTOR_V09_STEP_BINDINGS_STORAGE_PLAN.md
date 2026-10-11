# Card Constructor v0.9 — what author state must remember about a binding

The previous design placed a binding where its readers could see it. That rule
is withdrawn: **placement decides when the player is asked**, so it is a fact to
preserve, not a thing to recompute. This asks what author state has to hold
instead.

Analysis only. Nothing was changed. Measured at `bcf7b4a`.

**Conclusion: one bit per binding — whose it is, the ability's or the step's.**
Everything else is derivable from the walk. No persistent scope object, no
scope identity, no change to the card language, and nothing new in the card
format.

---

## 1. The timing invariant

Two sites, and they are the whole of it.

**An ability's targets are resolved before the ops exist** — before any step
runs, whether or not the step that reads one is ever reached:

```python
if ops is None:
    self._target_resolver.resolve_all(ability.targets, self._state, context, self._rng)
    ops = self._interpreter.build(ability.effects)
```

**A step's own targets are resolved when that step runs**, and the comment
beside it says why the difference matters:

```python
if op.asks:
    # Questions this effect asks for itself, in the order written: a
    # card that swaps two cards must ask about the first before it can
    # sensibly ask about the second.
    self._targets.resolve_all(op.asks, context.state, ability, context.rng)
```

So there are exactly **two timings**, and a binding has one of them by virtue
of where it is written:

| written | asked |
|---|---|
| the ability's `targets` | before any step runs |
| a step's `targets` | when that step runs |
| inline in a step's `target` | when that step runs |

Measured: **inline and a step's list are indistinguishable to the engine.**
Both enter the arm's namespace, both are visible to later steps in that arm,
and both are refused outside it:

| | |
|---|---|
| inline binding, read by a later step | accepted |
| step-list binding, read by a later step | accepted |
| inline inside a `may`, read after the `may` | refused |

So the two rows that matter are **ability** and **step**. Inline versus list is
a difference of shape, not of meaning.

---

## 2. The placement invariant

A round trip must preserve, together:

```
authored name  +  owner/placement  +  scope  +  ordering
```

and **placement is not readership**. The measurement that settles it:

| | |
|---|---|
| ability-level bindings in shipped content | 98 |
| …read by exactly one step | **86** |
| …of those, whose single reader sits **inside a branch** | **77** |

Under "put it where its readers can see it", 86 of 98 would move onto their one
reading step, and 77 would move inside a `may`, an `if` or a mode — asked later
than the card asks them, and in 77 cases not asked at all when the branch is
not taken. That is a change of meaning to bindings that work today.

Placement therefore has to be remembered. Author state cannot remember it now:
the ability's `targets` is discarded on read (`_read_value` returns
`_NOT_AN_ANSWER` for a list of targets) and rebuilt by gathering, so by the
time the writer runs, an ability-owned binding and a step-owned one look
identical — both are an `aim` with a word on some step.

---

## 3. A, B and C

### A — keep the ability's `targets` in author state

What breaks, measured rather than guessed:

- **The page would not draw it.** `fieldsHtml` draws only `asked ∈ {first,
  more, deeper}`; `ability.targets` is published `asked: "never"`, `shown:
  "body"`, `role: "body"`. Probed in the browser with a populated list: the
  targets body is **not drawn**, the name does not reach the page, no JS error.
  So A needs a publication change — `asked` must stop being `never`.
- **That change creates two places to say one thing.** An author could add a
  target to the ability's list *and* aim a step at its own choice. Nothing
  reconciles them, and `asked: never` is currently true for a good reason: the
  aim on a step is what asks the question.
- **A dead path with an unstable name goes live.** `_written_one` for a target
  writes `body["as"] = described.get("as") or f"chosen_{id(described) % 997}"`.
  Author state spells the authored word `name`, not `as`, so every entry would
  fall through to a name derived from a **memory address** — different on every
  run. Measured: author state holds a targets list for **0 of 332** readable
  cards today, so this path is unreached; A reaches it.
- **Mixing risk is real.** Nothing would stop an ability-level entry and a
  step-owned aim carrying the same word, and the two have different timings.

A is not impossible, but it is a bigger change than it looks and it opens a
double-entry problem that does not exist today.

### B — record who owns the binding, on the aim

The question is how little suffices.

- **Does it need a persistent scope ID?** No. Scope comes from the walk, and
  the walk is the same one the checker makes. Nothing is stored about scope.
- **Does it need the owning *step*?** No. The copy already lives on a step, so
  "this step's own" is positional and needs no name. A later step reading the
  same word finds it by the stack lookup, in walk order, before it could create
  a second.
- **Does it need branch information?** No, for the same reason: the branch is
  where the walk is.
- **Is `ability-owned | step-owned` enough?** Measured: **no word in any
  shipped ability is owned at both levels** — 179 bindings, zero clashes. So
  `(word, level)` is unambiguous and one bit is enough.

So B is: each aim in author state carries one fact — *the ability chose this*
or *this step chooses it*. Nothing else.

### C — only the 24 bindings a card already puts on a step

C still needs the same bit: the writer must not hoist those 24, and must tell
them from the 98 that look identical in state. So C costs what B costs and
delivers less — it leaves the **57 inline bindings** losing their authored word,
which is 37 cards. C is B with the benefit removed.

**Recommended: B.**

---

## 4. The minimal state, per binding

For all 179 bindings, what the writer needs and where it comes from:

| what | needed? | from |
|---|---|---|
| the authored **name** | yes | already in state as `aim_name` / `name`, except for inline bindings, which the reader discards today |
| **placement** (which timing) | yes | **the one bit** — not derivable, see §2 |
| **scope** | yes | derived: the stack of arms the walk is already in |
| **identity** (is this the same binding as that one) | yes | derived: `(word, current scope chain)`, which §3 shows is unambiguous |
| the owning **step** | no | positional — the copy sits on it |
| the owning **branch** | no | positional — the walk knows |
| a scope **ID** | no | nothing is stored about scope |
| inline versus a step's list | no | derivable from readership *within one timing*, which is safe because timing does not change: read only by its own step → inline; read by later steps in the arm → the step's list |

**One field. Two values.** Everything else is either already there or a
property of where the walk is.

### Stability under editing

The bit travels on the copy, which lives on the step, so no positional identity
is needed:

| edit | effect |
|---|---|
| insert a step | none |
| move a step | the bit moves with it; a step-owned binding follows its step into or out of a branch, and its timing follows correctly |
| edit a branch, change how many arms | none — copies move with their steps |
| delete the step that owns a binding a later step reads | the later step's copy still says *step-owned* and creates the binding at its own position. The card has changed, so the timing changing with it is right — but it is a behaviour to name, not a surprise to discover |

---

## 5. Why this does not change runtime semantics

Nothing in `runtime/`, `effects/`, `rules/`, `content/` or the card format is
involved. The bit exists only in author state, which no engine reads. What is
written back is card JSON of the same three shapes the language already has,
each carrying the timing the card had:

| the card wrote | state remembers | the writer writes | asked |
|---|---|---|---|
| the ability's `targets` | ability-owned | the ability's `targets` | before any step |
| a step's `targets` | step-owned | that step's `targets` | at that step |
| inline in `target` | step-owned | inline in `target` | at that step |

No binding crosses between rows. That is the whole guarantee.

---

## 6. How scope, timing and ordering are each kept

**Scope** — the writer carries a stack of gathering lists: push on entering an
arm, pop on leaving, look up through parents, create in the current one. That
is `visible = current + parents`, the model measured in the previous stage:
A, B and C legal; **D impossible**, because a popped list cannot be consulted —
and refused by the checker independently, which is what makes relaxing the
reader safe.

**Timing** — from the bit, never from readership. An ability-owned binding is
created in the root list whatever arm reads it; a step-owned one is created in
the arm the step is in.

**Ordering** — two rules, both already true of the walk:
1. a binding is created when first needed, and the walk visits steps in order,
   so a binding is always written on or before the step that reads it — which
   is what the checker requires (*a name read before it is bound is refused*);
2. within one step's `targets`, entries are written in the order the answers
   were read, which is what `swap_cards` depends on — *"a card that swaps two
   cards must ask about the first before it can sensibly ask about the
   second."* `finger` binds `mine` then `theirs` in one step's list; both stay
   step-owned, in that order, in that list.

---

## 7. The regression cards, checked against this model

| card | binding | owned by | asked | depth | reconstructed as |
|---|---|---|---|---:|---|
| `the_d20` | `rerolled` | ability | before any step | 0 | the ability's list — **one** binding, both readers resolve to it |
| `the_curse` | `top` ×3, `raised` ×3 | step (inline) | at the step | 3 | inline in three arms; three lists, never compared, **all six words kept** |
| `dead_bird` | `roller` | ability | before any step | 0 | the ability's list |
| | `snatched` | step (list) | at the step | 2 | that step's list, inside the `may` |
| `finger` | `roller` | ability | before any step | 0 | the ability's list |
| | `mine`, `theirs` | step (list) | at the step | 2 | one step's list, **in that order** |
| | `swap_pair` | step (inline) | at the step | 2 | inline, naming both |
| `g_fuel` | `woken` | ability | before any step | 0 | the ability's list |
| | `revived` | step (list) | at the step | 2 | that step's list |
| `pestilence` (alt) | `chosen` | ability | before any step | 0 | the ability's list |
| | `their_victim` | step (list) | at the step | 1 | that step's list |
| `pestilence` (base) | `first_point`, `second_point` | step (list) | at the step | 1 | one step's list |
| | `divided` | step (inline) | at the step | 1 | inline |
| `incubus` | `shown` | step (list) | at the step | 3 | that step's list |
| | `mine_card`, `their_card` | step (list) | at the step | 4 | one step's list, in order |
| | `swap_pair` | step (inline) | at the step | 4 | inline, naming both |
| | `returned` | step (inline) | at the step | 3 | inline |

`the_d20` is the test against "every step owns its binding": one ability
binding, two readers in different arms, and it must stay one. Under B it does,
because the bit says ability and the root list holds it.

`the_curse` is the test against ability-wide naming: six inline bindings, two
words, three arms each. Under B each arm's list is separate, so nothing is
compared and nothing is renamed.

`incubus` remains **not promised**. Its model is covered — every binding is
step-owned, and depth is only depth — but it is the deepest case, it has an
answer naming several, and one binding is read one arm further in. It has to be
measured, not assumed.

---

## 8. What is not settled here

The bit needs a name and a spelling in author state, and that is the first
thing implementation should propose rather than pick. This document does not
choose one.

Nor does it claim B is free of new concepts: **it is one new field in author
state**, which is exactly the thing the previous analysis said to stop and
describe. This is that description. It is not in the card format, not in the
runtime, and not a scope object — but it is a field, and adding it is a
decision to take deliberately.

Everything else in this stage is derivation from what the tree already knows.
