# Card Constructor — analysis and plan for v0.7

The walk shipped in v0.6.1 makes one card do one thing. A card that deals two
damage and then gives three cents is, as far as the engine is concerned, the
same card with a second item in a list it already has — and as far as the walk
is concerned, impossible.

This is a plan for closing that gap. As before: no new pipeline, no second card
model, no runtime of its own.

Everything below was measured against the engine at `3338241` (v0.6.1).

---

## 1. What already exists

### The whole back end already does this

The single most important finding. Two effects in one ability, built through
the ordinary builder:

```
build_card(… effects: [deal_damage amount 2 → target_player,
                       gain_coins  amount 3 → controller] …)
```

produces

```json
{ "trigger": "on_play",
  "effects": [ { "effect": "deal_damage", "amount": 2, "target": "chosen_1" },
               { "effect": "gain_coins",  "amount": 3, "target": "chosen_2" } ],
  "targets": [ { "target_player": { "as": "chosen_1" } },
               { "controller":    { "as": "chosen_2" } } ] }
```

The checker accepts it and the runtime plays it. `build_card` already hoists
each step's aim into its own binding with a distinct generated name; the
validator already walks a list of steps in order and already knows that a value
one step stores is visible to the next; the executor already runs them in
sequence.

**No change is needed to the card schema, the builder, the validator or the
runtime.** v0.7 is a user-interface change and nothing else.

### The Expert Editor already offers it

`bodyHtml` draws any `a_list_of` field as a list of nodes with *Add something
that happens*, *remove*, *↑* and *↓*. An author in the editor can already build
the two-step card above. The walk is the only place that cannot.

### What the shipped content says about how much this matters

Measured over the 352 shipped definitions that have rules:

| | cards |
|---|---|
| busiest ability has 1 effect | 242 |
| busiest ability has 2 effects | 59 |
| busiest ability has 3+ effects | 33 |
| **2 or more** | **92 (26%)** |
| at most one ability on the card | 314 (89%) |

So a second effect in one ability is common and a second *ability* is rare.
That is the right order to build them in, and it is the metadata's order too.

### The load-bearing measurement

Of the 93 abilities with two or more effects, only **40 are flat sequences**.
The other 53 use a control node — `if`, `may`, `choose`, `for_each`, `repeat`,
`sequence`, `stop`. The single most repeated shape in the whole content is

```
roll_dice → if → if → if      (14 abilities)
roll_dice → if                (13 abilities)
```

which is branching, and branching is explicitly out of scope.

Of the 40 flat sequences, **34 use only actions the walk already offers**; the
other 6 are held back because they edit a replaced event. 32 of the 40 are
exactly two steps long.

**So flat multiple actions reaches 34 of 352 implemented cards — about 10%.**
That is honest and it is still worth doing: it roughly doubles what somebody
can say in the walk, and every one of those 34 is a card a person would
plausibly want to write. But it should not be sold as "most multi-effect
cards", because the majority of those need `roll_dice → if`.

Examples now in reach: `viii_justice` (draw loot → gain cents), `pickpocket`
(lose cents → gain cents), `pestilence` (damage → damage), `goat_head`
(discard → draw), `xxi_the_world` (reveal hand → draw loot).

### What the metadata already says

| Fact | Where it lives | Already used for |
|---|---|---|
| an ability holds a *list* of steps | `ability.effects.a_list_of = "step"` | the editor's list renderer |
| what a step may be | `KINDS.step` → `can.effects` + step-shaped structures | the action screen |
| what each step asks | `asks`, `asked`, `role`, `choices`, `means` | every walk question |
| what a step may be aimed at | `hits` × `gives` | the "who does this happen to" question |
| what an earlier step chose | targets with `after: true` — `previous_target`, `previous_result`, `group` | offered in the editor, in their own group |
| which effects keep a result | `stores` | the reference control |

Nothing here is missing for a flat sequence.

### The answer to "new layer or extend the constructor"

**Extend the constructor.** There is no layer to add: the model already holds a
list, the builder already writes it, the editor already edits it. What the walk
lacks is a screen that asks "anything else?" and a second pass over the same
question machinery.

---

## 2. What can be reused, and what must be added

Reused unchanged:

| Piece | Role in v0.7 |
|---|---|
| `questions()` | already derives an action's questions; becomes a walk over a list of actions |
| `ask(n)` / `oneByOne` / `valueHtml` | every question, unchanged |
| `aimHtml` / `fits` | the target question for each action, unchanged |
| `chooseAction` / `finishable` | the action list, unchanged, shown a second time |
| `addNode` / `dropNode` / `moveNode` | adding, removing and reordering a step — already generic |
| `at` / `setField` / `setAim` / `drawn` | writing answers, unchanged |
| `build_card` / `check_card` / `show_card` | unchanged |
| `EffectSpec`, `asks`, `values_mean`, `hits`, validator | unchanged |
| `state.card` | unchanged — the second action is one more item in a list it already has |

Added:

- `walk.step` becomes an index into the step list rather than a fixed path.
- One screen between actions: *"Add another thing this card does"* / *"That's
  all"*, plus a list of what has been said so far, with remove and reorder
  reusing the editor's own handlers.

**No new metadata is required.** This is the second most important finding
after "the back end already works".

The "anything else?" question is not a special case bolted on: `effects` is
declared `a_list_of`, and a list is the language's own way of saying more than
one is allowed. Reading the offer off `a_list_of` rather than writing it into
the walk means the same screen will extend to a second *ability* later without
new code, because `abilities` is a list for the same reason.

---

## 3. Three user journeys, compared

### A — ask, then ask again

```
kind → action → its questions → "anything else?" → action → its questions → done
```

**For.** It is what already exists, run twice. Nothing new to learn, nothing
new to draw, no new state. Reaches all 34 cards. Costs a median of 4 questions
for a two-action card, which stays a walk rather than becoming a form.

**Against.** A person cannot see the whole card while answering. Reordering is
awkward mid-walk. The "anything else?" screen is one more click on the common
path, where most cards are still one action.

### B — templates

```
kind → template → change the actions in it
```

**For.** Fewest decisions for a beginner. Reads like the printed cards people
already know.

**Against.** It requires either a store of partly-filled cards (see §4) or a
way to open an existing card, which does not exist today. It also answers a
question nobody has asked yet: the walk has been shippable for one release, and
there is no evidence about which shapes people reach for. **Premature.**

### C — a visual chain

```
kind → build the sequence, seeing all of it at once
```

**For.** Shows the whole card. Natural for reordering. Would extend to
branching later.

**Against.** It is the Expert Editor with different paint. The editor already
draws the list, with add, remove and reorder. Building a second one means two
things to keep in step — exactly the duplication the whole design avoids. And
"seeing all of it at once" is the thing the walk exists to *not* do.

### Recommendation: **A**, with one borrowing from C

Take A, and put the list of what has been said so far on the "anything else?"
screen, drawn by the editor's own `bodyHtml`. That gives C's visibility and
reordering at the moments they matter, at no cost in duplicated code, and keeps
the one-question screens for the answering.

---

## 4. Templates — not yet, and here is what is actually missing

**Can a template be described using only the existing `CardDefinition`?**
Technically yes: a template is a card with some answers already in it. But it
cannot be *used* today, and the reason is worth stating plainly:

> There is no inverse of `build_card`. Nothing reads a `CardDefinition` back
> into the form state the page edits. "My cards" lists names and cannot open
> one.

So shipping templates means one of two things:

1. **Store templates in the page's wire format** (`state.card`). No new reader
   needed — but it puts a second on-disk representation of card content beside
   `CardDefinition`, which is the thing this project has refused at every turn.
   The wire format is form state, not a card, and it should not become a file.

2. **Write the inverse** — `CardDefinition` → form state. Real work, and it has
   to agree with `build_card` exactly or a card will change by being opened.
   It needs its own round-trip test: build → write → read → build again, byte
   for byte, over every shipped card.

Option 2 is the right one, and it is worth more than templates: it is what
makes "edit a card I saved last week" possible, which is a plainer gap than
"start from a template". It is also bigger than v0.7 should be.

The evidence does not argue for templates yet either. Of the 40 flat sequences
in the shipped content, only a handful repeat: `deal_damage → deal_damage` (3),
`add_modifier → add_modifier` (3), `cancel_stack → end_turn` (4),
`add_modifier → require_attack` (3), `take_card → make_eternal → move_cards`
(3). Nothing like a set of canonical card shapes to seed a template library
from — and the four examples in the brief (a simple treasure, an event card, a
combat item, a monster with a reward) are mostly distinctions of card *kind*
and printed numbers, which the walk already asks about, not distinctions of
what the card does.

**Recommendation: do not build templates in v0.7.** Revisit once the inverse
reader exists and there is usage evidence about which shapes recur.

---

## 5. Metadata changes needed

**None.**

If implementation finds otherwise, the rule from the previous two rounds
applies: stop and report the missing concept rather than writing a special case
into the page.

One thing to watch, already known: three effects (`cancel_stack`,
`copy_effect`, `require_attack`) build and validate but the runtime refuses,
because `EffectSpec.hits` is deliberately coarser than they are. Two of the 34
reachable sequences use them (`cancel_stack → end_turn`,
`add_modifier → require_attack`). A finer target vocabulary would fix that and
is the clearest metadata gap the project has — but it is a separate piece of
work, and v0.7 should not smuggle it in.

---

## 6. Order of implementation

1. **Test first, again.** Extend the equivalence test to sequences: for a
   sample of ordered pairs of offerable actions, build the card by the walk and
   by the editor and compare byte for byte. The invariant is the deliverable;
   if it cannot be made to hold, the design is wrong.
2. **Generalise `questions()`** from one step to the step list. No new screens
   yet — verify the same single-action card still comes out identical.
3. **The "anything else?" screen**, driven by `a_list_of`, with the list drawn
   by `bodyHtml` and remove/reorder wired to the existing handlers.
4. **A second pass** through `chooseAction` for the next action.
5. **Measure**: how many questions a two-action card costs, in a browser,
   before and after.
6. **Gate**: `pytest`, `ruff check .`, `mypy src --strict`, `git diff --check`,
   shipped cards at 352/1045, 1000-game replay unchanged, Expert Editor
   unchanged.

Steps 1–2 are the risky ones and are worth doing on their own before any screen
is drawn.

---

## 7. Test strategy

| Claim | How it is checked |
|---|---|
| the walk and the editor make the same card | both ways in, byte for byte, over a sample of ordered action pairs |
| a two-action card passes the checker | every sampled pair, no exceptions list |
| a two-action card plays | in a real game via `Workbench.show_card`, with the known coarse-`hits` exceptions named |
| order is preserved | the built `effects` list is in the order the questions were answered — the runtime runs them in that order and a later step can read what an earlier one stored |
| each action keeps its own aim | two aims become two bindings with distinct names, and each step points at its own |
| the walk still offers nothing it cannot finish | unchanged rule, re-checked with sequences |
| existing cards unchanged | 352/1045, 1000-game replay identical |
| the Expert Editor is unchanged | its own tests, plus a browser check that a walked two-action card opens in it unconverted |
| the page names nothing | the existing test that walks every published effect name |

The sample in the first two rows should be bounded — the full cross product of
58 actions is 3,364 cards and the suite already spends four minutes. A fixed
sample of a few hundred pairs, chosen deterministically, is enough to catch a
walk that agrees about one order and not another.

---

## 8. What is deliberately not in v0.7

- **Branching** — `if`, `may`, `choose`, `for_each`, `repeat`. This is where
  the majority of real multi-effect cards live, and it is the obvious next
  question after v0.7. It is not this one.
- **Several abilities on one card.** 89% of implemented cards have at most one,
  and the mechanism built here extends to them later for free.
- **Stored values.** `roll_dice → if the roll was 6` is branching by another
  name.
- **Templates.** See §4.
- **Drag and drop.** The editor's ↑/↓ already reorders, and it works with a
  keyboard.
- **Anything generated.** No suggestions, no "cards like this one", nothing
  invented on the author's behalf.
- **A finer target vocabulary.** Needed, and separate.

---

## 9. Risks

| Risk | Weight | What holds it down |
|---|---|---|
| the walk becomes a form | medium | keep one question per screen; measure the question count and stop if a two-action card costs more than about six |
| "anything else?" taxes the common path | medium | most cards stay one action; the screen must make *done* the obvious answer, not the second option |
| the two ways in drift apart | low | the equivalence test is written first and covers ordered pairs |
| the second action's target question feels repetitive | low | targets marked `after: true` already mean "what the last step chose" and are already offered; no new metadata |
| scope creep into branching | **high** | the measurement in §1 makes branching look tempting because it is where the content is. It is a bigger design and needs its own round. |
| a card that builds but will not play | low | the three coarse-`hits` effects are already named in a test, and the last screen already plays the card |

---

## 10. The invariant, unchanged

```
Constructor ──┐
              ├──→ state.card ──→ build_card ──→ CardDefinition ──→ Validator ──→ Runtime
Expert Editor ┘
```

One card model, one builder, one checker, one runtime. A card says nothing
about which way in made it, and moving between the two converts nothing. If any
part of v0.7 needs a second format to work, that part is wrong.
