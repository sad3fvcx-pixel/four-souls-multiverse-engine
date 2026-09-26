# `DRAWS` — not the second copy it looks like

Analysis only. Nothing in `src/`, `tests/` or `content/` was changed, nothing
was committed. Measured at `bff6cd0`.

Runtime behaviour, the card language, `when`, event fields and step-local
bindings were not touched, and nothing here proposes touching them.

The stage was set up to ask whether `DRAWS` is another `CARD_KINDS`. **It is
not**, and saying so plainly matters more than making the analogy fit:
`CARD_KINDS` restated a fact the model already held, and `DRAWS` states a fact
the model does not hold and should not. What *is* wrong is different, smaller
in each instance and larger in total — **ten enumerations of the same eight
words, two of which have already drifted and pass anyway.**

**Classification: D — mixed.** Detail in §5.


## 1. Current architecture

```
capabilities.py::_fields
    computes `shown` for every parameter — one of eight words
        ↓  published in the catalogue
author.html
    the dispatcher      an if-chain, one branch per word   ← what the page can draw
    const DRAWS         the same eight, listed             ← a second statement of it
    drawable(node)      every field's `shown` is in DRAWS
        ↓  one consumer
    KINDS.step.of()     which control nodes the step chooser offers
```

`DRAWS` is declared at `author.html:1074` and read in exactly one place —
`drawable`, at line 1072 — and `drawable` itself has exactly one consumer:

```js
step: { of: () => can.effects.concat(
          can.structures.filter(x => x.a_step && drawable(x))), … }
```

So the whole reach of `DRAWS` is: *which control nodes appear in the chooser
inside a body.* Nothing else consults it.


## 2. What `DRAWS` actually describes

Not the card language, not card-type metadata, not UI layout. It is a
**renderer capability**: which of the model's eight ways of showing a field
this particular page has a control for.

That is a different question from the one `shown` answers, and it has a
different owner:

| question | answered by | owner |
|---|---|---|
| how should this field be shown? | `shown`, in the catalogue | the model |
| do I have a control for that? | `DRAWS` | the page |

A second page — a different client, a terminal form — would answer the second
question differently while reading the same `shown`. So the fact belongs on the
page, and publishing it from `capabilities.py` would be the model claiming to
know what its readers can draw.

**This is the whole difference from `CARD_KINDS`.** There, the correct twelve
were already computed and shipped in the same response as a hand-written six.
Here there is nothing in the model to read: the model has never said which
controls exist, and should not.


## 3. Every duplicate, and which have drifted

Ten enumerations of the eight words, found by scanning `src/` and `tests/`:

| file | line | values | state |
|---|---|---|---|
| `capabilities.py` | the `shown` ladder | 8 | **the source** — computes them |
| `author.html` | dispatcher if-chain | 7 explicit + fallthrough | the page's real capability |
| `author.html` | `const DRAWS` | 8 | **restates the dispatcher** |
| `tests/test_value_renderer.py` | 439 | 8 | complete |
| `tests/test_author_rendering.py` | 662 | 8 | complete |
| `tests/test_metadata_language.py` | 587 | 8 | complete |
| `tests/test_body_renderer.py` | 80 | 8 | complete |
| `tests/test_body_renderer.py` | 389 | 8 | complete |
| `tests/test_body_renderer.py` | 306 | 7 | deliberately omits `given`, with a reason |
| `tests/test_ability_metadata.py` | 457 | 5 | deliberately the five a plain parameter may have |
| **`tests/test_card_composition.py`** | **453** | **7** | **drifted — missing `named`** |
| **`tests/test_human_metadata.py`** | **315** | **7** | **drifted — missing `named`** |

### The two that drifted, and why nothing noticed

Both were left behind when `named` was added, and both still pass.

`test_card_composition.py:453` asserts every field of the **card** shape is
drawable. Measured, the card shape uses four of the eight — `advanced`, `body`,
`form`, `given` — so a list missing `named` covers it. It would fail the day
the card shape gained a `named` field, and not before.

`test_human_metadata.py:315` uses the list to *exclude* routing words from a
check that the renderer never names an effect. `named` is not the id of any
effect, condition or target, so omitting it changes nothing — today.

Neither is held to the source by anything. That is the finding: **the copies
are not wrong because they are copies; they are wrong because nothing checks
them, and two have already proved it.**


## 4. Measurements

Against the full catalogue and the live page.

**Nothing is undrawable.** Of 168 published shapes — effects, conditions,
targets, cards, abilities, statics, structures — **zero** fail `drawable`. All
seven control nodes pass. `DRAWS` is exactly the set of `shown` values in use:

```
shown values in use : advanced, body, form, given, group, named, nested, spelling
DRAWS               : advanced, body, form, given, group, named, nested, spelling
```

**The guard filters nothing.** Its only consumer, with and without it:

```
with the filter : 70 offered
without         : 70 offered
difference      : []
```

**Options A and B are indistinguishable.** The page rendered with `drawable`
forced to `true`, against the page as it stands, on a card holding both an `if`
and a `promise`:

```
Option B — keep DRAWS     {controls: 65, stepChooser: 70, html: 129426}
Option A — drop the guard {controls: 65, stepChooser: 70, html: 129426}
identical: True
```

No page errors, no missing control, no unexpected control, either way.

**The guard is also partial.** Probed with a synthetic node carrying a `shown`
the page has no branch for:

```
the guard would hide the node from the step chooser : True
but the dispatcher would still draw the field       : True, as <input>
```

`drawable` protects the step chooser and nothing else. The same undrawable
field inside an effect, or inside a nested node, is drawn by the dispatcher's
fallthrough as a plain box — a structure asked for in a text box, which is the
exact failure the concept exists to prevent.

**Cards are unaffected either way**: 1045 readable, 352 with rules, 352
checker-clean, unchanged.


## 5. Classification — **D, mixed**, in three parts

**Not A (duplicate publication).** `DRAWS` does not restate a model fact. The
model does not know which controls a page has, and should not be made to.

**Not B (missing declaration) either.** Nothing needs a new model field. A
`shown` value the page cannot draw is a page problem, and publishing "this can
be drawn" would put the page's answer in the model's mouth — the same mistake
in the opposite direction.

**Partly C (the page uses what it has incorrectly).** `DRAWS` restates the
page's own dispatcher, one screenful away from it, and the two are kept in step
by hand. Today they agree. Nothing makes them.

**And mostly a testing gap, which is the largest part.** Eight of the ten
enumerations live in tests, and two of those have drifted with no failure. The
words are checked in ten places and guaranteed in none.

So the honest shape of it: **`DRAWS` is in the right file, saying the right
thing, unchecked — and the drift has already happened in the copies of it, not
in it.**


## 6. Safety

Confirmed for anything this analysis proposes:

| | required? |
|---|---|
| card JSON changes | **no** |
| runtime changes | **no** — nothing here is on a game path |
| gameplay changes | **no** |
| content changes | **no** |
| new hardcoded lists | **no** — the proposal removes copies, adds none |
| new renderer branches | **no** — none proposed |
| card counts | unchanged: 1045 / 352 / 352 |


## 7. Recommended next stage

**Not a removal.** Deleting `DRAWS` would delete a true statement and leave the
guard's one job to nothing. Deriving it — having the page scrape its own source
for `f.shown === "…"` branches — would be worse than the list it replaced.

The stage worth doing is smaller and different:

1. **One assertion, in one place**: every `shown` the catalogue publishes is
   one the page's dispatcher has a branch for. That is the claim `DRAWS` makes
   and nothing verifies, and it is checkable from the two sides that exist —
   the catalogue and the page's source.
2. **Delete the drifted copies**, or point them at the one assertion.
   `test_card_composition.py:453` and `test_human_metadata.py:315` both assert
   something about the eight words and both have fallen behind; neither needs
   its own list.
3. **Leave the deliberate partial lists alone.** `test_body_renderer.py:306`
   omits `given` for a stated reason and `test_ability_metadata.py:457` lists
   the five a plain parameter may have. Those are claims, not copies.

Optionally, and separately: `drawable` guards the step chooser only, while the
dispatcher's fallthrough draws an unknown `shown` as a box anywhere else.
Whether that fallthrough should say so instead of drawing a box is a real
question and a different one — it is about what the page does when the model
outgrows it, and it should not be bundled with tidying the copies.

**Priority: low.** Nothing is broken for any card today, and the measurement
says so in three ways — nothing undrawable, nothing filtered, both options
identical. This is drift insurance, not a fix.


## 8. Files that would theoretically change

Named, not touched.

| file | what it would carry |
|---|---|
| `tests/test_body_renderer.py` | the one assertion, beside the other tests about the routing |
| `tests/test_card_composition.py` | its own list removed |
| `tests/test_human_metadata.py` | its own list removed |

Unchanged: `author.html`, `capabilities.py`, `author.py`, `runtime/`,
`content/`, and every card file.
