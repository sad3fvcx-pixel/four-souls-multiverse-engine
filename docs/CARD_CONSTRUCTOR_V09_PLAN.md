# Card Constructor v0.9 — a card that chooses

After v0.8 a card can be opened, read, changed part by part and kept. What it
still cannot do is open most of the cards that exist.

Measured against the engine at `f3ae5be`.

---

## 1. Where it stands

| | cards | |
|---|---|---|
| shipped cards with rules | 352 | |
| **read** | **248** | 70% |
| of those, **editable** | **231** | 93% of what reads |
| of those, view only | 17 | |
| **refused** | **104** | 30% |

Editing is nearly finished for whatever opens; opening is where the loss is.
And the 104 refusals are not 104 problems:

| refused because | cards |
|---|---|
| **it chooses between things that happen** | **90** |
| a step picks something out for itself | 8 |
| a value is worked out from something the ability chose | 4 |
| a step keeps its result under a name for a later step | 1 |
| an answer holds several things the ability chose | 1 |

**One cause is 87% of everything that does not open.**

Which settles what kind of work this is. Ninety cards do not need ninety
fixes, and none of them needs fixing at all — they are correct cards, written
the way the game writes them, and it is the reader that stops. **This stage
widens the reader. It does not touch a single card**, and any stage that found
itself editing content to make cards open would be the wrong stage.

---

## 2. What that one cause is

Four control nodes, counted over every shipped card:

| written | times | in cards |
|---|---|---|
| `if` | 108 | 47 |
| `may` | 33 | 25 |
| `choose` | 22 | 21 |
| `for_each` | 2 | 2 |

A step that holds other steps. `roll_dice`, then *if it came up under four* do
one thing, *otherwise* another — which is what half the printed cards in this
game say.

Three more structures are published and **no shipped card uses any of them**:
`sequence`, `repeat`, `stop`. They come along for free and are not the reason
to do this.

The refusal is one place — `author.py::_read_step`:

```python
    if name in CONTROL_NAMES:
        raise UnreadableCard(
            f"This card uses {name!r}, which chooses between things that "
            "happen. Cards that do that are edited in full."
        )
```

`CONTROL_NAMES` lives in `runtime/interpreter.py`, beside the code that acts on
it. The reader asks the runtime what a control node is rather than keeping a
list of its own, which is why this is one line to change and not a search.

---

## 3. The metadata is already there

Every one of them is published, in the catalogue's `structures`, with its
questions already written in the card's own words:

| | its body | asked | what it asks a person |
|---|---|---|---|
| `if` | `then`, `else` — each `a_list_of: step` | first | *What happens when it is?* / *…when it is not?* |
| `may` | `effects` — `a_list_of: step` | first | *What happens if they say yes?* |
| `choose` | `modes` — `a_list_of: mode` | first | *The options?* |
| `for_each` | `effects` — `a_list_of: step` | first | *What happens for each one?* |

`if` also carries `conditions` as `a_list_of: condition`, which is the same
list a static already reads today. `mode` is itself a published shape: a
description and its own `effects`.

So there is **no metadata missing**. A control node is a node whose body is a
list of steps, which is exactly what an ability is, and the page already draws
one of those. Nothing here needs a new concept — that is the finding this
stage rests on, and it is why the stage is worth taking now.

Each also has both spellings, like everything else: `{"if": …}` and
`{"conditions": …}`, `{"may": …}` and `{"effects": …}`. `normalise` already
turns both into one, and the reader already writes back through it.

---

## 4. How far it reaches

| | read | editable |
|---|---|---|
| today | 248 | 231 |
| with control nodes, as estimated here | 338 | to be measured |
| **with control nodes, as measured after** | **322** | to be measured |

> **Measured afterwards: 248 → 322, not 338.**
>
> 338 was a forecast, and it was made the only way it could be made before
> the work: by counting the cards whose *first* refusal was a control node.
> A card is refused at the first thing the reader cannot take, so that count
> could never see what stood behind it.
>
> Sixteen of the ninety had a second reason, and removing the control node
> refusal is what uncovered them — eight hold a step that picks something out
> for itself, seven keep what they chose under a name for a later step to
> read, one points at something the ability chose. None of them is a new
> problem: each is a limit that was already there, hidden behind the larger
> one.
>
> The measured answer is **322 cards read stably** — stable meaning read,
> built and read again to the same author state, and passing the checker
> afterwards. That is the number to plan from; 338 was arithmetic.

Of the 90, **85 nest one level deep** and 5 nest two. Most use one kind only:

| | cards |
|---|---|
| `if` alone | 45 |
| `may` alone | 22 |
| `choose` alone | 17 |
| two kinds together | 5 |
| `for_each` alone | 1 |

Three further cards hold a control node *and* something else that is refused
first, so they need this and one more thing.

After it, 14 cards are refused, for four reasons that have nothing to do with
each other — which is a different kind of work from one cause worth 90.

---

## 5. The 17 that read and cannot be changed

All of them, and only them, for three effects:

| | cards |
|---|---|
| `modify_event` | 7 |
| `cancel_event` | 7 |
| `prevent_damage` | 3 |

Each declares `replacing`, meaning it only works inside a replacement ability,
and the walk offers only what it can finish. That is a smaller and separate
stage: it needs the walk to know it is inside a replacement, not a new way to
read a card.

---

## 6. What the reader has to do

`_read_step` refuses by name. Instead it should read a control node the way it
reads a part: find the shape, read its fields, and for a field that is
`a_list_of: step` read each step under it — which is `_read_fields` calling
itself, and it already descends into `a_list_of` fields for everything else.

Two things need care, and both already have an answer elsewhere in the file:

- **`if` holds conditions**, not steps. `_read_fields` reads a list of
  conditions for a static today.
- **`choose` holds modes**, each a node with its own steps. A mode is a
  published shape, so it is read as a node like any other.

What must not change: a card that is read comes back meaning the same thing,
and a card that cannot be read faithfully is still refused rather than
half-read. Reading 90 more cards is worth nothing if any of them comes back
meaning something else.

---

## 7. What the screens need

The walk asks about one node at a time and already points at *a node*, not at
a step list — Stage 3B made it so. A control node is a node whose body is a
list of steps, so the walk can point inside one the way it points at a part.

The open question: **how a person sees where they are.** A card with a branch
is not a list of steps any more, and "one question per screen" has held every
stage so far.

This plan deliberately does not choose. The decision waits until the reader
exists and a branching card has been turned into author state, because the
shape of that state is the evidence — what a branch actually looks like once
it is in hand, how deep it goes, how much of a screen one holds. Choosing
before that would be choosing from imagination. Two shapes suggest themselves
in the meantime:

- the walk goes *into* a branch and comes back out, with `sofar` saying which
  branch is being filled in;
- the branch is a part like an ability is, listed on the parts screen.

Both are drawn from published `asks` text either way. Neither needs new
metadata.

---

## 8. Order

1. **Measure first**: read all 90 with the reader changed, and prove every one
   comes back meaning the same thing — the same contract v0.8 was built on.
2. **The reader**, descending instead of refusing.
3. **The count moves 248 → 322**, in a test. (Estimated 338 before the work;
   see §4 for why the two differ.)
4. **Decide the screen** (§7) — once branching cards are in author state and
   can be looked at, not before.
5. **The walk**, into a control node and out.
6. **Gate**: pytest, ruff, mypy --strict, `git diff --check`, 352/1045,
   1000-game replay, no JS errors, and the file on disk untouched.

Steps 1–3 are worth doing and reviewing before a screen exists. They are also
where the risk is: the reader is the part that can silently change a card.

---

## 9. Deliberately not in this stage

- **The 14 other refusals.** Four unrelated causes, small each.
- **The 17 replacement cards.** Its own stage.
- **Adding or removing a part, or a step.** Editing what is there is still a
  smaller thing than changing what a card is made of.
- **`sequence`, `repeat`, `stop`.** They arrive free and are not aimed at.
- **A second card model.** There is one, and it is `state.card`.

---

## 10. Risks

| Risk | Weight | What holds it down |
|---|---|---|
| a card comes back meaning something else | **high** | step 1 is the whole of the contract, over all 90, before anything is offered |
| the walk becomes a form | medium | the screen is decided on evidence, after the reader, not designed first |
| nesting two deep is a different problem from one | low | measured: 5 cards, and the reader recurses either way |
| scope creep into the other 14 | medium | they are four causes and this is one |

---

## 11. The invariant, unchanged

```
Constructor ──┐
              ├──→ state.card ──→ build_card ──→ CardDefinition ──→ Validator ──→ file
Expert Editor ┘         ↑                                              │
                   read_card ←────────────────────────────────────── the file
```

One builder, one checker, one reader, one writer. A card that chooses between
things that happen is the same object as one that does not, which is why the
metadata for it was already published before anything meant to read it.
