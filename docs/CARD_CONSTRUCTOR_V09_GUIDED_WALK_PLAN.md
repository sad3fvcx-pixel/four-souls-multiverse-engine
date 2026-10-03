# The guided walk — what it refuses, and why

Analysis only. Nothing in `src/`, `tests/` or `content/` was changed, nothing
was committed. Measured at `17c0214`.

Runtime execution, the event model, event fields, promise logic, step-local
bindings and card content were not touched, and nothing here proposes touching
them.

**Classification: a routing gap, with one decision inside it.** Every control
the walk would need already exists and is already reached by the code the walk
itself calls. But the gate is two checks rather than one, they do not agree
with each other, and widening the one everybody knows about would make the walk
offer an action it then never finishes. That second half is a decision about
what `asked` means, not a new concept.


## 1. How the walk works

Three functions decide everything, and all three read published metadata.

```
chooseAction  → actionsIn(node)   → finishable(e)   → putable(f)
                                                       ↑
ask(n)        → questions()       → putable(f)  AND  f.asked === "first"
                     ↓
                 oneByOne([one.f], …)      ← the expert editor's own dispatcher
```

`ask()` renders with **`oneByOne`** — the same function `fieldsHtml` calls for
the expert editor. `fieldsHtml` adds nothing but grouping: it splits fields by
`asked` and calls `oneByOne` three times. So the walk and the editor draw
through one renderer, and the walk is not a reduced one.

Nested structure is not foreign to the walk either. `armsOf` finds every list
of steps a node holds and the walk descends into it as a new list — that is how
a branch's `then`, a `may`'s `effects` and a mode's steps are already filled in.
One measured qualification: `heldBy` filters to lists the card *already
writes*, so an arm exists only for structure that is there. The walk follows
structure; it does not create the first entry of one.


## 2. Every `shown`, measured

Across all 417 published parameters — effects, conditions, targets, cards,
abilities, statics and structures.

| `shown` | parameters | renderer exists | `putable` allows | asked by the walk | cards affected |
|---|---|---|---|---|---|
| `form` | 278 | yes | 276 | **44** | — |
| `given` | 59 | yes (by falling through) | 0 | 0 | none: the engine answers it |
| `group` | 32 | yes | 0 | 0 | none: aiming is asked apart |
| `body` | 20 | yes | 0 | 0 | **2** (`watch_for`) |
| `spelling` | 14 | yes | 0 | 0 | none: asked under the other name |
| `nested` | 9 | yes | 0 | 0 | none: no required one |
| `advanced` | 4 | yes | 0 | 0 | none: no required one |
| `named` | 1 | yes | 0 | 0 | **4** (`promise`) |

**Every one of the eight is drawn.** `DRAWS` lists all eight, and the
dispatcher has an explicit branch for seven of them (`given` is handled by
returning nothing, deliberately). `putable` allows exactly one.

The 44 is the other half of the story: of 278 `form` parameters, the walk asks
44, because `questions()` also requires `asked === "first"`.


## 3. The exact blocking point

Two gates, and the measurement was worth doing because they are not the same
gate.

```js
function putable(f) {
  return f.asked !== "never" && f.shown === "form";
}

function finishable(e) {
  return e.fields.every(f => !f.required || putable(f));
}

// in questions():
(shape.fields || []).filter(f => f.asked === "first" && putable(f))
```

`finishable` asks only whether a required field is *putable*. `questions` asks
whether it is putable **and** `first`. Today the two agree, by accident: no
parameter anywhere is required, `form`, and not `first` — measured, the set is
empty. So the disagreement has never shown.

The two effects the walk refuses, and the field that stops each:

| effect | field | `shown` | `asked` |
|---|---|---|---|
| `promise` | `changes` | `named` | **`deeper`** |
| `watch_for` | `effects` | `body` | **`deeper`** |

Both are `deeper`. That is what makes this more than a one-line change:
**widening `putable` alone makes `finishable` true and `questions` still skip
the field.** Measured, with `putable` widened to `DRAWS` in the live page:

```
refused with the gate as it is : ['promise', 'watch_for']
refused with the gate widened  : []

watch_for   walk would ask : [['event', 'form']]
            required       : [['event','first','form'], ['effects','deeper','body']]
            required but never asked: [['effects', 'deeper', 'body']]
promise     walk would ask : [['event', 'form']]
            required but never asked: [['changes', 'deeper', 'named']]
```

The walk would offer both actions and finish neither — producing exactly the
card `finishable`'s own docstring exists to prevent: *"putting a question with
no box to answer it in, and then saving a card the checker refuses."*

### Which of the four possible causes it is

| candidate cause | measured |
|---|---|
| the model cannot describe them | **no** — `shown`, `asked`, `each_shaped_like` and `a_list_of` all published |
| the renderer cannot draw them | **no** — see below |
| the walk refuses them | **yes** — `putable`, and `questions`' second filter |
| validation rejects them | **no** — all six affected cards check clean |

The renderer was tested rather than assumed. Calling `oneByOne` exactly as
`ask()` calls it, with the two refused fields:

```
promise.changes     drew   254 chars  empty=False  has a control=True
watch_for.effects   drew   209 chars  empty=False  has a control=True
```

**The walk's own renderer already draws both.** Nothing is missing downstream
of the gate.


## 4. Affected shipped cards

Derived from the catalogue rather than from the two known names: every effect
the walk refuses, then every card using one.

| card | blocked parameter | published shape | `shown` | why the walk refuses |
|---|---|---|---|---|
| `treasure_deck-active_items-base_game-compost` | `promise.changes` | `A_MAPPING`, `each_shaped_like: change` | `named` | not `form`, and `asked: deeper` |
| `treasure_deck-active_items-base_game-mom_s_bra` | `promise.changes` | same | `named` | same |
| `treasure_deck-active_items-base_game-two_of_clubs` | `promise.changes` | same | `named` | same |
| `monster_deck-bosses-alt_art-polycephalus` | `promise.changes` | same | `named` | same |
| `treasure_deck-active_items-base_game-crystal_ball` | `watch_for.effects` | `A_LIST`, `a_list_of: step` | `body` | same |
| `treasure_deck-active_items-base_game-host_hat` | `watch_for.effects` | same | `body` | same |

**Six cards.** Every one of them reads, means the same, rewrites stably and
passes the checker — measured. The expert editor edits all six. Only the walk
cannot make one.

No other card is affected, and no effect other than these two is refused.


## 5. What is published and ignored

**The information is all there and one function looks at a sixth of it.**
`shown` is published for every parameter with all eight values; `putable`
compares it against one string.

Three places enumerate the eight, and they agree today:

| where | what it is |
|---|---|
| `capabilities.py`, the `shown` ladder | computes it — the source |
| `author.html`, `const DRAWS` | a hand-written copy of the same eight |
| `author.html`, the dispatcher's `if` chain | a branch per value |

`DRAWS` and the computed set are equal, measured. That is a second copy of a
published fact, of the kind the `CARD_KINDS` stage removed — worth naming, but
it is not the blocker and should not be bundled with it.

Hardcoded single values inside the walk's own three functions:

```
putable     f.asked !== "never"
putable     f.shown === "form"        ← the gate
armsOf      f.a_list_of === "step"    ← only a list of steps is an arm
```

`armsOf`'s `"step"` is correct as it stands: an arm is a place the walk
*continues into*, and only a list of things that happen is that. A list of
conditions is not somewhere to walk.

There is no field anywhere saying "this structure can be asked interactively",
and none is needed to answer the question — `shown` plus the renderer already
answer it.


## 6. The minimal model

**Option A — routing — with one decision inside it.**

The routing half is small and needs no new concept:

- `putable` asks whether the page has a control for the field, which is what
  `DRAWS` already says, rather than whether the field is a box.
- `finishable` and `questions` are made to agree, so an action is offered only
  if every required field is one the walk will actually ask.

The decision is the second half, and it is about `asked`:

> `asked` is documented as *"the one thing here that is not a fact about the
> engine. It is a fact about people writing cards"* — `first`, `more`,
> `deeper`, `never`. In a form, `deeper` means "behind Advanced". **A walk has
> no Advanced.** It asks one question after another until the action is
> finished.

So for the walk, `deeper` on a *required* field cannot mean "do not ask": that
is the same as refusing the action. Two coherent readings, and the choice is
the user's:

1. **The walk asks every required field it has a control for, whatever `asked`
   says**, and `asked` keeps meaning "how prominent in a form". Measured
   consequence: exactly `promise` and `watch_for` change, because no other
   parameter anywhere is required and not `first`.
2. **`asked` is respected, and an effect with a required non-`first` field
   stays out of the walk.** Then nothing changes and the six cards stay
   expert-only — which is today's behaviour, now with a stated reason.

Reading 1 is the smaller change and the one the measurement supports: the set
it affects is exactly the set that is broken.

**Option B is not required.** No new declaration would say anything the model
does not already say. A `guided editor capability` field would be a third copy
of what `shown` and `DRAWS` between them already know, and it would have to be
kept in step with the renderer by hand.

### One thing routing alone does not settle

`heldBy` filters to lists the card already writes, so a freshly-made
`watch_for` has no arm and `armsOf` returns `[]` — measured. Filling `effects`
through the walk therefore needs either the `body` control drawn in the
question itself (which draws, measured, and carries its own "add" button), or
an arm offered for an empty required list. That is a design choice for the
implementation stage, not a gap in the model, and it is the one place where
"just route it" is not the whole answer.


## 7. Safety

Verified for anything this analysis proposes:

| | required? | why not |
|---|---|---|
| card content | **no** | the walk makes new cards; no file is read differently |
| card JSON | **no** | the walk writes through the same builder as the editor |
| runtime behaviour | **no** | nothing here is imported by `rules/`, `state/`, `stack/` or `runtime/` |
| JSON migration | **no** | nothing stored changes shape |
| event model, event fields | **no** | untouched, and out of scope by instruction |
| step-local bindings | **no** | `armsOf` and the binding walk are not changed |
| promise logic | **no** | `state/promises.py` untouched |

The whole surface is `author.html` and, if the second copy is removed at the
same time, one published field.


## 8. Recommended next stage

**Stage — let the walk ask what it can already draw.** Scoped as:

1. `putable` asks whether a control exists, read from the same place the
   dispatcher routes by, rather than comparing against `"form"`.
2. `finishable` and `questions` made to agree, so no action is offered whose
   required field the walk will not ask.
3. A decision, taken first and stated: whether a required field is asked
   regardless of `asked` (reading 1 above) — measured to affect exactly
   `promise` and `watch_for`.
4. How an empty required `body` gets its first entry — the `heldBy` finding in
   §6.

It should **not** be merged with removing the `DRAWS` copy. That is the same
kind of second-copy removal as `CARD_KINDS` and deserves its own measurement;
bundling it would make one stage answer two unrelated questions.

Expected effect: six shipped cards become makeable through the walk, and the
number of effects the walk refuses goes from two to nought.


## 9. Files that would theoretically change

Named, not touched.

| file | what it would carry |
|---|---|
| `src/fsme/lab/desk/static/author.html` | `putable`, `finishable`, `questions`; possibly how an empty required body is offered |
| `tests/test_constructor_walk.py` | that the walk offers every effect and finishes each |
| `tests/test_body_renderer.py` | the walk's gate reads the same routing the editor draws by |

Unchanged: `capabilities.py`, `author.py`, `runtime/`, `content/vocabulary.py`,
`state/promises.py`, `effects/`, `rules/`, and every card file.
