# Card Constructor v0.9 Stage 2 — showing a card that chooses

Stage 1 made branching cards readable. 322 of 352 shipped cards now come back
as author state, 74 of them holding a control node. This is the analysis of
what to *show*, and it was written after measuring that state rather than
before.

Measured against the engine at `a04104b`.

---

## 1. What they look like in author state

Nothing new. A control node is `{id, fields, groups}` like everything else,
and what it holds is a list of the same:

```
{ id: "if",
  fields: {
    if:   [ {id: "dice_less",   fields: {value: 4}} ],   ← a condition
    then: [ {id: "gain_coins",  fields: {amount: 1}} ],  ← steps
    else: [ {id: "deal_damage", fields: {amount: 1},
             aim: "controller"} ] } }

{ id: "may",
  fields: { may: [ …steps… ], prompt: "Take two?" } }

{ id: "choose",
  fields: { choose: [ {id: "mode", fields: {description: "A",
                                            effects: […steps…]}},
                      {id: "mode", fields: {description: "B",
                                            effects: […steps…]}} ] } }

{ id: "for_each",
  fields: { for_each: "opponents", effects: [ …steps… ] } }
```

An arm is a list of steps. A mode is a node with a description and a list of
steps. A card's ability is a node with a list of steps. **They are the same
shape**, which is why Stage 1 needed no new model and why the screens need no
new one either.

---

## 2. It is not a tree

This is the finding that decides the stage. Over all 74 branching cards:

| | |
|---|---|
| control nodes in all | 138 — `if` 104, `may` 18, `choose` 15, `for_each` 1 |
| **cards with no nesting at all** | **69 of 74** |
| cards nesting one level | 5 |
| cards nesting deeper than that | **0** |
| **`if` nodes with exactly one condition** | **104 of 104** |
| **`if` nodes with an `else`** | **3 of 104** |
| **arms holding exactly one step** | **150 of 169** |
| arms holding two | 17 |
| the largest arm in the game | 7 steps |
| `choose` with 2 / 3 / 5 / 6 modes | 7 / 6 / 1 / 1 |
| nodes carrying a `prompt` | 18 |

And per card:

| control nodes on one card | cards |
|---|---|
| 1 | 45 |
| 2 | 9 |
| 3 | 14 |
| 4 | 2 |
| 6 | 3 |
| 7 | 1 |

So the shape a person actually meets is: **a flat list of steps, one of which
has one condition and one step under it.** Not a branch with two arms — 101 of
104 `if`s have only a `then`. Not a nest — 69 of 74 cards are one level deep.

A tree widget would be built for 5 cards out of 74, and a two-armed branch
drawing for 3 nodes out of 104. **Designing a tree here would be designing for
the exception.** What the data asks for is a list that can indent.

---

## 3. Keeping the three principles

**One question per screen.** A control node adds its own first questions and
nothing else: *What must be true?* for `if`, *What to ask them?* for `may`,
*What to do it for each of?* for `for_each`. Those are questions like any
other, already written in the metadata, already `asked: "first"`. Then the
walk continues into the arm, which is a list of steps — which is exactly what
`sofar` and `oneByOne` already walk. No screen holds a tree; each screen holds
one question or one list.

**Metadata-driven.** Every fact the screens need is published: which fields
hold steps (`a_list_of: "step"`), which hold conditions, which hold options
(`a_list_of: "mode"`), what each asks, and which key names the node. Stage 1
reads all of it already. Nothing below needs `if` or `may` written in the page.

**No second representation of a card.** There is one `state.card`, and a
control node is a node inside it. The walk already points at *a node* rather
than at a step list — Stage 3B of v0.8 made it so — which is the property this
stage rests on.

---

## 4. What the walk would reach

| | cards |
|---|---|
| branching cards read | 74 |
| **every leaf step is one the walk already offers** | **70** |
| held back by a leaf it does not offer | 4 — `cancel_event` ×3, `prevent_damage` ×1 |

Those four are the replacement-ability stage, not this one.

So editing would go from **231 to about 301** of 352, and the walk's rule
would not change: it already refuses a card whose steps it cannot offer. The
one thing in its way is that control nodes are published with `a_step: true`
and the walk offers only what is not — correctly, today, because a control
node was not something it could finish.

---

## 5. What is missing on the reading screen

One concrete gap, found by reading the page rather than guessing:

```js
function saidAs(step) {
  const doing = named(can.effects, step.id);
  if (!doing) return step.id || "something";
```

`saidAs` looks a step up in `can.effects`. Control nodes are published under
`can.structures`, so a branch falls through to `step.id` and renders as the
bare word **"if"** with nothing under it. A card that chooses currently opens
and shows almost nothing of what it does.

That is the smallest useful piece of work in this stage, and it is worth doing
on its own: a person can already open 74 more cards and cannot yet see them.

---

## 6. The minimum, in order

1. **Show a branch.** `saidAs` reads the node's own words from whichever
   catalogue describes it, and an arm is drawn as an indented list of the same
   sentences. Reading only. This alone makes 74 cards legible.
2. **Walk into an arm.** The node's first questions, then its arm as a list of
   steps, then back out. `sofar` gains a way to say which arm is being filled
   in; nothing else changes.
3. **Offer control nodes as actions**, so a card being made can branch. This
   is the point at which `a_step` stops being the walk's filter and becomes a
   question of what a step may hold.
4. **Adding and removing arms** — a mode added to a `choose`, an `else` added
   to an `if`. Deliberately last, and possibly not in this stage at all: it is
   changing what a card is made of, which every stage so far has kept separate
   from changing what it says.

Steps 1 and 2 cover the measured shape. Steps 3 and 4 are where a tree would
start to be a real question, and they can be judged on their own once 1 and 2
exist.

---

## 7. Deliberately not in this stage

- **A tree control.** The data says a list that indents; if a card ever nests
  three deep this is worth reopening.
- **The 4 replacement cards**, and the 30 that do not read.
- **Saving.** Already built and unchanged — a branching card saves through the
  same path as any other, and Stage 1 proved the round trip.
- **A second card model.**

---

## 8. Risks

| Risk | Weight | What holds it down |
|---|---|---|
| the walk becomes a form | **high** | one question per screen is the rule that has held every stage; an arm is a list, and lists already have a screen |
| a tree is built for five cards | medium | measured before designing, which is why this plan does not build one |
| a branch is shown flattened | **high** | it would read as "do both" instead of "do one" — the reading screen must indent, and a test compares what is shown against what the state holds |
| editing an arm disturbs its neighbour | medium | the same contract Stage 3B used, over every branching card |

---

## 9. The invariant, unchanged

```
Constructor ──┐
              ├──→ state.card ──→ build_card ──→ CardDefinition ──→ Validator ──→ file
Expert Editor ┘         ↑                                              │
                   read_card ←────────────────────────────────────── the file
```

An arm of a branch is a list of steps, an ability is a list of steps, and a
mode is a node holding a list of steps. One shape, three names for where it
sits.
