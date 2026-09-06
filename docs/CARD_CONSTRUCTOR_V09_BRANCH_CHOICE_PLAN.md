# Card Constructor v0.9 Stage 2.2.2 — choosing between branches

Stage 2.2.1 lets the walk follow a branch. Where a node has one arm it goes
straight in, which is most of them. This is about the rest: the places where
there really is something to pick.

Analysis only. Measured against the engine at `c75d6f1`. Nothing in `src/`.

---

## 1. How much choosing there actually is

Over all 322 cards that read:

| | |
|---|---|
| control nodes in all | 138 |
| **nodes with more than one arm** | **18** |
| of those, `choose` | 15 |
| of those, `if` with an `else` | 3 |
| `may` with more than one arm | **none** — `may` always has exactly one |
| cards holding at least one such node | **17** |
| cards where every node has one arm | **57** |

Options per node:

| | nodes |
|---|---|
| 2 options | 10 (7 `choose`, 3 `if`) |
| 3 options | 6 |
| 5 options | 1 |
| 6 options | 1 |

**So 120 of the 138 control nodes are passed without asking anything**, and
the largest choice in the game is six.

What is behind an option:

| steps in one option | options |
|---|---|
| 1 | 40 |
| 2 | 8 |
| 0 | 1 |

The one that holds nothing is `devil_deal`'s *"Put this into discard."* — an
option that means *do none of the others*, which is a real thing to offer and
not a mistake.

**No option anywhere holds another choice.** Choosing is one level deep in
every shipped card, so nothing here has to nest.

---

## 2. The metadata already names every option

Nothing new is wanted. For a `choose`:

| | field | `asked` | `shown` | |
|---|---|---|---|---|
| where the options are | `choose` / `modes` | first | body | `a_list_of: mode` |
| **the text of an option** | `mode.description` | **first** | **form** | required |
| the steps of an option | `mode.effects` | first | body | `a_list_of: step` |

For an `if`, the two arms carry their own words:

| | |
|---|---|
| `then` | *What happens when it is* |
| `else` | *What happens when it is not* |

And the options are in good order: of 49 option labels, **none is missing**,
**none is duplicated within its node**, the median is 26 characters and the
longest is 98, with 6 over 60.

---

## 3. It already fits the walk — and mostly already works

Checked rather than assumed, and much of it was settled by Stage 2.2.1:

| question | answer |
|---|---|
| is a chosen arm an ordinary node? | **yes** — a list of steps like any other |
| can the choice be held as a path? | **yes** — `armsOf` already returns one, and `intoArm` puts it in `walk.list` |
| does it survive going back? | **yes** — measured: `outOfArm` returns to the exact list it came from |
| is a new state format needed? | **no** |

Going back and then in again offers the choice afresh rather than remembering
it, which is the right behaviour: picking again costs nothing and there is
nothing to remember that the card does not already say.

---

## 4. The one thing that is wrong today

The screen exists. What it says is poor, and measurably so — this is what the
six options of `i_the_magician` look like now:

```
One option of a choice — what this option offers: Change the result to a 1.
One option of a choice — what this option offers: Change the result to a 2.
One option of a choice — what this option offers: Change the result to a 3.
…
```

Forty-seven characters of preamble before the words that differ, repeated on
every row. It happens because the screen names an option with `saidAs`, which
is built to *describe a step* — a sentence about what a thing is, then its
answers. An option does not need describing: it has a name, and the metadata
says which field it is (`mode.description`, `role: names`, required).

The `if` case is already right — *What happens when it is* / *…when it is not*
— because those arms are named by their own field rather than by `saidAs`.

So the defect is one line, and it is the difference between a screen a person
can read down and one they have to read across.

---

## 5. The minimum

**Option A — show the options, pick one, carry on into the existing walk.**
Chosen, and most of it is built.

- **B, showing options in view mode only**, is behind where the code already
  is: the choice screen exists and works.
- **C, editing the structure of a choice** — adding an option, removing one,
  changing how many there are — is the thing every stage so far has kept
  separate from changing what a card says, and it would need questions the
  engine does not publish for the `if` case at all.

What A still needs, and all of it:

1. **Name an option by its own name**, not by a sentence describing what an
   option is. One lookup: the field whose `role` is `names` on the shape of
   the thing being offered.
2. **Let a long option wrap** rather than truncate — 6 labels run past 60
   characters and the longest is 98.
3. **Say what is being chosen between**, once, at the top: the node's own
   words (*one of several options*, *depending on something*) instead of on
   every row.

That is the whole of it. There is no screen to invent, no tree, and no new
metadata — the measurements say the shape is at most six short lines, one
level deep, each already carrying a name.

---

## 6. Order

1. **The label**, read from the `names` field of whatever is being offered —
   generic, so a structure the engine gains is named by this too.
2. **The heading**, from the node being chosen within.
3. **Wrapping**, so nothing is cut.
4. A test that no option is drawn as a description of what an option is, and
   one that every shipped choice draws distinct labels.
5. **Gate**: pytest, ruff, mypy --strict, `git diff --check`, 352/1045,
   1000-game replay, browser check over all 17 cards, no JS errors.

---

## 7. Deliberately not in this stage

- **Adding or removing an option or an arm.**
- **Editing a condition** — no question for one is published.
- **Remembering which arm was last chosen.**
- **Nesting** — no shipped option holds a choice.
- **The 29 cards that are still view only.**

---

## 8. Risks

| Risk | Weight | What holds it down |
|---|---|---|
| the label is taken from a named field rather than a role | medium | read `role: "names"` off the shape, so nothing names `description` |
| a long option is cut and two options read alike | medium | measured: 6 run past 60 characters; the rows wrap |
| an option that does nothing looks like a bug | low | one exists and is deliberate; it keeps its own name |
| scope creep into changing how many options there are | **high** | it is the next thing anybody would ask for and it is not this |

---

## 9. The invariant, unchanged

```
Constructor ──┐
              ├──→ state.card ──→ build_card ──→ CardDefinition ──→ Validator ──→ file
Expert Editor ┘         ↑                                              │
                   read_card ←────────────────────────────────────── the file
```

An option is a node with a name and a list of steps. Which is what an ability
is, with a name.
