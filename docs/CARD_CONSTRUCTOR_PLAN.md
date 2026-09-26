# Card Constructor — analysis and plan for v0.6.0

The editor after v0.5.2 asks good questions in a sensible order. It still asks
them about a *card*: its name, its kind, the rules it holds, what each rule
reacts to. Somebody who plays Four Souls and has never seen the source starts
somewhere else — from **what the card should do** — and has to work backwards
to reach it.

This is a plan for meeting them there. No new pipeline, no second card model,
no runtime of its own: a different way in to the same metadata, ending in the
same `CardDefinition`.

Everything below was measured against the engine as it stands at `dbfe8b3`.

---

## 1. What already exists and can be reused

The renderer is already generic enough that the constructor needs almost none
of its own drawing code. Every one of these is used unchanged:

| Primitive | What it already does | Constructor uses it for |
|---|---|---|
| `fieldsHtml` / `oneByOne` | draws any shape's fields, folded by `asked` | the questions an action asks |
| `folded` | "More options" / "Advanced" | keeping an action to one or two questions |
| `aimHtml` | "Who or what does this happen to?", filtered by `hits` | *the* constructor question |
| `valueHtml` | one control per `role`, glossed by `values_mean` | every answer |
| `bodyHtml` / `nodeHtml` | a list of nodes of a declared kind | several actions on one card |
| `becauseOf` / `moot` | why a question is not being asked | unchanged |
| `at` / `setField` / `setPick` | writing answers into the card being built | unchanged |
| `build_card` (`author.py`) | the card shape → a `CardDefinition` | **unchanged, and this is the point** |
| `check_card` | the loader's own validator | unchanged |
| `Workbench.show_card` | "try it in a game" | unchanged |

**The constructor is a different first screen, not a different renderer.**

## 2. What the metadata already says

Measured across all 63 effects:

| | |
|---|---|
| effects offered as actions | 63 |
| asking **0 or 1** question up front | 63 — *all of them* |
| that act on something (so the aim question applies) | 61 |
| of those, kind-restricted so the aim list is already filtered | 25 |

Every effect already carries what an action needs: a sentence saying what it
does (`about`), the one question it is mostly about (`asked == "first"`, which
is its `primary` parameter), a human question for it (`asks`), glossed answers
(`values_mean`), and what it may be aimed at (`hits`).

**The catalogue of actions is the effect catalogue.** No second list.

### The load-bearing measurement

A card built from nothing but *(card kind + chosen action + aim + the questions
that action asks)*, then put through the real validator and played in a real
game:

> **55 of 63 effects produce a valid, playable card.**

That is the whole feasibility argument. The constructor needs no new
capability; it needs a smaller first question.

### The eight that do not fit the minimal flow

None of them is new, and none is caused by the constructor. All three groups
are gaps this project has already written down.

| Effects | Why | Where it is already recorded |
|---|---|---|
| `cancel_event`, `modify_event`, `prevent_damage` | need an open event in context — a replacement ability | `CORRECTNESS_AUDIT_0_5_0.md`, gap **G1** |
| `cancel_stack`, `copy_effect`, `require_attack` | act on something narrower than the two kinds the vocabulary has | same, gap **G2** |
| `promise`, `watch_for` | require a nested body, not a value | `AUTHOR_UI_UX_AUDIT.md` |

The constructor should not pretend otherwise: it offers them and says what else
they need, the way the editor already says a thing it cannot build yet.

## 3. What is missing

Exactly one fact, and it is a real engine fact that is simply unpublished.

### The card kind does not say how a card is used

A constructor that asks "what should this card do?" must supply the trigger
itself — asking "when does this happen?" first is the question it exists to
avoid. The answer is in the rules and nowhere else:

- `rules/loot.py` emits `ON_PLAY` when a loot card is played.
- `rules/activation.py` refuses to activate an item that has no `ON_ACTIVATE`
  ability — so a treasure's normal way of doing something *is* `on_activate`.
- `rules/combat.py` and `rules/shop.py` emit `ON_ENTER` when a card comes into
  play.

So "how a card of this kind normally does something" is derivable, but it is
spread across three rules modules and published nowhere. Reading it is what
lets the constructor put an action on a card without asking about triggers.

**This is the one metadata addition proposed**, and it follows the rule every
other addition in this project has followed: declared beside the code that
enforces it, published through the catalogue, read by the page.

### Not proposed

- **A category tree for actions.** The effect descriptions already read as
  actions ("Deal damage to a player or monster.", "Add coins to a player."),
  and `common` already orders them. A second grouping would be a second list to
  keep in step.
- **Any per-effect form.** Forbidden, and unnecessary: 63 of 63 effects ask at
  most one question up front.
- **A constructor card model.** The state is the same `{fields, groups}` the
  editor already writes, so a card can be started in one mode and finished in
  the other.

## 4. Where metadata is extended

One field, on the card kind rather than on any effect:

```
CardType  →  how a card of this kind does something
             loot          → on_play
             treasure      → on_activate
             starting_item → on_activate
             monster, room, character, curse → (unset)
```

Declared beside the rules that emit those events, published as part of the
`kinds` section the page already reads. Left unset where the engine has no
single answer — silence is not a claim, and the constructor asks in that case.

Nothing else. `asks`, `values_mean`, `asked`, `hits`, `primary`, `needs_target`
and `common` are all already there and all already used.

## 5. First iteration — the smallest thing that works

A prototype, not a visual editor. Six steps, each of which already has its
machinery:

1. **Choose a kind** — the existing kind screen.
2. **"What should this card do?"** — the effect catalogue, common first, each
   shown by its own sentence. New screen, ~30 lines, no effect named.
3. **Add the action** — write an effect node into
   `state.card.fields.abilities[0].fields.effects`, with the trigger taken from
   the kind. Reuses `addNode`/`setNode`.
4. **Answer its questions** — `aimHtml` for the aim, `fieldsHtml` for the rest.
   Unchanged.
5. **See the card** — the existing live check and card face.
6. **Try it in a game** — unchanged.

Plus a way between the two modes, because they are two views of one card:
"Show me everything" from the constructor, "Simpler view" from the editor.

### What it will not do in the first iteration

Drag and drop. Conditions and costs (they are behind "More options" and stay
there). Statics. Several abilities. Anything in the eight effects above beyond
saying what they need.

## 6. Files this touches

| File | Change |
|---|---|
| `cards/types.py` or `rules/` | declare how each kind of card does something |
| `runtime/vocabulary.py` | publish it |
| `lab/desk/capabilities.py` | carry it in the `kinds` section |
| `lab/desk/static/author.html` | the action screen and the mode switch |

**Not touched:** `build_card`, the validator, the runtime, the card schema, the
content, `web/` (watch mode), `.github/`.

## 7. The audit that follows the prototype

Stated now so it cannot be graded generously later:

1. **No new pipeline** — a card made in the constructor and the same card made
   in the editor produce byte-identical JSON. Testable, and the test is the
   proof of this whole plan.
2. **No duplicated logic** — the constructor adds no function that draws a
   field, writes a card or checks one.
3. **No effect named** — the existing test that walks every published name and
   refuses to find it in the script must still pass.
4. **Existing cards unchanged** — 1045 definitions load; 1000 recorded games
   replay identically.
5. **The gate** — `pytest`, `ruff check .`, `mypy src --strict`,
   `git diff --check`, and a browser smoke test of the six steps.

## 8. Risks

- **The mode switch is where a second model would creep in.** If the two modes
  ever need different state, the constructor has become a second editor. The
  test in §7.1 is what catches it, and it should be written first.
- **"How a card of this kind does something" is a rule of the game, not of the
  engine.** It is derived from what the rules emit, and it is declared unset
  wherever the engine does not settle it — a guess there would put a trigger on
  a card that never fires.
- **The eight effects will look like bugs to an author.** They are honest
  limits with recorded causes; the constructor must say which, not hide them.
