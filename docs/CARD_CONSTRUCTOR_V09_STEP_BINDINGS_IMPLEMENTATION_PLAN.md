# Card Constructor v0.9 — designing the editor's model of scope

The scope model is settled: a name is visible from where it is bound to the end
of the arm that bound it, and inside everything nested there. This asks what
author state has to become for the editor to agree with it.

Analysis only. Nothing was changed, and nothing here is a proposal to write
code. Measured at `bcf7b4a`.

**The conclusion: no new stored field, and no new card-language concept.** The
minimum is that the reader stops discarding the card's word, and that the
writer carries a *stack* of gathering lists instead of one — because
`visible = current scope + parent scopes` is a stack, and the writer already
walks the arms that would make it.

---

## 1. What author state actually is today

Not "an ability with a list of bindings". Measured on `the_d20`, which is
readable now:

```json
"targets": []                                       ← the ability's list, empty
step[0]  {"id": "destroy_treasure",
          "aim": "target_treasure", "aim_name": "rerolled"}
step[1].then[0]
         {"id": "gain_treasure", "aim": "holder",
          "aim_groups": {"of": {"id": "target_treasure",
                                "fields": {"exclude_eternal": true},
                                "name": "rerolled"}}}
```

A binding is stored as **an inlined copy of the thing chosen, carrying the
card's word** — as `aim`/`aim_fields`/`aim_groups`/`aim_name` on a step, or as
`{id, fields, groups, name}` inside another target's answer. The ability's own
list is empty in state; the writer *rebuilds* it by gathering every copy as it
walks, and `_pick_out` treats two copies as one binding **when they carry the
same word**.

So the existing architecture is **copy-and-merge**, and the merge key is the
word, across the whole ability. That single fact is the defect:

| | |
|---|---|
| right within an arm | two steps saying `rerolled` mean one choice |
| wrong across arms | three modes saying `top` mean three |

Everything below follows from narrowing that key without breaking the first
row.

---

## 2. The life of a binding, stage by stage

| stage | where it is made | where the word lives | where the scope lives | where a reference is resolved | what is lost |
|---|---|---|---|---|---|
| card JSON | ability list, step list, or inline | `as` | implied by position | by the interpreter, per arm | — |
| reader `_bound_by` | reads **only** the ability's `targets` | — | — | — | **a step's own list is never seen** |
| reader `_read_step` | — | `aim_name`, kept for a card's word | **nowhere** | `_as_chosen` inlines what a name points at | **the word, for an inline binding** |
| author state | a copy per step and per referring answer | `aim_name` / `name` | **nowhere** | — | — |
| walker | — | — | — | offers a choice only where state holds one | — |
| writer `_pick_out` | gathers copies into **one list per ability** | matched on | **nowhere** | by word, ability-wide | **the distinction between arms** |
| `_written_part` | writes that list into the ability's `targets` | `as` | — | — | — |
| checker | — | — | derived per arm from `BRANCHES` | correctly | — |
| card JSON | ability list | `as` | implied by position | — | — |

Two losses, one cause. The reader drops an inline word *because* the writer's
key is ability-wide; the reader refuses a step's list for the same reason.

---

## 3. The three variants

### A — scope as an entity in the state

```
Ability → Scope → { bindings, child scopes }
```

Correct, and the most explicit. Two measured costs:

- Every copy becomes a **reference into a scope**, so a scope needs an identity
  that survives editing. The only identity available is position, and position
  changes whenever a step is inserted or moved — an editor's ordinary act.
- The scope tree runs parallel to the step tree and must be kept in step with
  it on every edit. Nothing in author state works that way today; it is one
  tree, rebuilt on open.

### B — bindings held on the step

Close to what exists: a step already carries its copy. But it has **no home for
an ability-level binding read from two arms**, and that is not hypothetical —
three shipped cards do it:

| card | name | bound in | read in |
|---|---|---|---|
| `the_d20` | `rerolled` | the ability | `.effects`, and `.effects[1].then` |
| `the_d4` | `rerolled_player` | the ability | `.effects[1].then`, and one deeper |
| `incubus` | `shown` | a mode's `effects` | that arm, and a `may` inside it |

Under B, neither reading step owns the binding, so either it is duplicated —
two choices where the card means one — or it needs an owner, which is variant A.

### C — keep copy-and-merge, narrow the key **(recommended)**

Change nothing about *where* state is held. Change two things about meaning:

1. **The reader keeps the card's word in every case**, inline included. It is
   dropped today only to protect an ability-wide key that is about to stop
   existing.
2. **The writer carries a stack of gathering lists.** Entering an arm pushes a
   new list; leaving it pops. Lookup searches the current list, then its
   parents. Creation happens in the current list.

That is `visible = current scope + parent scopes`, exactly — and it is a stack
because scopes nest and never intersect.

**Why C is minimal:** no new field, nothing new stored, and therefore no scope
identity to keep stable across edits. The scope is *derived while walking*, by
both reader and writer, from the same `BRANCHES` fact the checker already uses.
Author state stays one tree.

---

## 4. The visibility rule, checked against the four cases

```
lookup(word):  current list → parent → … → the ability
create(word):  the current list, always
```

| | expectation | under the stack |
|---|---|---|
| **A** bind `enemy` in an arm, use it there | allowed | created in that arm's list, found there. One binding, word kept. |
| **B** `top` in arm A and `top` in arm B | two independent bindings | two lists, neither consulted by the other. Two bindings, **both called `top`**. |
| **C** bind `outer`, use inside a `choose` | allowed | not found in the arm; found walking up. One binding. |
| **D** bind `inner` in an arm, use outside | forbidden | the arm's list is popped before the outer step is written, so nothing is found — and the checker refuses it independently. |

D is worth stating twice: it is already refused by the checker
(*"'inner' is bound, but not where this can see it"*), so the boundary is not
being held up by the reader's refusal. Relaxing the reader does not relax the
boundary.

### `the_curse`, specifically

Three modes, each choosing a deck and calling it `top`; three more calling
something `raised`. Under the stack each mode's `effects` is its own list, so
the three are created independently and none is ever compared with another. The
card comes back as

```
arm A: as "top"     arm B: as "top"     arm C: as "top"
```

and not `top`, `top_1`, `top_2` — because nothing renames anything. Renaming
exists today only to keep an ability-wide key unique.

---

## 5. What the writer would have to decide

The stack answers *which* binding; it does not answer *where to write one*.
Measured over the 171 distinct bindings in shipped content:

| | | a home |
|---:|---|---|
| 47 | never named again | written inline, where it is used — no name needed at all |
| 25 | read once, by the step that chose it | the same, or that step's own `targets` |
| 99 | read by something else | the innermost list that is visible to every reader — the ability's `targets` for an ability binding, a step's own `targets` within an arm |

(171 counts distinct names per ability; the 179 occurrences counted elsewhere
differ by exactly the 8 repeats of the four words bound three times each.)

So the rule is derivable rather than invented: **a binding is written in the
innermost place all of its readers can see.** For 72 of 171 that place is the
step itself, and the name may be left out entirely — which would remove
`chosen_N` from those cards rather than renaming it.

Order matters and is a constraint, not a preference: the checker refuses a name
read before it is bound, so a binding must be emitted on or before the first
step that reads it.

---

## 6. Components touched

| component | change | kind |
|---|---|---|
| `author.py` `_bound_by` | walk the arm, not just the ability's list | reader |
| `author.py` `_read_step` | keep `aim_name` for an inline binding too | reader |
| `author.py` `_as_chosen` | unchanged in shape; already carries `name` | — |
| `author.py` `_given` / `_pick_out` | look up a stack; create in the current list | writer |
| `author.py` `_written_part` / `_chooses` | write an arm's list where its readers can see it | writer |
| `static/author.html` walk | offer a choice at the step, from the published model | page |
| `capabilities.py` | publish which nodes may bind, and the visibility rule | publication |
| `runtime/`, `cards/`, `content/`, `effects/`, `rules/` | **nothing** | — |

---

## 7. Which cards this is for

**Should open — twelve.** One arm binds, depth one or two, no name leaves its
arm: `brimstone`, `dingle`, `epic_fetus`, `guppy_s_paw`, `host_hat`,
`mulliboom`, `pestilence` (base), `the_habit`, `the_lamb`, `the_lost`,
`rainbow_tapeworm`, `ultra_greed`.

**The proof cases — four.** They bind at the ability *and* inside an arm, so
the stack must be consulted at two levels at once. Nothing measured says they
cannot work; they are where the design is actually tested.

| card | why it is harder |
|---|---|
| `g_fuel` | ability binding plus one inside a `may` |
| `pestilence` (alt) | ability binding read by two steps that bind their own |
| `dead_bird` | ability binding read inside a `may` that binds its own |
| `finger` | the same, and one answer names several |

**Not promised — one.** `incubus`: three arms, four levels deep, an answer
naming several, and a name read one arm deeper than it was bound. Legal, and
covered by the model in principle. Whether the reader follows it faithfully is
to be measured, not assumed.

**A different sentence — three.** `famine`, `viii_justice` and `the_d4` bind
nothing in a step; they refuse because a worked-out value or a `for_each`
domain names a binding the reader would drop. They should follow once a binding
survives where it was made, but they are not step-local bindings.

**Must stay refused — nothing new, and `promise`'s four stay view-only.** The
four `promise` cards are a separate question about what an event carries, and
nothing here touches them.

---

## 8. Risks

1. **Merging what should stay apart, and splitting what should merge.** The
   merge is load-bearing: two steps saying `rerolled` must mean one choice, or
   "destroy an item and replace it" destroys one item and replaces another. The
   38 A-and-B reads are the cases a wrong stack breaks, and `the_d20` is the
   smallest example that already works today. Measure those before anything.
2. **Silent change to existing cards.** 163 readable cards currently carry an
   invented name; under the new writer, 72 of 171 bindings need no name at all,
   so a great many cards would be written back in a *different shape*. The
   round-trip contract asks whether a card still means the same, not whether it
   is spelled the same — so it should pass, and that is exactly why it must be
   run rather than reasoned about. Case B's failure mode is a card that loads,
   passes the checker, and chooses the wrong thing.
3. **Order within an arm.** A binding written after its first reader produces a
   card the checker rejects — or, worse, one it accepts with the wrong reading
   order. The rule in §5 has to hold for every emitted binding.
4. **Checker and runtime.** Neither changes, and neither should. The checker is
   the guard for all of the above, and the mass replay is the guard for the
   claim that nothing about play changed. If either moves, the design is wrong.
5. **`own_names` misread as the boundary.** It marks a boundary on `ability`
   and `static` only, as a switch. Anything treating it as *the* scope marker
   rebuilds the ability-wide key this whole analysis is removing.

---

## 9. What this establishes

The criterion was proof that the fix is a change to the editor's
representation rather than an extension of the card language. The measurements
give it:

- every construction involved is already legal and already played — all twenty
  refused cards pass the checker;
- the scope rule is already implemented, already obeyed, and violated nowhere
  in the content, with the one forbidden case enforced;
- the disagreement is one line of meaning in the editor: a binding is keyed by
  its word across an ability, where the truth is its word within an arm.

Narrowing that key needs a stack, not a schema. **No new field is proposed**,
and if implementation finds one needed, it should stop and describe it
separately rather than add it.
