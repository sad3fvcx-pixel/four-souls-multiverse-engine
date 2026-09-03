# Card Constructor v0.9 — the scope a name really has

The previous analysis established that a name is arm-scoped and that the rule
already exists in `cards/references.py`. This measures the rule exactly,
against every shipped card and against cases built to break it, and asks the
question the implementation turns on: **is this solved by widening what the
editor can represent, or by changing the card language?**

Analysis only. Nothing was changed. Measured at `bcf7b4a`.

**The answer: by widening the editor's representation.** Nothing in the card
language, the runtime, the schema, the rules, the effects or the content needs
to change. What has to change is that author state keeps a binding's name in
every case, and that the writer's notion of *which two choices are the same
one* becomes `(name, arm)` where it is now `name`.

---

## 1. The scope model, measured

Every read of a bound name in shipped content, classified by the scope it
crosses. An arm is the namespace the checker creates: entering a key in
`BRANCHES` copies the visible names, so the arm is *the list that key holds* —
which is why two steps of one `effects` share names and two modes of one
`choose` do not, each mode carrying its own `effects`.

| | | |
|---:|---|---|
| 12 | **A** | the ability → the ability |
| 26 | **B** | one arm → the same arm |
| 102 | **C** | an outer scope → a nested branch |
| **0** | **D** | a nested scope → outside it |

A, B and C all occur and must stay legal. **D does not occur once in the
content** — and it is not merely absent, it is refused:

```
abilities[0].effects[1].target: 'inner' is bound, but not where this can see it
```

Four further rules, each put to the checker rather than assumed:

| | |
|---|---|
| a name bound by a step's own list, read by a later step in the same arm | **accepted** |
| the same, read by an *earlier* step | refused — *not where this can see it* |
| a name bound inside a `may`, read after the `may` | refused |
| two steps in one arm binding the same word | refused — *already bound by another target* |

The last is the one that matters most for what follows: **within one arm a
name is unique.** So `(name, arm)` is a key, and nothing in the content
violates it.

---

## 2. Where the data is lost

Three ways a card may write a binding, put through the pipeline one at a time
with everything else held equal:

| written | reader | author state | written back | the card's word |
|---|---|---|---|---|
| in the ability's own list | opens | the aim, inside the step, with `aim_name` | `targets: [{…"as": "victim"}]` | **survives** |
| inline where it is used | opens | the aim, inside the step, **no `aim_name`** | `target: "chosen_1"` | **lost** |
| in a step's own list | **refuses** | — | — | — |

And the structural fact behind all three: **author state has no binding
container.** It holds an aim per step —

```json
{"id": "deal_damage", "fields": {"amount": 1},
 "aim": "target_player", "aim_fields": {}, "aim_name": "victim"}
```

— and the ability's `targets` list in author state is **empty**. The list in
the rebuilt card is produced by the writer *gathering* every aim as it walks,
and `_pick_out` decides that two aims are the same binding when they carry the
same word:

```python
already = [one for one in aimed
           if target in one
           and (str(one[target].get("as", "")) == called if called
                else _without_name(one[target]) == written)]
```

That gathering list is **one per ability** (`_written_part` puts it wherever
the shape says the part keeps its targets; only `ability` declares such a
place). So the writer's key is `name`, across the whole ability.

Which is right within an arm and wrong across arms. It is exactly why the
reader throws an inline name away — the comment says so:

> The builder gathers every choice into one list for the ability, where a name
> has to mean one thing — and a card may call two choices in two different
> branches by the same word.

Two consequences, both measured:

- **57 of 179 bindings** in shipped content are written inline, and every one
  of them loses its word. **37 cards** come back with `chosen_N` where the
  author wrote something.
- **24 of 179** are written in a step's own list, and every one of those cards
  is refused rather than risk the merge.

The ability-level key is the single cause of both.

---

## 3. The minimal model

The shape in the brief —

```
Ability
 └── Scope
      ├── bindings
      └── child scopes
```

— is the right model, and the measurement says something more useful about it:
**it does not have to be materialised.** The writer already walks the tree and
already knows when it enters a branch, because that is the same walk the
checker makes. So the minimum is two changes of meaning, not a new container:

1. **Author state keeps the card's word in every case**, inline included. It
   is dropped today only because the key is ability-wide; under `(name, arm)`
   there is nothing to protect against.
2. **The gathering list becomes one per arm**, created on entering a branch
   exactly as the checker copies its namespace, and consulted only within it.

Put to the case the brief names:

```
choose
 ├ arm A: bind top
 └ arm B: bind top
```

Two arms, two lists, two bindings, and both keep the word `top`. Nothing
merges them, because nothing compares them. `the_curse` writes exactly this
three times over and is the card that forced the current behaviour.

Where an arm's bindings are *written* needs no new place either: a step may
carry its own `targets`, the interpreter takes them off the node before the
effect is looked at, and a name bound there is visible to later steps in the
same arm — all three measured above. So an arm's bindings go on the step that
first needs them, and the ability's own list stays what it is.

---

## 4. What the writer would have to reproduce

| | |
|---|---|
| the original name | yes — it is in author state already for two of the three kinds, and dropped from the third only because of the ability-wide key |
| the original scope | yes — the arm is where the writer already is when it writes the step |
| the nesting | yes — arms nest because the walk nests; C is simply "found in an enclosing list" |

The four cases, as the tree behaves **today**:

| case | checker | reader | note |
|---|---|---|---|
| 1 — bound in an arm, used in that arm | accepts | **refuses** | the seventeen-card class |
| 2 — the same word in two arms | accepts | opens | two bindings kept, **both words lost** |
| 3 — an outer name used inside an arm | accepts | opens | `outer` survives |
| 4 — bound in an arm, used outside it | **refuses** | refuses | correctly, and must stay so |

Case 4 is already enforced by the checker independently of any of this, which
is what makes widening the other three safe: the boundary is not being
maintained by the reader's refusal, so relaxing the reader does not relax the
boundary.

---

## 5. The twenty refusals, assessed

Every one of them is a **valid card** — the checker accepts all twenty. The
columns are what makes each hard: how many distinct arms bind, how deep the
deepest binding sits, whether an answer names several, and whether any name is
read outside the arm that bound it.

| card | blames | binds at | arms | depth | several | non-local reads |
|---|---|---|---|---:|---:|---:|
| `brimstone` | `deal_damage` | arm | 1 | 1 | – | – |
| `dingle` | `add_counter` | arm | 1 | 1 | – | – |
| `epic_fetus` | `deal_damage` | arm | 1 | 1 | – | – |
| `guppy_s_paw` | `destroy_treasure` | arm | 1 | 1 | – | – |
| `host_hat` | `deal_damage` | arm | 1 | 1 | – | – |
| `mulliboom` | `deal_damage` | arm | 1 | 1 | – | – |
| `pestilence` (base) | `divide_damage` | arm | 1 | 1 | 1 | – |
| `the_habit` | `recharge` | arm | 1 | 2 | – | – |
| `the_lamb` | `lose_soul` | arm | 1 | 2 | – | – |
| `the_lost` | `recharge` | arm | 1 | 2 | – | – |
| `rainbow_tapeworm` | `copy_card` | arm | 1 | 2 | – | – |
| `ultra_greed` | `add_counter` | arm | 2 | 2 | – | – |
| `g_fuel` | `recharge` | ability + arm | 2 | 2 | – | 1 |
| `pestilence` (alt) | `deal_damage` | ability + arm | 2 | 1 | – | 2 |
| `dead_bird` | `take_card` | ability + arm | 2 | 2 | – | 2 |
| `finger` | `swap_cards` | ability + arm | 2 | 2 | 1 | 1 |
| `incubus` | `reveal_hand` | arm | 3 | 4 | 1 | 1 |
| `famine` | `discard_loot` | ability | 1 | 0 | – | 2 |
| `viii_justice` | `draw_loot` | ability | 1 | 0 | – | 2 |
| `the_d4` | `for_each` | ability | 1 | 0 | – | 2 |

**Likely to open** — twelve cards binding in a single arm, at depth one or
two, with no name leaving its arm: `brimstone`, `dingle`, `epic_fetus`,
`guppy_s_paw`, `host_hat`, `mulliboom`, `pestilence` (base), `the_habit`,
`the_lamb`, `the_lost`, `rainbow_tapeworm`, `ultra_greed`.

**Needs the two-level case to work as well** — four cards binding both at the
ability and inside an arm: `g_fuel`, `pestilence` (alt), `dead_bird`,
`finger`. Nothing measured says these cannot work; they are simply the ones
where an arm list and the ability list must both be consulted, so they are the
proof cases rather than the easy ones.

**Hardest, and not promised** — `incubus`: three arms, four levels deep, an
answer naming several, and a name read one arm deeper than it was bound. It is
legal and the model covers it in principle. Whether the reader follows it
faithfully is something to measure, not to assume.

**A different sentence** — `famine`, `viii_justice` and `the_d4` bind nothing
in a step. They refuse because a worked-out value or a `for_each` domain names
a binding the reader would drop. They should follow once a binding survives
where it was made, but they are not step-local bindings and should not be
counted as such.

So: twelve straightforward, four proof cases, one open question, three that
come along behind. **No claim that all twenty open.**

---

## 6. What does not have to change

Checked one by one, and each answer is measured rather than assumed:

| | |
|---|---|
| **card language** | nothing. Every construction involved is already written in shipped cards and already read by the runtime. |
| **runtime execution** | nothing. A step's `targets` is taken off the node before the effect is looked at and resolved like any other; this has always been so. |
| **schema** | nothing. There is no schema document to change — `SCHEMA = "1"` is a version stamp, and the shapes are derived from the engine. |
| **rules / effects** | nothing. No handler, no registration, no vocabulary of the game. |
| **content** | nothing. All twenty refused cards are already valid; the checker accepts every one. |
| **`BY_BINDING`** | unchanged. It still says the name is written for the author, which stays true. |
| **`refers_to`** | unchanged. It still says which namespace a name comes from. |
| **`names_at_least`** | unchanged. Cardinality is a separate axis and stays one. |

One thing is currently unpublished and would have to be said, and it is a
publication rather than an invention: **which nodes may bind, and where a name
is visible.** `a_list_of == "target"` is the existing way to say the first, and
only `ability` uses it though the engine accepts it anywhere. `BRANCHES` is the
existing statement of the second, and nothing in the catalogue carries it —
no published key mentions scope, visibility, branch or arm. `own_names` is the
nearest neighbour and is the right idea at the wrong granularity: it marks a
boundary, but only on `ability` and `static`, and only as a switch.

**No new field is required by this analysis.** If implementation finds one, it
should stop and describe it separately, as this document was asked to.

---

## 7. Risks

1. **The merge is load-bearing.** `_pick_out` merging two aims with one word
   is what makes "damage a player and steal a cent from them" mean one player.
   Narrowing the key to `(name, arm)` must not narrow it further by accident,
   or that card becomes two choices. The 26 B-reads and 12 A-reads are the
   cases that would break, and they are the ones to measure first.
2. **Silent breakage.** Case 2's failure mode is not an error — it is a card
   that still loads, still passes the checker, and chooses the wrong thing.
   Only the round-trip contract catches it, which is the same lesson Stage 1B
   taught.
3. **Order within an arm.** A name must be bound before it is read; the
   checker refuses the other way round. A writer that puts an arm's bindings
   anywhere but on the step that first needs them can produce a card the
   checker rejects, or worse, one it accepts with the wrong reading order.
4. **`own_names` at the wrong granularity.** Anything that reads it as *the*
   boundary will place scopes at the ability, which is the model this analysis
   disproves. It should be published alongside, not reused.
5. **The four two-level cards.** An arm list and the ability list must both be
   in view at once. This is the part of the model least exercised by anything
   already working, and `dead_bird` is the smallest example of it.

---

## 8. What this establishes

The success criterion was proof that the problem is solved by extending the
editor's representation rather than by changing the card language. The
measurements give it:

- every construction involved is already legal, already written in shipped
  cards, and already executed by the runtime — twenty of twenty refused cards
  pass the checker;
- the scope rule that governs them is already implemented and already obeyed,
  with **zero** violations in the content and enforcement for the one case
  that must stay forbidden;
- the only thing that disagrees is the editor: it keys a binding by name
  across a whole ability, where the truth is name within an arm — which loses
  a word in 37 cards and refuses 17 more.

Nothing above proposes a field, a name, or a data shape. That is the next
stage, and it should begin by measuring the twelve straightforward cards
against the A and B reads that already work.
