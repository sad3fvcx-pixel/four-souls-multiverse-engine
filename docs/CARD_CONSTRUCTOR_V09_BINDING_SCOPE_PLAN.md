# Card Constructor v0.9 — who owns the name of a choice

Stage 1 made a name survive a round trip. It opened two cards. This asks the
question that stopped it: when a card names something it chose, **whose name is
that** — the card's, the ability's, the branch's, or the program's?

Analysis only. Nothing changed. Measured against the working tree with Stage 1
applied but **not yet committed**, so every number below includes it.

---

## 1. Where a name is made, kept and read

| | makes | keeps | reads |
|---|---|---|---|
| a card's `targets` entry — `{"target_player": {"as": "rival"}}` | ✓ | ✓ | |
| a target written inline in a step | ✓ | ✓ | |
| `store` on a step | ✓ | ✓ | |
| `as` on a control node | ✓ | ✓ | |
| a step's `target: "rival"` | | | ✓ |
| a worked-out value's `of` / `from` / `minus` | | | ✓ |
| reader `_bound_by` | | keyed by name | ✓ |
| reader `_as_chosen` | | since Stage 1 | ✓ |
| reader `_the_card_s_own` | | tells a card's word from ours | |
| writer `_written_body` (a target) | falls back | **honours `described.get("as")`** | |
| writer `_pick_out` | `chosen_N` | **honours a given name** (Stage 1) | |
| writer `_written_node` | | **skips anything `BY_BINDING`** | |
| runtime `target_resolver.normalise` | | returns `as` in the params | ✓ |

---

## 2. What the names actually are

Over every shipped card: **186 names across 130 cards.**

| where it is made | |
|---|---|
| in the ability's own `targets` | 122 |
| inside a step | 64 |

| what it is | |
|---|---|
| **A** — said again somewhere else | **116** |
| **B** — never said again | **66** |
| **C** — the same name made more than once in one card | **4** |

And the question that decides the model:

> **Not one name in the shipped content is said outside the ability that made
> it.** 116 of 116.

That took two passes to establish. A first probe reported three crossings, all
in `the_curse` — and all three were **my own false positives**: that card writes
`"position": "top"`, which is a value meaning the top of a deck, and my probe
matched it against the binding named `top`. `move_cards.position` carries
`refers_to = ''`, so the engine never confuses them. Only a parameter that says
it names something can be naming something, which is what the reader already
asks and what a text search cannot.

---

## 3. The scope a name lives in

**Global — `name → value` — is wrong**, and four cards prove it. `the_curse`,
`sleight_of_hand` and `sack_head` each write three `choose` options whose steps
all name their choice `top`, `ordered` or `raised`:

```
choose ─┬─ option 1 → deck_top of the loot deck      as "top"
        ├─ option 2 → deck_top of the treasure deck  as "top"
        └─ option 3 → deck_top of the monster deck   as "top"
```

Three different choices, one word. It is safe on the card because **only one
option ever happens** — and Stage 1 hit this exactly: matching on the name
alone merged them, and the rebuilt card drew three times from the loot deck.

**Ability scope is right**, and it is already the engine's own model: a context
is built per ability and shares nothing with the next, which is why
`NodeShape.own_names` exists and why `_bound_by` reads one ability at a time.
Nothing measured needs more.

But ability scope is not quite *uniqueness*: within one ability, sibling
branches may reuse a word. So the honest statement is

> a name identifies one choice **on the path through the card that runs**,
> not one choice per ability

and the only thing that breaks it is gathering every choice from every branch
into a single list — which is what the builder does. That is why Stage 1 keeps
names for the 122 bound by an ability and drops them for the 64 written inside
a step.

**Node scope would be stronger than anything in the content needs**, and no
card measured requires it.

---

## 4. What `BY_BINDING` actually says

Its own declaration, in full:

> `BY_BINDING` — the name a target is bound under, so that later steps can
> point at it. **Written in every card file and answered by no author**:
> whatever is writing the card chooses the name, and a form offering the box
> takes an answer it is about to overwrite.
>
> Anything showing a parameter to a person reads this **to decide what to
> offer**.

So it governs **what to ask a person**. It says nothing about what to keep.
The reader and the writer both read it as *do not keep*, which is a stronger
claim than it makes — and they do not even agree with each other:

| | parameters | does the writer write it? |
|---|---|---|
| a target's `as` | **46** | **yes** — `_written_body` must, or nothing could be pointed at |
| a control node's `as` | **7** | **no** — `_written_node` skips it |

Every `BY_BINDING` parameter in the engine is one of those 53, and there is no
effect among them.

**So no change to what `BY_BINDING` means is needed.** It already means
"never ask". What is inconsistent is that one writer honours such a name and
the other discards it. A control node's `as` should be written when author
state carries one, exactly as a target's already is, and still never asked for.

Which cards need it:

| card | keeps a name under | said again? |
|---|---|---|
| `xii_the_hanged_man` | `choose` ×3 | yes |
| `the_bloat` | `store` ×2 | yes |
| `crystal_ball`, `cheese_grater`, `the_capricious`, `devil_deal` ×2, `mulligan` | `choose` / `may` | **no** |

The five that never say the name again still need it kept: it is how two
choices in one ability stay two choices rather than colliding on a default.

---

## 5. Why `chosen_N` still appears — and where the truth should live

`described.get("as")` existed all along in `_written_body`, for targets. It
was never consulted by `_pick_out`, which is the path that rebuilds an
ability's `targets` — so every name went in one side and a fresh one came out
the other. Stage 1 closed that.

`chosen_N` still appears, and should: it is for a choice the card never named.
The rule that follows from the measurements is

> **the card's own word if it has one, and ours only if it does not** — and
> ours must be recognisable as ours, or reading a card back hands the author
> our handwriting as if it were theirs.

That last clause is not hypothetical: without it a card grew a new name every
time it was opened.

---

## 6. What would open, measured rather than guessed

The guards were lifted in a scratch process — nothing on disk — and every card
rebuilt and read back:

| | read | whole | refused by the checker |
|---|---|---|---|
| today | 324 | 324 | 0 |
| if a worked-out value were read | **326** | **325** | **1** |

So of the two cards a stable name would let through, **one comes back whole
and one produces a card the checker refuses.** Not automatic.

The 28 still refused:

| | cards | turns on ownership? |
|---|---|---|
| a step picks something out for itself | **16** | **no** — a different problem |
| a control node keeps a name (`choose` 5, `may` 2) | 7 | **yes** — §4 |
| a value worked out from a name | 2 | **partly** — 1 of 2 |
| a step keeps its result (`store`) | 1 | **yes** |
| an answer built from several names | 1 | **yes**, and needs more besides |
| a control node points at a name | 1 | **yes** |

**Twelve of the 28 turn on ownership; sixteen do not.**

---

## 7. What to do, in order

1. **A control node's `as` written when state carries one** — the
   inconsistency in §4, no change to `BY_BINDING`'s meaning. 8 cards.
2. **The worked-out value** — 2 cards, and one of them needs whatever the
   checker is complaining about understood first.
3. **`store`** — 1 card, same family.
4. **An answer built from several names** — 1 card, and it needs an answer to
   hold more than one thing.
5. **A step's own target** — 16 cards, and not this thread at all.

---

## 8. Risks

| Risk | Weight | What holds it down |
|---|---|---|
| a kept name merges two choices | **high** | it already happened once; sibling branches reuse words, and the fix was to keep only what an ability binds |
| `BY_BINDING` is read as "never write" again | medium | it says "never ask"; the two writers disagreeing is the evidence |
| our invented names are mistaken for the card's | **high** | `MADE_UP` is declared beside what makes them |
| lifting a guard opens a card the checker refuses | medium | measured: 1 of the 2 |
| this is taken as licence to open the 16 | medium | §6 says which turn on ownership and which do not |

---

## 9. The answer to the question

A name belongs to **the card**, and means something **within the ability that
wrote it**, on **the path that runs**. It is not the runtime's: the runtime is
handed it. It is not the program's: ours are recognisable and are only ever a
substitute. And it is not global — four cards say the same word three times
and mean three different decks.
