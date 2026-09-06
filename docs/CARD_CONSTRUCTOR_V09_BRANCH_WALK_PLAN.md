# Card Constructor v0.9 Stage 2.2 — walking through a branch

Stage 2.1 made a branching card legible. This asks the next question: can a
person be led through one by the rule the whole Constructor runs on —
**one question, one answer, the next question** — without a tree editor.

Analysis only. Measured against the engine at `aee72fc`. Nothing in `src/`.

---

## 1. What the branches actually are

All 74 cards whose author state holds a control node:

| | |
|---|---|
| control nodes in all | 138 |
| `if` | 104 · `may` 18 · `choose` 15 · `for_each` 1 |
| **cards where every node has exactly one arm** | **57 of 74** |
| cards where some node has more than one arm | **17 of 74** |
| cards with more than one such node | **1** |

Arms per node:

| | nodes |
|---|---|
| `if` with one arm (a `then`, no `else`) | 101 |
| `if` with two arms | 3 |
| `may` with one arm | 18 |
| `for_each` with one arm | 1 |
| `choose` with 2 / 3 / 5 / 6 modes | 7 / 6 / 1 / 1 |

And inside an arm:

| steps in one arm | arms |
|---|---|
| 1 | **150** |
| 2 | 17 |
| 7 | 1 |
| 0 | 1 |

Depth: **69 of 74 cards have no nesting at all**; 5 nest one level; none
deeper.

**So the answer to "how many cards need a real choice" is 17 of 74.** For the
other 57, a branch is a condition and a single path — there is no *which
branch* to ask, because there is only one. And in 150 of 169 arms, the path is
one step long.

---

## 2. The questions a control node carries — and the limit found here

Every field of every control node, by what the metadata says of it:

| node | its `asked: first` fields | `shown` |
|---|---|---|
| `if` | `then`, `else` | **body** |
| `may` | `effects` | **body** |
| `choose` | `modes` | **body** |
| `for_each` | `effects` | **body** |
| `mode` | `description`, `effects` | **form**, body |

The page draws a question when `putable(f)` — `asked !== "never"` **and**
`shown === "form"`. So:

> **No control node has a single first question the walk can draw.**
> Every one of them is a body — a list of other nodes — and the only `form`
> fields any of them carry (`description`, `prompt`, `optional`, `store`) are
> `asked: "more"`.

Two consequences, and the second decides this stage:

- **The walk cannot stop on a control node**; it has nothing to put there. It
  must pass *through* the node into its arm.
- **The condition itself is `asked: "never"`.** `if.if` and `if.conditions`
  are both `shown: body`, `asked: never`, and `for_each.of` is `asked: never`
  too. There is no question anywhere in the metadata that asks a person *what
  must be true* — so nothing can author a new branch today. That is not a
  screen that has not been written; it is a question the engine does not yet
  publish.

`choose` is the one that looked most likely to need a new control, and does
not: a mode is a published node with `description` as a `form`/`first`/
required field and its own list of steps. **A mode is a small part, and
`oneByOne` already draws parts like it.** No new kind of UI is needed for it.

---

## 3. The hand-off, checked rather than assumed

```
control node → an arm → a child step → the existing questions() → build_card
```

| question | answer |
|---|---|
| is a child step the same author state node? | **yes** — `{id, fields, groups}`, identical to a top-level step |
| does the order survive? | **yes** — an arm is a list, and order is list order |
| can the walk address it? | **yes** — `at(path)` splits on `.` and `[]` and reduces to any depth, so `…effects[1].fields.then[0]` already resolves |
| which part's bindings apply? | **the enclosing ability's** — `partAt` matches the `^state.card.fields.<list>[n]` prefix, so a nested path still finds the part that binds |
| is a separate state format needed? | **no** |
| can it go back? | **yes** — `walk.list` + `walk.doing` is a path and an index; an arm is just another path |

The one thing that is not ready: `walkable()` asks whether every step of a
part is an action the walk offers, and control nodes are published with
`a_step: true`, which the walk excludes — correctly until now, since it could
not finish one. **70 of the 74 have every *leaf* step already offered**; the
4 held back use `cancel_event` or `prevent_damage`, which belong to the
replacement stage.

---

## 4. What `build_card` already does with an edited branch

Measured, not reasoned: for every branching card that holds a number inside a
branch, that number was changed, the card rebuilt, checked, and read back.

| | |
|---|---|
| cards tried | **51** |
| rebuilt and refused by the checker | **0** |
| rebuilt but read back differently | **0** |
| rebuilt, stable, but the change dropped | **0** |

**The pipeline already supports editing inside a branch.** Nothing is lost, no
binding moves, nothing becomes unstable. This was the risk worth measuring
first, and it is not there — which means the stage is screens, not Python,
exactly as Stage 3B of v0.8 was.

---

## 5. The minimum first step

**Option A — open a branch and change a step already in it.** Chosen.

- **B, walk a branch in view mode**, adds almost nothing to Stage 2.1. The
  card is already legible; walking it read-only is a second way to look.
- **C, add branch *choosing* to the walk** in the sense of creating one, is
  blocked by §2: a new `if` needs its condition authored, and the condition is
  `asked: "never"`. Building it would mean inventing a question the engine
  does not publish, which is the thing this project stops and reports rather
  than doing.

A is what the measurements support: the pipeline already keeps such an edit
(§4), the addressing already reaches it (§3), 70 of 74 cards qualify, and for
57 of them there is not even a branch to choose — the walk passes through the
node into its one arm and asks the ordinary questions of the ordinary steps
inside.

For the 17 with more than one arm, one extra screen: *which of these?* — a
list of arms labelled by what the metadata already says (`what happens when it
is`, `…when it is not`, and for a `choose`, each mode's own description). That
is a list of words, like the parts screen, not a tree.

---

## 6. Order of implementation

1. **Widen `walkable()`** from "every step is an action the walk offers" to
   "every step is an action the walk offers, or a node whose arms hold only
   such actions". Prove the count moves 231 → about 301 in a test.
2. **Pass through a control node into its one arm**, for the 57 that have
   exactly one. No new screen at all.
3. **The arms screen**, for the 17 — labelled from the metadata.
4. **Back out of an arm** to the step list that holds it.
5. **Gate**: pytest, ruff, mypy --strict, `git diff --check`, 352/1045,
   1000-game replay, browser check, and the file on disk untouched.

Steps 1 and 2 cover 57 cards and add no screen. Step 3 adds one.

---

## 7. Deliberately not in this stage

- **Creating a branch**, which §2 shows is not possible from today's metadata.
  If it is wanted, the missing piece is a published question for a condition,
  and that is a change to the engine's vocabulary, not to a screen.
- **Adding or removing an arm, or a mode.**
- **Reordering steps inside an arm.**
- **The 4 replacement cards**, and the 30 that do not read.
- **A tree control.** 69 of 74 cards have no nesting at all.

---

## 8. Risks

| Risk | Weight | What holds it down |
|---|---|---|
| the walk stops on a node with nothing to ask | **high** | measured: no control node has a drawable first question, so passing through is the design rather than an oversight |
| a person cannot tell which arm they are filling in | medium | `sofar` says where it is; the arm's own `asks` text names it |
| editing an arm disturbs its neighbour | low | §4 — 51 cards, nothing moved |
| scope creep into creating branches | **high** | it is blocked by metadata, and the plan says so rather than working around it |
| the one-question rule quietly becomes a form | medium | an arm is a list of steps, and lists already have a screen |

---

## 9. The invariant, unchanged

```
Constructor ──┐
              ├──→ state.card ──→ build_card ──→ CardDefinition ──→ Validator ──→ file
Expert Editor ┘         ↑                                              │
                   read_card ←────────────────────────────────────── the file
```

A step inside an arm is a step. That is the whole reason this stage is small.
