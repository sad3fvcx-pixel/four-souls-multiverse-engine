# Capability coverage: the authoring frontier after the metadata renderer

An architecture review, measured rather than assumed. Every claim below was
checked by running the real path — build a card the way the form builds it,
validate it the way the loader validates it, and play it in a real game — not
by reading either side and inferring the other.

Measured at `21c8581`, against 1014 shipped cards, 63 effects, 41 conditions,
46 targets, 66 triggers and 7 control nodes.

## The headline

**The form can reproduce 101 of the 329 shipped cards that carry rules — 31%.**

Effects, conditions and targets are essentially complete. What is missing is
one layer up: the *ability* that holds them, and the control nodes that shape
them. Every one of the top five blockers lives in `Ability` or in
`CONTROL_KEYS`, and none of them is a renderer problem — the renderer has
nothing to render from, because `capabilities.catalogue()` never hands the page
the node shapes the engine already builds.

| What stops the other 228 | cards | share of carded cards |
| --- | ---: | ---: |
| `ability.scope` | 170 | 51.7% |
| `ability.conditions` | 76 | 23.1% |
| a dynamic head (`from`, `count`, …) | 46 | 14.0% |
| more than one ability | 38 | 11.6% |
| a static | 29 | 8.8% |
| `may` | 26 | 7.9% |
| `ability.replacement` | 23 | 7.0% |
| `choose` | 21 | 6.4% |
| statics only, no ability | 15 | 4.6% |
| `ability.cost` | 12 | 3.6% |
| `for_each`, `store`, `ability.zone` | 1 each | 0.3% |

---

# 1. Fully supported capabilities

Exists in the engine, has metadata, can be built in the form, survives
validation, and executes. Verified by building and playing one card per item.

## Effects — 60 of 63

Every effect the catalogue offers can be built from the form and played, with
three exceptions covered in §2. Examples verified end to end:

- **Simple values** — `gain_coins` (amount), `heal` (amount, or `full`),
  `draw_loot`, `lose_coins`, `roll_dice`.
- **Domains** — `add_modifier` (`stat` from 9, `duration` from 2),
  `move_cards` (`deck` from 4, `position` from 3), `take_card`
  (`to` from 2, `shuffle` from 5).
- **Naming a player** — `give_treasure.to`, `take_card.player`,
  `deal_damage.dealt_by`, `require_attack.who`: a target picker over the 16
  player-yielding targets, written as `{"player_of": "<bound name>"}`.
- **Two concepts at once** — `require_attack` writes the player who owes the
  attack *and* the monster owed one, from two separate controls.
- **Structures** — `promise.changes`, `watch_for.effects`: a parsed structure
  editor; a card missing one is now refused rather than saved as ready.
- **Lists** — `target_stack_item.kinds` / `.triggers` as multiple selections
  producing arrays.

## Conditions — 41 of 41

All forty-one build from the branch editor, validate and evaluate. Verified by
constructing `{"if": [<condition>], "then": [gain_coins]}` for each.
Examples: `player_has_coins` (operator + value), `dice_greater`, `monster_hp`,
`card_in_zone`, `nth_time_this_turn`, `values_equal`, `last_effect_did`.

Not offered: `and`, `or`, `not` — see §2.

## Targets — 46 of 46

Every target is offered, aimable, and resolves. Each keeps its own parameters,
rendered by the same generic code as an effect's.

## Control structures — 1 of 7

`if` only, through "＋ depending on something". The other six are in §2.

## Card abilities — 3 of 10 fields

The builder writes `trigger`, `effects` and `targets`. The remaining seven
fields of `Ability` are in §2.

## Static abilities — 0 of 7

Not reachable at all. See §2.

---

# 2. Engine capabilities not currently authorable

Each verified by feeding the builder a description that asks for it and
observing what came out.

## Control flow

| Feature | Where it lives | Why the form cannot make it | Intentional? |
| --- | --- | --- | --- |
| `may` | `interpreter.py::_expand_may`, `CONTROL_KEYS["may"]` | `author.py::_effects` handles exactly two node shapes: `{"branch": …}` → `if`, and `{"id": …}` → an effect. Anything else is dropped and the ability comes out empty. | Intentional for now — the MVP shipped one control node. The drop is silent, which is not. |
| `choose` | `_expand_choose`; modes each carry `description` + `effects` | Same; and a mode list is a second level of nesting the editor has no shape for. | Intentional |
| `for_each` | `_expand_for_each`; takes a target in `of` | Same. Would need a target picker plus a nested body. | Intentional |
| `repeat` | `_expand_repeat` | Same; would need a number plus a nested body. | Intentional |
| `sequence` | dispatch in `interpreter.py` | Same. Rarely needed — the effect list is already a sequence. | Intentional |
| `stop` | dispatch in `interpreter.py` | Same. A leaf node, the cheapest of the seven to offer. | Accidental — nothing about it is hard |

None of the six is refused; all six are **silently discarded**. A future editor
that emits them will work, because the validator and interpreter already accept
them — the gap is entirely in `author.py` and the page.

## Card structure

| Feature | Where it lives | Why | Intentional? |
| --- | --- | --- | --- |
| More than one ability | `build_card` sets `card["abilities"] = [ability]` from a single `ability` key | The form models one card as one ability. 38 shipped cards need two or more. | Intentional, and now the second-largest structural blocker |
| Statics | `cards/definition.py::Static`; `rules/statics.py` | `build_card` never writes `statics`. 29 cards have one; 15 have *only* statics and no ability at all, so they cannot be made in any form. | Intentional |
| `ability.scope` | `runtime.py::ability_scope`, `ABILITY_SCOPES = ("self","controller","any")` | The form writes no scope, so the engine defaults: `self` for the 14 self-scoped triggers, **`any` for everything else**. A card built as "when you take damage, gain 1¢" is written with `trigger: damage_dealt` and fires on damage to *anyone at the table*. It validates clean and its behaviour contradicts its own printed text. | Accidental. This is the single most valuable missing control and the most dangerous silence in the tool. |
| `ability.conditions` | `Ability.conditions`, evaluated before the effects run | The form offers branch conditions inside the effect list but no condition on the ability itself. 76 cards need one. | Accidental — the metadata for conditions already exists |
| `ability.replacement` | `Ability.replacement`; guards in `replacement.py` | Without it, `cancel_event`, `modify_event` and `prevent_damage` are the three effects that can be built, validated, and can never run: they refuse at play time with "may only be used by a replacement ability". | Accidental |
| `ability.cost` | `Ability.cost` | No control. 12 cards need one. | Intentional |
| `ability.optional` / `zone` / `description` | `Ability` | No control; 0 / 1 / cosmetic use in shipped content. | Intentional |
| Nested ability structures | — | Follows from the control-node gap. | Intentional |

## Runtime concepts

| Feature | Where it lives | Why | Intentional? |
| --- | --- | --- | --- |
| Dynamic heads — `from`, `count`, `from_event`, `last_result` | `effect_executor.py::_resolve_params`; `DYNAMIC_HEADS` in the validator | **The builder already passes them through** — `_written_fields` keeps a mapping unchanged, and a card with `{"amount": {"from": "dice"}}` builds and validates. What is missing is only a *control*: a number box writes a number. 46 cards need one. | Accidental, and cheaper than it looks |
| `player_of` | same | Supported, and the only head with a control: the `whom` picker writes it. | — |
| `store` | `_MODIFIER_KEYS` includes `store`; `roll_dice` and `reroll` store under `dice` | No control writes `store`, and `values_equal.of` asks for the name of a stored value in a plain text box. Only 1 shipped card uses it. | Intentional |
| `previous_target` / `previous_result` | `target_resolver.py` | **Now supported** — offered under "what an earlier step chose". | — |
| `and` / `or` / `not` | `condition_evaluator.py`; `BOOLEAN_CONDITIONS` | They have no `ConditionShape`, so they never reach the catalogue and the branch editor cannot offer them. A branch can hold one condition, never a chain. | Accidental — the absence is a missing shape, not a decision |

---

# 3. Authoring limitations

Places where the path works and the experience does not. The test applied was:
*could a new expansion author understand what is being asked without reading
engine code?*

### An effect's target kind is enforced and never declared

**33 of the 61 targeting effects refuse at least one aim the form offers**, and
the form says nothing about which. `gain_coins` aimed at a treasure builds,
validates, and dies at play time with "expects player targets"; `cancel_stack`
accepts 4 of the 15 aims tried; `deactivate`, `recharge`, `make_eternal`,
`copy_card` all want cards. The engine knows — every one of those messages is a
handler guard — and the metadata does not carry it, so the picker offers all 42
targets for every effect. This is the same shape of problem the project has
fixed five times before: *a fact enforced in a handler and declared nowhere.*

### `scope` is a hidden runtime assumption with teeth

Covered above as a missing capability; it is also an experience failure. There
is no way for an author to discover that omitting a control they have never
seen makes their card react to the whole table.

### A structure editor with no guidance

`promise.changes` is a JSON box. The valid change keys are
`value`, `delta`, `factor`, `cap`, `floor`, `flip` — enforced in the handler,
absent from the metadata, and not shown anywhere. An author writing
`{"amount": {"plus": 1}}` gets a card that validates and then refuses to play.

### Domains the engine knows and the metadata does not declare

- `card_in_zone.zone` — the handler does `getattr(state, zone)` and answers
  *false* for anything unknown. There are exactly 12 zones. A typo makes a
  condition that is silently never true.
- `place_monster.slot` — the handler reads `unattacked` and treats everything
  else as `free`. A typo silently means `free`.

Both are text boxes today.

### Open vocabularies with no suggestions

`counter`, `tag`, `named`, `key` are genuinely open — an author's own counter
is a legitimate new word — but the loaded content already contains the answer
(`charge`, `egg`, `tear`, `nuke`, `knot`, `gold`, …; tags `guppy`, `passive`).
Nothing offers them.

### Available only by hand-editing JSON

Everything in §2. A set made in the form and a set made in a text editor are
the same format, so all of it is reachable — by opening the file.

---

# A. Current capability matrix

| Capability | Engine | Metadata | UI | Status |
| --- | :---: | :---: | :---: | --- |
| Effects (60) | ✅ | ✅ | ✅ | Fully supported |
| `cancel_event`, `modify_event`, `prevent_damage` | ✅ | ✅ | ⚠️ | Buildable, never runnable — needs `replacement` |
| Conditions (41) | ✅ | ✅ | ✅ | Fully supported |
| `and` / `or` / `not` | ✅ | ❌ | ❌ | No shape, so never offered |
| Targets (46) | ✅ | ✅ | ✅ | Fully supported |
| Target parameters | ✅ | ✅ | ✅ | Rendered recursively |
| Effect → target kind | ✅ | ❌ | ❌ | Enforced at play time only |
| Triggers (66) | ✅ | ✅ | ✅ | Fully supported |
| Control node `if` | ✅ | ✅ | ✅ | Fully supported |
| `may`, `choose`, `for_each`, `repeat`, `sequence`, `stop` | ✅ | ✅ (node shapes) | ❌ | Silently dropped by the builder |
| One ability per card | ✅ | ⚠️ | ✅ | Supported |
| Several abilities | ✅ | ⚠️ | ❌ | Not authorable |
| `ability.scope` | ✅ | ⚠️ (values only) | ❌ | Not authorable; silent wrong default |
| `ability.conditions` | ✅ | ⚠️ | ❌ | Not authorable |
| `ability.replacement` / `cost` / `optional` / `zone` | ✅ | ⚠️ | ❌ | Not authorable |
| Statics | ✅ | ⚠️ | ❌ | Not authorable |
| Dynamic heads `from` / `count` / `from_event` / `last_result` | ✅ | ❌ | ❌ | Builder passes them; no control writes one |
| `player_of` | ✅ | ✅ | ✅ | Fully supported |
| `store` | ✅ | ❌ | ❌ | Not authorable |
| `previous_target` / `previous_result` / `group` | ✅ | ✅ | ✅ | Fully supported |

⚠️ in the Metadata column means the engine builds a shape that
`capabilities.catalogue()` never passes to the page.

---

## Target system map

| Engine target | Hands back | Where the form offers it | Its own questions | Available |
| --- | --- | --- | --- | :---: |
| `current_monster` | cards | first list | leave out the monster being fought | yes |
| `target_monster` | cards | first list | chooser, count, min, max, prompt, exclude_attacked | yes |
| `random_monster` | cards | everything else | leave out the monster being fought | yes |
| `target_player` | players | first list | chooser, count, min, max, prompt, exclude_controller, most | yes |
| `target_player_or_monster` | mixed | everything else | chooser, count, min, max, prompt, two excludes | yes |
| `target_treasure` | cards | first list | of, chooser, count, min, max, prompt, owner, tag, counter, 2 excludes | yes |
| `target_shop_item` | cards | everything else | chooser, count, min, max, prompt | yes |
| `target_stack_item` | cards | everything else | chooser, count, min, max, prompt, kinds (8), triggers (66) | yes |
| `target_loot` | cards | first list | of, chooser, count, min, max, prompt | yes |
| `target_soul` | cards | everything else | of, chooser, count, min, max, prompt | yes |
| `target_deck_card` | cards | everything else | deck, pile, from_top, card_type, exclude_type, tag, named, chooser, count, min, max, prompt | yes |
| `group` | passthrough | what an earlier step chose | of (a group picker) | yes |
| `previous_target` | passthrough | what an earlier step chose | — | yes |
| `previous_result` | passthrough | what an earlier step chose | — | yes |

All fourteen are available. The remaining 32 targets are too.

---

## Parameter system map

| Role | Count | Routed to | Control drawn |
| --- | ---: | --- | --- |
| `amount` | 99 | form | number, with `min` from `least` and the effect's default as placeholder |
| | 8 | spelling | not asked — a second name for a question already asked |
| `which` | 43 | form | single selection (39) or multiple selection (4, when the kind is a list) |
| `switch` | 31 | form | checkbox |
| `names` | 32 | form | text |
| | 46 | given | not asked — `as`, written by FSME |
| | 2 | group | a picker over any bound group |
| `whom` | 26 | group | a target picker filtered by what it names |
| | 4 | given | not asked — the engine supplies the card |
| `structure` | 4 | advanced | parsed structure editor |
| `open` | 2 | form | text read as JSON, kept as words when it is not |

Nothing falls through to a generic box by accident. The 32 remaining text
boxes divide into:

- **Correct as text** (21): `prompt` ×11, `label`, `named`, `tag` ×6, plus the
  free-form counter names.
- **Should have a domain** (2): `card_in_zone.zone` (12 known zones),
  `place_monster.slot` (2 known slots).
- **Should be a picker but has nothing to pick from** (1):
  `values_equal.of` names a stored value, and no control writes `store`.

---

## Metadata completeness

Effects, conditions and targets are complete enough for a generic renderer:
every parameter carries `role`, `kind`, `values`, `least`, `required`,
`unless`, `unless_when`, `default`, `describes`, `refers_to` and `written_as`,
and 297 of 297 land in a known place. Labels: effects 7 bare of 61, conditions
0 of 49, targets 0 of 97.

Four things the engine knows and the metadata does not say:

1. **What kind of target an effect accepts.** 33 of 61 targeting effects guard
   on it at play time. Nothing declares it. This is the largest single gap.
2. **Node shapes never reach the page.** `engine_vocabulary()` builds shapes
   for `ability`, `static` and all seven control nodes.
   `capabilities.catalogue()` returns `kinds, triggers, effects, conditions,
   targets` — and nothing else. Every ability-level blocker in §2 traces to
   this one line.
3. **Node-shape parameters are all typed `text`.** `runtime/vocabulary.py`
   builds them as `ParamShape(key, TEXT)` regardless. `optional` and
   `replacement` are booleans, `cost` is a mapping, `conditions`/`targets`/
   `effects` are structures, `amount` on a static is a number. Only `scope`
   carries a domain. Exposing these as they stand would give the renderer bad
   metadata, not thin metadata.
4. **What a `promise` change may say.** `CHANGES` is a six-value domain
   enforced in the handler and declared nowhere.

---

# B. Missing authoring capabilities

| Feature | Technical location | Difficulty | Value to authors |
| --- | --- | --- | --- |
| `ability.scope` | `Ability.scope`, `runtime.py::ABILITY_SCOPES`, node shape in `runtime/vocabulary.py` | **Low** — one selection over three declared values, once the node shape reaches the page | **Highest.** 170 cards (51.7%). Also removes a silent wrong default that makes a card contradict its own text |
| Effect → target kind | 33 handler guards across `effects/builtin/*` | **Medium** — declare beside each guard, the way `values=` already is; filter the aim picker on it | **High.** Turns a play-time crash into a picker that only offers what fits |
| `ability.conditions` | `Ability.conditions`; condition metadata already complete | **Low** — reuse the condition control the branch editor already has | **High.** 76 cards (23.1%) |
| Node shapes in the catalogue | `capabilities.catalogue()`; `runtime/vocabulary.py` node-shape construction | **Medium** — the shapes exist but are typed `text`; they need real kinds first | **High.** Unblocks scope, conditions, replacement, cost, optional, statics, and all six control nodes at once |
| Several abilities per card | `author.py::build_card` | **Medium** — a list where there is now one, and the page's whole editor is currently one ability | 38 cards (11.6%) |
| `ability.replacement` | `Ability.replacement` | **Low** once node shapes land | Makes three currently-dead effects live |
| `may` | `interpreter.py::_expand_may`; `author.py::_effects` | **Medium** — a nested body, like the branch already has | 26 cards (7.9%) |
| `choose` | `_expand_choose` | **High** — a list of modes, each a description plus a body | 21 cards (6.4%) |
| Statics | `Static`; `rules/statics.py` | **Medium** — a second editor, seven fields, no nesting | 29 cards (8.8%), 15 of which have nothing else |
| Dynamic heads | `_resolve_params`; the builder already passes them | **Medium** — a "or work it out" mode on every number control | 46 cards (14.0%) |
| `ability.cost` | `Ability.cost` | Low–Medium | 12 cards (3.6%) |
| `and` / `or` / `not` | `condition_evaluator.py` — no `ConditionShape` | **Medium** — give them shapes, then nest conditions in the branch editor | Unknown; no shipped card uses one, but the absence caps every branch at one test |
| `for_each`, `repeat`, `sequence`, `stop` | `interpreter.py` | Low (`stop`) to Medium | 1 card between them |
| `store` | `_MODIFIER_KEYS` | Medium | 1 card |
| Zone and slot domains | `_card_in_zone`, `place_monster` | **Very low** — two `values=` declarations | Removes two silent-failure typos |
| `promise` change domain | `state/promises.py::CHANGES` | **Very low** | Makes the one structure editor answerable |
| Counter/tag suggestions from content | `ContentLibrary` | Low | Quality of life |

---

# C. Recommended roadmap

## Next small improvements

Metadata the engine already has, declared where it is enforced. No new UI
concepts, no DSL change.

1. `card_in_zone.zone` and `place_monster.slot` domains — two declarations,
   two silent failure modes gone.
2. The `promise` change domain from `CHANGES`.
3. The remaining 7 bare effect labels.
4. Counter and tag suggestions drawn from loaded content.

## Next major milestone — "the ability, not just its effects"

The single coherent piece of work that unblocks half the shipped content, in
dependency order:

1. **Give node shapes real metadata.** `runtime/vocabulary.py` builds
   `ability` and `static` shapes with every field typed `text`; make them
   describe what `Ability` and `Static` actually hold.
2. **Hand node shapes to the page** from `catalogue()`.
3. **Render the ability's own fields** with the renderer that already exists —
   `scope` is a `which`, `optional` and `replacement` are `switch`es,
   `conditions` is the control the branch editor already draws.
4. **Declare what kind of target each effect accepts** and filter the aim
   picker on it.

Steps 1–3 are one architecture, not four features: `scope` (51.7%),
`conditions` (23.1%) and `replacement` (7.0%) all fall out of the same change,
and it needs no new authoring concept — only the metadata layer applied one
level up from where it stops today.

## Future architecture work

Each needs a new shape in the editor, not just new metadata.

- **Nested bodies** — `may`, `for_each`, `repeat`, and then `choose` with its
  list of modes. The branch editor is the precedent; the question is whether
  to generalise it into one "a body of steps goes here" component driven by
  `CONTROL_BODIES`, which the metadata now carries.
- **Several abilities, and statics** — the editor is built around one ability.
  This is the largest UI change on the list and the one most likely to want a
  rethink of the page rather than an addition to it.
- **Values worked out during play** — dynamic heads need every number control
  to offer "a number" or "work it out from…", and the second branch needs its
  own small vocabulary. `store` belongs with it: a value nothing can write is
  a value nothing can read back.
- **Condition chains** — `and`/`or`/`not` need shapes before a branch can hold
  more than one test.
