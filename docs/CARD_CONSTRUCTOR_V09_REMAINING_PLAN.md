# Card Constructor v0.9 — what is left, and why

After Stage 2.2.2 the Constructor reaches most of the shipped content. This
counts what it does not reach and says, for each card, the one thing that
stops it.

Analysis only. Measured against the engine at `a631b08`, through the page's
own rules rather than a model of them. Nothing in `src/`.

---

## 1. Where it stands

| | cards | |
|---|---|---|
| shipped cards with rules | 352 | |
| **readable** | **322** | 91% |
| **editable** | **293** | 83% of all, 91% of readable |
| read but not editable | 29 | |
| not readable | 30 | |

---

## 2. The 29 that read and cannot be changed

Filed by the one thing that stops each card:

| | cards | what stops them |
|---|---|---|
| **A · replacement effects** | **21** | `cancel_event` (10), `modify_event` (7), `prevent_damage` (4) |
| **F · an answer only the expert editor asks for** | **5** | `promise` (4), `watch_for` (1) |
| **E · a branch inside a branch** | **3** | `sack_head`, `chaos_card`, `pandora_s_box` |

**A.** These three effects declare `replacing: true` — they only work inside a
replacement ability, and the walk offers only what it can finish anywhere. The
cards are correct and the effects are correct; the walk simply does not know
it is inside a replacement. **Nothing is missing but the walk knowing where it
is.**

**F.** `promise` and `watch_for` each carry a required field that is
`shown: "advanced"` — `promise.changes` and `watch_for.effects`. The walk
draws `shown: "form"` and nothing else, so it cannot finish them. The
metadata is complete; the walk has no control for that routing value.

**E.** These read perfectly. `walkable` collects the steps under a node and
asks whether each is an action it offers — and a *nested* control node is one
of those steps, and is not an action. The rule needs to recurse rather than
flatten. **One line, and no metadata at all.**

---

## 3. The 30 that do not read

| | cards | the reason given |
|---|---|---|
| **E · a step that picks its own target** | **16** | *"…picks something out for itself"* |
| **B · a name bound for a later step** | **9** | *"…keeps what it chose under a name"* |
| **C · a value worked out from a choice** | **4** | *"…works `amount` out from something the ability chose"* |
| **D · an answer built from several choices** | **1** | `decoy`'s `group` of `mine` and `theirs` |

### They are one problem wearing four coats

The reader turns a binding into the thing it points at and **drops the name**:
an ability binds `{"target_player": {"as": "rival"}}`, and author state keeps
the player, not the word *rival*. On the way back out the builder invents a
fresh one:

```python
body["as"] = str(described.get("as") or f"chosen_{id(described) % 997}")
```

So a card that refers to what it chose — a later step pointing at `rival`, a
count worked out `of: "rival"`, a step choosing something of its own that a
later step could reuse — cannot survive the round trip, and the reader
refuses rather than letting it change meaning. That refusal is right. What is
missing is that **author state has nowhere to keep the name a card gave to
what it chose.**

Note the writer already takes one: `described.get("as")` is honoured before a
name is invented. The hook exists; nothing fills it.

The metadata is not missing either. A computed value has a published shape —
`worked_out`, with `from`, `of`, `minus`, `floor`, `times`, `plus` — so class
C needs no new vocabulary, only a name that survives.

---

## 4. Do these cards open if the reader is widened, without touching the cards?

**Yes for all of them, and no card is wrong.** Every one of the 59 is correct
content, written the way the game writes it. Nothing here is a card to fix.

But "widening the reader" is not one job:

| | cards | reader | writer | UI | metadata / runtime |
|---|---|---|---|---|---|
| A · replacement effects | 21 | — | — | **yes** | — |
| E · a branch inside a branch | 3 | — | — | **yes** | — |
| F · an advanced answer | 5 | — | — | **yes** | — |
| B · a bound name | 9 | **yes** | hook exists | — | — |
| C · a worked-out value | 4 | **yes** | hook exists | — | — |
| D · an answer from several choices | 1 | **yes** | hook exists | — | — |
| E · a step's own target | 16 | **yes** | **yes** | — | — |

**Nothing on this list needs the runtime, the schema, the card language or the
content changed.** That is the finding worth carrying: 29 cards are held by
screens, 30 by one idea missing from author state, and none by the engine.

---

## 5. Order

Cheapest and safest first, and each is a stage of its own:

1. **A branch inside a branch** — 3 cards, one line, no metadata. `walkable`
   recurses instead of flattening.
2. **Replacement abilities** — 21 cards, the largest single win. The walk
   learns which part it is inside and offers `replacing` effects there.
3. **A name that survives** — 14 cards (B, C, D) at once, because they are one
   problem. Author state keeps the name a card gave to what it chose; the
   builder already writes it back. This is the one with real risk, and it is
   where the round-trip contract earns its keep.
4. **A step's own target** — 16 cards, and the hardest: it needs a place in
   author state for a choice that belongs to one step rather than to the
   ability, and the reason the reader refuses today is exactly that folding it
   up would silently merge two separate choices into one.
5. **An advanced answer** — 5 cards, and worth doing last or not at all: it
   asks the walk to draw a control it has never drawn, for the two most
   involved effects in the game.

Steps 1 and 2 are 24 cards for no new ideas. Step 3 is 14 for one.

---

## 6. Deliberately not

- **Changing any card.** All 59 are correct.
- **Changing the runtime, the schema or the card language.** Nothing here
  needs it, and a stage that reached for it would be solving the wrong
  problem.
- **Adding, removing or reordering** anything in a card — still separate from
  changing what it says.
- **Editing a condition** — no question for one is published, which remains
  the one genuine gap in the vocabulary.

---

## 7. Risks

| Risk | Weight | What holds it down |
|---|---|---|
| a name that survives changes what a card means | **high** | the round-trip contract over all 322 readable cards, which has caught every such attempt so far |
| folding a step's own target merges two choices | **high** | it is why the reader refuses today; step 4 must keep them apart or keep refusing |
| the walk offers a replacement effect outside a replacement | medium | `replacing` is published per effect; the walk asks the part it is in |
| chasing the 5 advanced cards pulls the walk into being a form | medium | last on the list, and skippable |
| a stage reaches into the runtime to make cards open | **high** | none of the 59 needs it; this plan says so with numbers |

---

## 8. The invariant, unchanged

```
Constructor ──┐
              ├──→ state.card ──→ build_card ──→ CardDefinition ──→ Validator ──→ file
Expert Editor ┘         ↑                                              │
                   read_card ←────────────────────────────────────── the file
```

Every card here already goes round this loop in the engine. What is missing is
that author state, in the middle, forgets one thing a card can say: the name
it gave to what it chose.
