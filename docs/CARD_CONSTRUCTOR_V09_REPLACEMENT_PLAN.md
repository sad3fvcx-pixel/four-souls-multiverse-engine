# Card Constructor v0.9 — the cards that change an event

Twenty-one cards read, rebuild, pass the checker and round-trip perfectly, and
cannot be changed in the Constructor. This is why, and what it would take.

Analysis only. Measured against the engine at `88ca197`. Nothing in `src/`.

---

## 1. Where the path is blocked

**In the walk, and nowhere else.** Measured over the 21:

| | |
|---|---|
| read into author state | **21 of 21** |
| rebuild and pass the checker | **21 of 21** |
| `read → build → read` identical | **21 of 21** |
| offered by the walk | **0 of 21** |

So the contract already holds end to end:

```
read_card → author state → build_card → read_card      ✓ all 21
                     ↑
                  the walk                              ✗ all 21
```

The reader is not missing anything. The writer is not missing anything. The
card language expresses these cards exactly as it should.

The block is two lines, both saying the same thing:

```js
// author.html:330  — chooseAction
const doing = can.effects.filter(e => !e.a_step && !e.replacing && finishable(e));
// author.html:787  — walkable
const offered = can.effects.filter(e => !e.a_step && !e.replacing && finishable(e));
```

And the comment above the first already says why, honestly:

> *"Not the ones that edit an event an ability was handed: this walk does not
> ask whether the ability is a replacement, so offering them would offer a
> card the checker refuses."*

The walk excludes them **everywhere**, because it has no way to know it is
somewhere they are allowed.

---

## 2. One cause, not several

| | |
|---|---|
| cards using such an effect | 21 |
| abilities holding one, marked as replacing | **21 of 21** |
| abilities holding one, not so marked | **0** |

Every one of the 21 is the same shape of problem: an ability that *is* a
replacement, holding an effect that requires one, offered by nothing.

The three effects behind them are used 10, 7 and 4 times. They are not three
classes — they are three members of one, and the model says so itself: each
carries the same published flag.

---

## 3. What the model already publishes

Both halves of the pairing are already public:

| | where | says |
|---|---|---|
| the effect's half | `EffectSpec.replacing` → the effects catalogue | this only works inside a replacement |
| the ability's half | the ability shape's switch, `asked: deeper`, `shown: form` | *"Does it change the event instead of reacting to it?"* |

Its full published shape:

```
name       'replacement'      role     'switch'
kind       'true or false'    asked    'deeper'
describes  'it changes the event instead of reacting to it'
asks       'Does it change the event instead of reacting to it?'
```

---

## 4. The one thing that is missing

**Nothing links the two.** The effect says *I need a replacement ability*; the
ability shape says *I am a switch about replacing*; and no published fact says
that this switch is what that requirement asks for.

Where the pairing actually lives is the validator, `cards/references.py`:

```python
self._replacing = ability.get("replacement") is True
```

and the refusal it drives:

> *"'…' edits the event an ability is handed, and this ability is not a
> replacement"*

So the fact is **enforced in one place and declared in none**, which is the
condition this project has treated as a defect every time it has come up: a
fact enforced in one place and declared in another is a second copy that
drifts, and a fact enforced but never declared is one the page can only
guess at.

The consequence is concrete. To offer these effects where they belong, the
page must ask "does the part I am in replace an event?" — and to ask that
generically it needs to be *told which field answers it*. Today it could only
find that field by writing `"replacement"` into the renderer, which is the one
thing the renderer is not allowed to do.

**This is the missing concept, and it is small**: one published pointer from
the requirement to the question that satisfies it. `ParamShape` already
carries exactly this kind of link for other pairings — `unless`,
`unless_when`, `instead_of`, `describes`, `refers_to`, `names_the_node`. This
is another of the same family, not a new idea.

---

## 5. So: can it be closed without changing runtime, schema or content?

| | |
|---|---|
| **content** | untouched — all 21 cards are correct |
| **schema** | untouched |
| **runtime behaviour** | untouched — nothing about how a game plays changes |
| **the card language** | untouched — no card writes anything new |
| **the vocabulary that describes the language** | **one field added**, so the pairing is declared where it is enforced |
| **the page** | two filters become one question about the part in hand |

The vocabulary addition is a change to how the engine *describes* itself, not
to what it does. That is the same boundary Stage 1 of v0.8 crossed when
`EffectSpec.replacing` was published in the first place — for exactly this
reason, and the docstring says so:

> *"an author choosing what a card does is choosing from these shapes, and a
> fact left on the runtime's side of the boundary is a fact the author never
> hears until the game refuses the card."*

Publishing the requirement without publishing what satisfies it left the job
half done. This finishes it.

---

## 6. Scope: editing, not creating

The ability's switch is `asked: "deeper"` — the expert editor's tier. The walk
asks `first`, so it never puts that question.

- **Editing one of the 21**: the answer is already in author state, read off
  the card. The walk needs only to consult it. **This is the stage.**
- **Making a new replacement ability in the walk**: would need a `deeper`
  question raised to a tier the walk asks, which is a different decision about
  what the simple path is for. **Not this stage.**

So a replacing effect becomes offerable exactly when the part in hand already
says it replaces. A new ability says nothing, and nothing changes there.

Expected: **296 → 317** of 352.

---

## 7. Order

1. **Publish the pairing** — one field on the effect side naming the question
   that satisfies its requirement, derived where the validator enforces it so
   the two cannot drift.
2. **The walk consults the part it is in** — `offered` becomes a function of
   the part rather than a constant, in both places that compute it.
3. **A test that the page names no field and no effect** — the same rule every
   stage has held to.
4. **Prove the count moves 296 → 317**, and that no card outside the 21 moves.
5. **Gate**: pytest, ruff, mypy --strict, `git diff --check`, 352/1045,
   1000-game replay, browser check on a card of each of the three, no JS
   errors.

---

## 8. Deliberately not

- **Making a replacement ability from the walk** (§6).
- **Raising the `deeper` tier** for anything else.
- **Changing any card**, the runtime, or the schema.
- **Writing the field's name into the page** — the whole point of §4.

---

## 9. Risks

| Risk | Weight | What holds it down |
|---|---|---|
| the walk offers a replacing effect where the checker refuses it | **high** | it is offered only when the part in hand says it replaces, which is the same condition the validator applies |
| the published pairing drifts from the validator | medium | derive it from where the enforcement reads, not beside it |
| the page ends up naming the field after all | medium | a test reads the drawing code back, as in every stage since 2.1 |
| this is read as licence to touch the runtime | **high** | nothing about play changes; the change is to what the engine says about itself |

---

## 10. The invariant, unchanged

```
Constructor ──┐
              ├──→ state.card ──→ build_card ──→ CardDefinition ──→ Validator ──→ file
Expert Editor ┘         ↑                                              │
                   read_card ←────────────────────────────────────── the file
```

These 21 cards already make this whole trip. Only the first arrow is closed to
them, and only because the walk cannot ask a question the engine never
published an answer for.
