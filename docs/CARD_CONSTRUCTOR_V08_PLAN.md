# Card Constructor — analysis and plan for v0.8

Everything FSME can do runs one way. A person describes a card, the builder
writes a `CardDefinition`, the checker reads it and the runtime plays it.
Nothing goes back. "My cards" lists names it cannot open, and a card saved last
week can only be edited by opening the JSON.

This is a plan for the return path. It is a harder problem than the last two,
and the measurements below say why: reading a card back is not the inverse of
writing one, and a naive reader silently changes what two shipped cards do.

Everything was measured against the engine at `1a206d2` (v0.7.0).

---

## 1. How reversible the data is today

### What does not exist

- **No inverse of `build_card`.** Nothing reads a `CardDefinition` into the
  form state the page edits.
- **No `to_data` on `CardDefinition`.** It can be built from data and never
  written back to it. The JSON on disk is the only serialised form, which is
  where a reader has to start — and is what `cards_in()` already loads.
- **`mine()` lists names.** It renders `c` as a string per card and offers no
  way in.

### What does exist, and changes the whole shape of this

The engine already contains three normalisers, one per kind of node a card
holds, each turning every accepted spelling into one:

| Function | Reads | Returns |
|---|---|---|
| `runtime/interpreter.py::normalise` | a step | `(name, params, target)` |
| `runtime/condition_evaluator.py::normalise` | a condition | `(name, params)` |
| `runtime/target_resolver.py::normalise` | a target | `(name, params)` |

Checked against every spelling a card file uses:

```
{"gain_coins": 3}                          → ('gain_coins', {'__value__': 3}, None)
{"effect": "gain_coins", "amount": 3, …}   → ('gain_coins', {'amount': 3}, 'controller')
"dice_equals"                              → ('dice_equals', {})
{"dice_equals": 6}                         → ('dice_equals', {'value': 6})
{"target_player": {"as": "victim"}}        → ('target_player', {'as': 'victim'})
```

These are the functions the runtime itself reads cards with. A reader built on
them cannot disagree with the runtime about what a card says, which is the only
guarantee worth having here. **The parsing is already written. What is missing
is that it lives on the runtime's side of the boundary and nothing hands it to
the desk** — exactly the job `runtime/vocabulary.py::engine_vocabulary()`
already does for shapes.

### What was measured

A reader was written on those three normalisers and run over every shipped card
that has rules, then fed back through `build_card`:

| | cards | |
|---|---|---|
| readable | **243** | 69% |
| not readable | 109 | 31% |
| — of which control nodes (`if`, `may`, `choose`, …) | 89 | |
| — a step aimed at a name nothing binds | 11 | |
| — a step carrying `targets` or `store` of its own | 9 | |

Of the 243 readable, **239 survive open → save → open → save unchanged.** The
first save canonicalises — bindings are renamed to `chosen_N`, shorthand is
written long — and the second changes nothing. That is the property an editor
actually needs, and it very nearly holds already.

### What is genuinely lost

Three things, and they are different in kind.

**1. A character's printed attack, on 25 cards.** `PRINTED_NUMBERS` lists
`("health",)` for a character, so `attack` is declared moot for that kind and
`_without_the_moot` drops it. But 93 of 97 shipped characters carry
`"attack": 1`, and `api/view.py` puts it on the card face. Building a character
card with attack today already discards it:

```
build_card(… type: character, health: 2, attack: 1 …) → {"type": "character", "health": 2}
```

This is not a rules bug — a player's combat damage comes from
`BASE_PLAYER_ATTACK`, not the card, and only `_monster_attack` reads
`definition.attack`. It is a **data-loss bug that is invisible today only
because nothing can open an existing card**, and it becomes visible the moment
v0.8 ships. It has to be fixed before, not after.

**2. A nested condition grows a layer every pass.** `stoney`:

```
on disk     {"not": ["is_event_source"]}
read once   {"not": {"of": ["is_event_source"]}}
read twice  {"not": {"of": [{"of": ["is_event_source"]}]}}
```

The condition normaliser puts the list under `of`; writing `of` back as an
ordinary field re-wraps it. Nesting conditions do not round-trip and must be
treated as editor-only until they do.

**3. A card can silently change what it does.** `jawbone` — "Steal 3¢ from a
player":

```
on disk     source_player: {"player_of": "victim"},  target: controller
read once   source_player: "chosen_1",               target: "chosen_2"
read twice  source_player: "chosen_1",               target: "chosen_1"   ← same binding
```

The `player_of` wrapper is dropped on the way in, and by the second pass the
two bindings have collapsed into one: the card now steals from its own
controller. **This is the single most important finding in this document.** A
reader that is merely mostly right turns a working card into a different
working card, with no error anywhere. It is the reason the round-trip test is
the first thing written and the reason a card that does not round-trip must be
refused rather than opened.

### The missing metadata, in full

**One field.** `EffectSpec.primary` — which parameter the shorthand fills —
exists on the spec and is *not published*. Without it nothing outside the
engine can expand `{"gain_coins": 3}`. Conditions need nothing: their own
`ConditionShape` docstring says they have "no shorthand key … one spelling, and
`normalise` turns every accepted form into it", and the measurement agrees.

Everything else a reader needs is already published: `fields`, `picks`,
`written`, `a_list_of`, `shown`, `asked`, `hits`, `replacing`, `used_by`.

### Is a separate author-state needed?

**No.** The existing structure carries everything, on one condition: the reader
must refuse what it cannot read faithfully rather than approximate it. The card
is the only record; adding a second one is §3's option C, and it is rejected
below.

---

## 2. The Expert Editor as a source of truth

It is not one, in the way the brief hopes. **The editor has never opened a
card.** There is no parse anywhere in the page: `startCard()` begins with an
empty `state.card`, and every renderer draws *from author state outward*.

| Primitive | Direction | Reusable for v0.8 |
|---|---|---|
| `bodyHtml` / `nodeHtml` / `chooserHtml` | state → HTML | yes, unchanged, the moment state exists |
| `valueHtml` / `oneByOne` / `aimHtml` | state → HTML | yes, unchanged |
| `saidAs` (the v0.7 read-back) | state → words | yes, and it is the constructor's summary already |
| `at` / `setField` / `setAim` | writes state | yes, unchanged |
| anything reading a `CardDefinition` | — | **does not exist** |

So the good news is real but narrower than it sounds: **every screen already
works on author state, so nothing about display has to be written.** The whole
of v0.8 is the one function that produces that state, plus a way to reach it.

---

## 3. Three architectures

### A — read straight into constructor state

```
card JSON → (the engine's three normalisers) → state.card → every existing screen
```

**For.** The parsing already exists and is the runtime's own. One
representation of a card in flight, which is the `state.card` both ways in
already share. No schema change. The reader belongs beside
`engine_vocabulary()`, which already exists to carry facts across that
boundary. Measured: 69% of shipped cards today, 239 of 243 idempotent.

**Against.** The reader must be complete or refuse, and `jawbone` shows what
"nearly complete" costs. Canonicalisation means opening and saving rewrites a
file that was not edited.

### B — an intermediate author model

```
card JSON → Author Model → state.card
```

**Against.** The author model *is* `state.card`. A layer between them would
have nothing to say that `state.card` does not already say, and would be a
third thing to keep in step with the builder and the runtime. It solves no
problem this analysis found.

### C — author metadata stored beside the card

**Against, firmly.** This is the second on-disk representation of card content
the project has refused at every turn, and it rots the moment anybody edits the
JSON by hand — which is exactly how the 1045 shipped cards were written. It
also cannot help with the shipped content, which has no author metadata and
never will. It buys back only the binding names, which are worth less than the
cost.

### Recommendation: **A**

with one rule that is not negotiable: **a card that does not round-trip is not
opened.** The reader returns either faithful author state or a refusal naming
what it could not read, and the refusal sends the person to the JSON rather
than to a card that will quietly change.

---

## 4. The journey

```
My cards → a card → Your card
                     ├─ what it is called          (a box)
                     ├─ what kind of card          (a box)
                     └─ what it does:
                          1. Deal damage — how much: 2; to a player somebody picks   [change] [remove]
                          2. Add coins   — how many: 3; to whoever controls this card [change] [remove]
                        [Add another thing it does]  [Save]  [Try it in a game]  [Change anything else]
```

This screen already exists. It is v0.7's `sofar()`, which reads a card back
into words from author state and offers add, change and remove. Opening an
existing card lands on it, and `change` walks that action's questions exactly
as it does for a card being made. **The whole user-facing side of v0.8 is
reached by giving `sofar()` a card it did not build.**

A card the reader refuses says so on the same screen, names the part it could
not read, and offers the JSON — not a half-loaded card.

---

## 5. Deliberately not in v0.8

- **Drag and drop** — reordering stays as it is.
- **Templates** — still premature, and this is the capability they were
  waiting on; revisit after.
- **Anything generated.**
- **Collaborative editing.**
- **A new card format** — the whole point is that there is one.
- **Control nodes** — 89 of the 109 unreadable cards. Branching is the next
  question after this one, and it is not this one.
- **Rewriting how bindings are named.** Canonicalisation to `chosen_N` is
  accepted; preserving an author's own binding names is a separate idea that
  would need the card to record them.

---

## 6. The critical questions, answered

**1. Can editing be done without changing the card JSON schema?**
Yes. Nothing in the measurement needed a schema change. One metadata field is
published (`primary`), and one metadata *fact* is corrected (`PRINTED_NUMBERS`
for a character). Neither touches the schema.

**2. Can any existing card be opened?**
No — 69% today, and that is with the reader written. The honest posture is that
this is a feature that works for most cards and says so for the rest.

**3. Which cards need the expert editor?**
Measured, in order: anything with a control node (89), a step aimed at a name
nothing binds (11), a step carrying its own `targets` or `store` (9), and —
until fixed — anything with a nested condition or a `player_of` reference.

**4. Where is the boundary between constructor and expert editor?**
The same one v0.6.1 drew and this does not move: the constructor asks questions
whose answers are single values, and the editor holds everything that is more
of the language. The reader inherits that boundary rather than inventing one —
it opens what the constructor can express and refuses the rest.

---

## 7. Test strategy

Written first, in this order:

| Claim | How |
|---|---|
| **open → save is faithful** | for every shipped card the reader accepts, the rebuilt `CardDefinition` equals the original once bindings are canonicalised |
| **open → save → open → save is stable** | the second save is byte-identical to the first; measured today at 239 of 243, and the target is all of them |
| **a card that cannot be read is refused, not approximated** | the 109 are named and each refusal says which part |
| **`jawbone` and `stoney` specifically** | the two cards that change meaning today get named tests before the reader ships |
| **changing one value changes one thing** | read a card, set one answer, save: exactly that key differs |
| **the two ways in stay equal** | a card opened in the constructor and the same card opened in the editor are one object — the existing equivalence tests extend to read cards |
| **shipped cards do not change** | 352/1045, and the 1000-game replay, unchanged — nothing here should touch a game |
| **a character keeps its attack** | the specific regression the `PRINTED_NUMBERS` fix closes, over all 93 characters |

---

## 8. Order of implementation

1. **Fix the attack loss first**, on its own. `PRINTED_NUMBERS` for a character
   is a one-line correction with a test over all 93 shipped characters. It is a
   live data-loss bug and it should not be bundled into a feature.
2. **Publish `primary`** beside `hits` and `replacing`, the same way.
3. **Write the round-trip test** over all shipped cards, expected to fail.
4. **Write the reader**, beside `engine_vocabulary()`, on the three
   normalisers. Refuse rather than approximate.
5. **Fix `player_of` and nested conditions**, or refuse them explicitly — decide
   by what the round-trip test says, not in advance.
6. **Open it from "My cards"**, landing on `sofar()`.
7. **Gate**: `pytest`, `ruff check .`, `mypy src --strict`, `git diff --check`,
   352/1045, 1000-game replay, expert editor unchanged, no JS errors.

Steps 1–3 are worth doing and reviewing before any reader is written.

---

## 9. Risks

| Risk | Weight | What holds it down |
|---|---|---|
| **a card silently changes meaning** | **high** | demonstrated on `jawbone`; the round-trip test is written first and the reader refuses rather than approximates |
| opening and saving rewrites an unedited file | medium | accepted, and made safe by idempotence: the second save changes nothing |
| the reader drifts from the runtime | low | it is built on the runtime's own normalisers, not a second parse |
| 31% of cards cannot be opened | medium | say so on the screen, name the part, offer the JSON |
| scope creep into control nodes | high | they are 89 of the 109 and will look like the obvious win; they are the next round |
| the fix to `PRINTED_NUMBERS` changes a game | low | nothing reads a character's attack in play; checked, and the replay will confirm |

---

## 10. The invariant, unchanged

```
                    ┌──────────────── (the engine's own normalisers) ──────────────┐
                    ↓                                                              │
Constructor ──┐                                                                    │
              ├──→ state.card ──→ build_card ──→ CardDefinition ──→ Validator ──→ Runtime
Expert Editor ┘
```

One card model, one builder, one checker, one runtime — and now one reader,
which is the runtime's own. A card still says nothing about which way in made
it, and nothing about whether it was made or opened.
