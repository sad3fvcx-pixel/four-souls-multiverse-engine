# Card Constructor v0.9 — the name a card gives to what it chose

Fourteen cards are refused for something to do with a name. This traces where
the name is made, where it is lost, and asks whether one change closes all
fourteen.

Analysis only. Measured against the engine at `02db1af`. Nothing in `src/`.

---

## 1. Where a name is made, kept and dropped

```
the card          "targets": [{"target_player": {"as": "rival"}}]
                            │
   reader   _bound_by       ├─ keyed by the name:  bound["rival"] = (kind, body)
                            │
            _read_value     └─ the targets list itself → _NOT_AN_ANSWER (dropped)
                            │
            _as_chosen      └─ a step naming "rival" becomes the thing itself,
                               inlined into the step's `groups` — the name gone
                            │
 author state     the step holds *what* was chosen. Nowhere holds *what it
                  was called*.
                            │
   writer   _pick_out       └─ binds it again under a name of its own making:
                               `chosen_{n+1}`, reusing one when two steps chose
                               identically
                            │
   checker                  the card is valid, and means the same thing
```

**This is why 322 cards round-trip perfectly.** Dropping the name is harmless
exactly when nothing else refers to it: the target is the same target, and
`chosen_2` reads as well as `rival`.

It stops being harmless the moment something *else* in the card says the name
out loud — and then the reader refuses, rather than reading a card that would
come back meaning something different.

There are two naming sites in the writer, and they do not agree:

| | |
|---|---|
| `_pick_out` | invents `chosen_{n+1}`; **an author's name is not consulted** |
| `_written_body` for a target | `body["as"] = str(described.get("as") or …)` — **honours one if given** |

So the hook exists in one place and not in the other, and the one that
actually rebuilds an ability's `targets` is the one without it.

---

## 2. What the fourteen actually say

| | cards | what they do |
|---|---|---|
| **B** | 9 | a step or a control node keeps what it chose under a name (`as`, `store`) |
| **C** | 4 | a value is worked out from something named |
| **D** | 1 | one answer is built from two names |

Card by card, the names each makes and whether anything says them again:

| | card | names it makes | said again |
|---|---|---|---|
| B | `xii_the_hanged_man` | `loot_top`, `treasure_top`, `monster_top` | yes ×3 |
| B | `the_d4` | `rerolled_player` | yes ×2 |
| B | `the_bloat` | `store: first_die`, `second_die` | yes ×2 |
| B | `crystal_ball` | `named_number` | **no** |
| B | `cheese_grater` | `shown_loot`, `discard_loot` | **no** |
| B | `the_capricious` | `swept`, `capricious_choice` | **no** |
| B | `devil_deal` ×2 | `found`, `devil_choice` | **no** |
| B | `mulligan` | `mulligan_choice` | **no** |
| C | `ii_the_high_priestess` | `victim` | yes |
| C | `viii_justice` | `rival` | yes ×2 |
| C | `famine` | `loser` | yes ×2 |
| C | `sloth` | **none** | — |
| D | `decoy` | `mine`, `theirs`, `decoy_pair` | yes ×3 |

Two things fall out of this that were not obvious:

**Five of the nine B cards make a name nothing refers to.** They still need it:
a name is how two choices in one ability stay two choices, and dropping it
would let the engine's default collapse them.

**One card is not a naming problem at all.** `sloth` writes

```json
"count": { "count": "loot", "of": "controller" }
```

and is refused because `of` is a key that *names* something — regardless of
what it names. Here it names `controller`, a **published standing target**, not
anything the ability chose. Nothing would be lost by reading it. The guard
looks at the key, and the question it means to ask is about the value.

---

## 3. So: is it one problem?

**Thirteen of the fourteen, yes.** Their common root is exactly one thing:

> Author state can hold *what* a card chose. It cannot hold *what the card
> called it*.

Every B, every C but one, and D fail for that and nothing else.

**The fourteenth is a separate, smaller thing** — a guard that refuses a
reference by the shape of the key rather than by what it points at. It needs
no name preserved and no new state; it needs the question narrowed from
*"does this key name something?"* to *"does this name something the ability
chose?"* — and the reader already holds `bound`, which is what answers it.

Calling all fourteen one problem would have been tidier and wrong.

---

## 4. What already exists, and what does not

| | published? | in author state? | notes |
|---|---|---|---|
| `as` on a target | as part of the target's body | **no** — dropped by `_as_chosen` | the runtime's own way of naming |
| `as` on a control node | yes, `written_as: BY_BINDING` | **no** — refused on read | the engine writes these |
| `store` on a step | yes | **no** — refused on read | same idea, different word |
| `refers_to` on a parameter | yes | read, then resolved away | how the reader knows a value names something |
| `worked_out` | **yes, a full node shape** | no | `from`, `of`, `minus`, `floor`, `times`, `plus` |
| `chosen_N` | no | no | the writer's invention, not a concept |

**No new vocabulary is needed for the values.** What is missing is a place in
author state for the name, and that is a change to the shape of author state
rather than to the language a card is written in.

---

## 5. Where the change lands

| | needed |
|---|---|
| **content** | no |
| **schema** | no |
| **runtime execution** | no |
| **the card language** | no |
| **the vocabulary describing it** | **probably not** — the concepts are published; the gap is in state |
| **reader** | **yes** — keep the name, stop resolving it away |
| **author state** | **yes** — a place for it |
| **writer** | **small** — `_pick_out` honours a given name, as its sibling already does |

So: **reader + author state + a small writer change.** Not schema, not runtime.

---

## 6. The contract to write first

For a card with a named choice, and nothing weaker:

```
read → state → build → read     identical
                  └─ and the name in the rebuilt card is the name the
                     card was written with, not one invented for it
```

Today no test asserts the second line, which is why the writer could invent a
name for years without anything noticing. That absence is the reason this is
worth doing carefully: the round-trip contract passes *because* the reader
refuses everything that would expose the gap.

---

## 7. Order

1. **Narrow the working guard** — `sloth` alone, no name preserved, one card,
   and it is independent of everything below.
2. **A place for the name in author state**, and the reader keeping it.
3. **`_pick_out` honouring it**, so a card comes back called what it was
   called.
4. **The names that are never said again** (5 cards) — they need only to
   survive, not to be pointed at.
5. **The names that are said again** (8 cards) — the real test.

---

## 8. Deliberately not

- **A step choosing its own target** — the 16, and a different problem: a
  choice belonging to one step rather than to the ability. Not this stage.
- **Naming any effect or any card** in reader or renderer.
- **Changing content** to make a card open.
- **Inventing a vocabulary field** before it is shown that the published ones
  cannot carry it.

---

## 9. Risks

| Risk | Weight | What holds it down |
|---|---|---|
| a preserved name changes what a card means | **high** | the round-trip contract over all 322, plus the new line in §6 |
| two choices that were one become two, or the reverse | **high** | `_pick_out` deduplicates identical choices today; honouring a name must not stop that |
| the guard is narrowed too far and a real loss slips through | medium | it is one card; the test names it |
| this is read as licence to open the 16 | medium | §8 |

---

## 10. The invariant, unchanged

```
Constructor ──┐
              ├──→ state.card ──→ build_card ──→ CardDefinition ──→ Validator ──→ file
Expert Editor ┘         ↑                                              │
                   read_card ←────────────────────────────────────── the file
```

A card that says *the player you chose* has to be able to say *which* choice
it meant. It says so with a name, and the middle of this loop is the only
place that cannot hear it.
