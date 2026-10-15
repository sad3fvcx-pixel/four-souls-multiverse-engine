# Author UI — UX audit (0.5.0)

An audit of what the card editor asks a person, written after an external test
by somebody who plays Four Souls, does not program, and had never seen the
source. They built a card. They also said the page reads like an aircraft
cockpit, that they worked by trial and error, and that a red message told them
something was wrong without telling them what to change.

This document is analysis only. No production code was changed to write it.

Everything quoted below was captured from the running page in a real browser,
not read off the source. The capture scripts are throwaway; the numbers are
reproducible from `catalogue()` and the page itself.

---

## Executive summary

### What is already good

- **The pipeline is honest.** Every word on the page comes from the engine, so
  the editor cannot offer a card the loader would refuse. That property is
  worth more than any wording fix and nothing here proposes giving it up.
- **The spine works.** Name → kind → what it does → save → try it in a game is
  a real workflow, and the external tester completed it.
- **Several label sets are genuinely good.** Effect descriptions ("Deal damage
  to a player or monster."), target descriptions ("a player somebody picks"),
  and trigger glosses ("a monster is killed") read as English.
- **The page already refuses to lie.** Where it cannot build something it says
  so rather than showing an empty box. That instinct is correct and should be
  extended, not trimmed.

### What blocks the user

Measured on a loot card with **one** effect that hits one player:

| | empty card | one effect |
|---|---|---|
| text inputs | 6 | **22** |
| dropdowns | 1 | **13** |
| JSON textareas | 4 | 4 |
| labels | 10 | **37** |
| words on screen | 260 | **1700** |

1700 words and 39 controls for "deal 1 damage to a player" is the cockpit. But
volume is a symptom. The three causes are:

1. **Fields are ordered alphabetically.** `capabilities._fields` calls
   `sorted(shape.params.items())`. The declared order in every dataclass is
   already the right order for a person — `Ability` declares
   `trigger, conditions, targets, effects, …`; `Static` declares `stat` before
   `amount` — and the sort throws it away. So an ability asks its cost, its
   description and its conditions *before* "what happens", and a static asks
   "by how much" before "which number it changes".
2. **One string is doing three jobs.** `ParamShape.describes` is written as a
   sentence fragment so it can sit inside the engine's own prose. The page then
   uses that same fragment as a form label *and* drops it into composed
   sentences. That is where every broken phrase comes from.
3. **Nothing in the metadata says how important a field is.** `shown` says
   which *control* to draw, never whether a person needs to see it. So the
   engine's plumbing (`id`, `expansion`), the rare (`zone`, `replacement`) and
   the essential (`trigger`, `effects`) all render at the same weight.

### The main problem layer

**Not the renderer, and not the engine — the metadata's description layer.**

The metadata describes machine semantics completely and human semantics barely.
It has exactly one human-facing string per parameter (`describes`) and one
optional gloss map used by exactly one field (`values_mean`, on `trigger`).
Everything the auditor complained about is downstream of that gap.

This is good news architecturally: most of the fix is data, not branches.

---

## The generated-label problem, precisely

The five phrases in the brief are not five bugs. They are two.

### Cause A — a fragment used as a label

`describes` was authored to complete an implicit sentence: *"[this parameter
is] the rules it follows"*. Used as a `<label>`, the relative clause is left
dangling.

| Rendered now | Why it reads wrong |
|---|---|
| `the rules it follows` | relative clause, no subject |
| `which kind of card it is` | indirect question used as a heading |
| `families it belongs to` | relative clause |
| `the roll needed to hit it` | noun phrase, but "it" has no referent on screen |
| `by how much` | fragment; and it appears *before* "which number it changes" |
| `attack` | no `describes` at all — the raw field name leaks through |

The metadata is not wrong. It is being asked for something it never promised.

### Cause B — a fragment composed into a sentence

```js
`Not used while <b>${labelOf(siblings, f.unless)}</b> says what it says.`
```

Substituting an indirect question yields:

> **Not used while which kind of card it is says what it says.**

On an empty loot card this exact sentence appears **four times** — it is the
most repeated text on the page. The algorithm is at fault, not the data: no
value of `describes` makes that template read well, because the template needs
a *noun phrase* and a *value*, and it is given a clause and nothing.

`— written out in full` (appended to every JSON textarea) and
`— FSME writes this one for you.` are the same mistake in smaller type: engine
bookkeeping rendered as if it were help.

### Where each phrase should come from

| Phrase | Origin | Verdict |
|---|---|---|
| "which kind of card it is" | `CARD_WORDS["type"]` | metadata — needs a question form |
| "families it belongs to" | `CARD_WORDS["tags"]` | metadata — needs a question form |
| "the roll needed to hit it" | `CARD_WORDS["roll"]` | metadata — acceptable as a noun, poor as a label |
| "attack" | **no metadata at all** | metadata gap — `CARD_WORDS` has no entry |
| "Not used while … says what it says." | `valueHtml` template | **algorithm** — needs the value, not the label |
| "written out in full" | `structureHtml` template | **algorithm** — internal concept surfaced |
| "FSME writes this one for you" | `WRITINGS` constant | **should not be shown at all** |

---

## Problem inventory

Severity: **S1** blocks understanding · **S2** causes trial and error · **S3** friction.

| Area | Current UI | Problem | Sev | Recommended solution |
|---|---|---|---|---|
| **Field order** | alphabetical everywhere | ability asks cost & description before "what happens"; static asks "by how much" before "which number" | S1 | 8 — drop `sorted()`, publish declared order |
| **Labels** | sentence fragments | "the rules it follows", "by how much" | S1 | 1 — add a question-form label to metadata |
| **`unless` explanation** | "Not used while which kind of card it is says what it says." ×4 | meaningless; most repeated text on page | S1 | 7+8 — template must name the *answer* |
| **Validation location** | "Needs at least one effect" ×2 | with 3 abilities, no way to know which is broken; engine knows and the layer discards it | S1 | 7 — carry location to the page |
| **Validation wording** | "Missing 'trigger'" | quotes an internal key; user saw a box called "when it happens" | S1 | 7 — resolve key → label via metadata |
| **Card numbers** | 4 disabled boxes on every loot card | pure noise, each with the broken sentence | S1 | 8 — hide, don't grey, when settled by kind |
| **Effect chooser** | ~65 sentences + 7 control nodes in one list | wall; control structures read as effects | S2 | 8 — group; separate "what happens" from "how it is shaped" |
| **Ability cost** | `<details open>`, 5 fields always | most cards pay nothing | S2 | 8 — collapse until wanted |
| **`values_mean`** | only `trigger` has glosses | scopes, stats, zones, forbids, card types are raw identifiers | S1 | 5 — extend the existing field |
| **Scope** | "whose events it listens to" + `self`/`any` | engine words; no explanation after choosing | S1 | 1+6 — question + per-value meaning |
| **Static scope** | `controller`, `opponents`, `all_monsters` | raw identifiers | S1 | 5 |
| **Static stat** | `max_hp`, `loot_plays`, `shop_cost` | raw identifiers | S1 | 5 |
| **`forbids`** | `play_loot`, `activate`, `purchase` | raw identifiers | S2 | 5 |
| **Card type** | 12 raw values incl. `bonus_soul`, `token`, `other` | kind screen offered 6 friendly ones; the tail offers 12 raw | S2 | 5+8 |
| **Dynamic values** | label printed twice, then a way-chooser below the control | "how much damage" appears twice in a row | S2 | 8 — chooser above, single label |
| **References** | "Nothing earlier in this card has made one yet." | true but offers no way forward | S2 | 6 — say what would make one |
| **`store`** | no control on effect nodes | cannot name a value deliberately | S2 | metadata gap |
| **Conditions** | 22 statements, "the counters on this card compare as you say" | reads as prose, not choices | S2 | 1 — phrase as conditions |
| **Nested structures** | JSON textareas for `tags`, `rewards`, `metadata` | a non-programmer cannot write JSON | S2 | 8 — real controls or hide |
| **`id` / `expansion`** | "— FSME writes this one for you." | internal; should not be on screen | S3 | 8 — remove from the form |
| **Add buttons** | "＋ a rule the card follows" | description where a verb belongs | S3 | 1 — "Add a rule" |
| **Required marker** | `NEEDED` | shouting; and "This one has to be filled in." duplicates it | S3 | 1 |
| **Target kind** | aiming `steal_soul` at a treasure validates clean | **no error at all** — a real gap, not wording | S2 | see architecture |

---

## Human-readable vocabulary

Three registers, kept apart on purpose. **An engine term must never become user
text by default.**

### Engine terms → author terms

| Internal concept | Current wording | Recommended user wording |
|---|---|---|
| `ability` | "a rule the card follows" | **Rule** — "What the card does" |
| `static` | "a number this card changes while it is in play" | **Ongoing effect** — "While this is in play" |
| `trigger` | "when it happens" | **When does this happen?** |
| `scope` (ability) | "whose events it listens to" | **Whose actions does this react to?** |
| `scope` (static) | "who it applies to" | **Who does this affect?** |
| `zone` | "where the card must be standing, if not in play" | **Where must the card be?** |
| `replacement` | "it changes the event instead of reacting to it" | **Replace the event instead of reacting to it** |
| `optional` | "the controller may decline it" | **The player may say no** |
| `effects` | "what happens" | **What happens** ✅ keep |
| `conditions` | "what must be true for it to happen at all" | **Only if…** |
| `targets` | "what it picks out before anything runs" | *(hide — the aim question already asks it)* |
| `cost` | "what the player pays to use it" | **What does the player pay?** |
| `stat` | "which number it changes" | **Which number changes?** |
| `amount` (static) | "by how much" | **By how much?** ✅ keep, but ask it second |
| `forbids` | "an action it does not allow instead" | **Or: stop players from…** |
| `per_counter` | "a counter it is worth its amount for each of" | **Count it once per counter** |
| `store` / `stores` | "the name of a value an earlier step stored" | **Remembered value** |
| `worked_out` | "worked out while the ability runs" | **Work it out during the game** |
| `one_of` group | "the way it is worked out" | **Where does the number come from?** |
| `unless` | *(never named)* | **Not used because …** |
| `a_list_of` / `body` | — | *(structural — never shown)* |
| `shaped_like` / `nested` | — | *(structural — never shown)* |
| `written out in full` | appended to JSON boxes | **Advanced — written as card data** |
| `BY_BINDING` | "FSME writes this one for you" | *(remove from the form entirely)* |
| `passthrough` targets | "what an earlier step chose" | **From an earlier step** ✅ keep |

### Four Souls terms — prefer these wherever they fit

`cents` (not coins) · `loot` · `treasure` · `soul` · `tap` / `untap` ·
`recharge` · `roll` · `DC` · `attack roll` · `shop` · `monster slot` ·
`eternal` · `counter`.

The cost block already gets this right (`cents`, `tap the card`, `loot cards to
discard`). It is the model for everything else.

### Rule

> A word may reach the user only if a Four Souls player would use it. If the
> only available word is the engine's, that is a missing description, not a
> label.

---

## Help model

A metadata-driven help layer, sitting on the existing description layer rather
than replacing it. **No renderer branches.**

The root cause is that `describes` is overloaded. Split it by purpose, exactly
as `kind`, `role` and `written_as` are already separate because they answer
different questions:

| Slot | Answers | Shown as | Example |
|---|---|---|---|
| `asks` *(new)* | What is the person being asked? | the `<label>` | "Which number does it change?" |
| `describes` *(exists)* | What is this, as a noun phrase? | inside composed sentences | "the number it changes" |
| `means` *(new, optional)* | Why would I want this? | one dim line under the control | "Most cards change attack or hit points." |
| `values_mean` *(exists, extend)* | What does this option say? | option text | `max_hp` → "maximum hit points" |
| `chosen_means` *(new, optional)* | What did I just choose? | one line after selection | `self` → "Only when this very card is involved." |
| `deeper` *(new, optional)* | The full story | `<details>`, closed | replacement timing, zones |

Rules that keep this from becoming a wall of text:

1. `asks` is **required** for anything a person answers. A missing `asks` is a
   test failure, the way a missing `role` already is.
2. `means` is **at most one sentence** and only where the label cannot carry it.
3. `deeper` is always collapsed and never counted as visible text.
4. Nothing composed from `describes` may be shown unless the template can also
   name a **value** — that is what fixes the `unless` sentence:

   > Not used because **which kind of card it is** says what it says. ❌
   > Not used — a **loot card** has no hit points. ✅

   Both halves are already in the metadata (`unless` names the field,
   `unless_when` names the values, `values_mean` can gloss them).

### Validation explanations

Messages need three parts, all derivable:

| Part | Source | Today |
|---|---|---|
| **where** | the path the checker already builds | thrown away by `in_plain_words` |
| **what** | key → `asks` via metadata | quotes the raw key |
| **what to do** | `values` + `values_mean`, or `did_you_mean` | partly there |

> `Missing 'trigger'`
> → **Rule 2: say when it happens.**

> `'attack_dice' is not one of the ones 'scope' allows here — 'attack' or 'max_hp' or …`
> → **"Who does this affect?" is set to *the card's controller*, so it can
> change a player's numbers — attack, maximum hit points, rolls. Try *attack*.**

---

## Progressive disclosure

### Essential — always visible

Card name · printed text · card kind · **the rules list** · for each rule:
**when it happens** and **what happens** · the aim question on an effect that
needs one · the live "is this ready" line.

### Occasional — one click away, collapsed

Conditions ("Only if…") · cost · optional · ongoing effects (statics) ·
printed numbers **that this kind of card actually has**.

### Advanced — behind "Advanced", collapsed

Scope · zone · replacement · dynamic values · references · `description` ·
tags · rewards · free-form notes · control structures beyond `if` / `may`.

### Internal — never shown

`id` · `expansion` · `as` bindings · `targets` as a list · every
`BY_BINDING` / `BY_ENGINE` note · `— written out in full`.

### Noise reductions, in order of payoff

1. Restore declared field order (one line).
2. **Hide** kind-settled numbers instead of greying them — removes four boxes
   and four broken sentences from every loot card.
3. Collapse `cost` unless it holds something.
4. Split the step chooser: *what happens* (effects) vs *how it is shaped*
   (if / may / repeat / choose).
5. Move the way-chooser above its control and print the label once.
6. Drop the `id` / `expansion` rows.

Estimated effect on the measured card: **1700 → ~600 words, 39 → ~14
controls**, with nothing removed from what the editor can build.

---

## Newcomer check

Format as requested. *Can existing metadata provide it?* / *New metadata?*

**1. Create a simple card**
```
Current experience:  Name, text, kind screen — clear. Then "More about this
                     card" opens with `attack` and four greyed boxes.
Problem:             The first thing after the friendly part is noise.
Severity:            S2
Recommended:         8 (hide settled fields) + 1 (question labels)
Existing metadata:   Yes — unless / unless_when already say it
New metadata:        No
```

**2. Add an effect**
```
Current experience:  "＋ a rule the card follows", then a rule box whose first
                     questions are conditions, cost and description. "What
                     happens" is fourth. The chooser is ~72 sentences.
Problem:             The main question is buried; the list is a wall.
Severity:            S1
Recommended:         8 (declared order, grouped chooser) + 1 (verb on button)
Existing metadata:   Yes — declared order exists and is discarded
New metadata:        A grouping hint for the chooser would help; not required
```

**3. Choose a target**
```
Current experience:  "Who or what does this happen to?" with good option text.
Problem:             Best question on the page. Only flaw: no confirmation of
                     what the choice means, and a wrong kind is not refused.
Severity:            S2
Recommended:         6 (contextual line) + validation gap (see architecture)
Existing metadata:   Yes — `gives` already says players/cards
New metadata:        No
```

**4. Add a condition**
```
Current experience:  "what must be true for it to happen at all", then 22
                     statements like "the counters on this card compare as you
                     say".
Problem:             Reads as prose; several are unintelligible cold.
Severity:            S2
Recommended:         1 (rephrase as conditions) + 5
Existing metadata:   Partly — `describes` exists but is phrased as narration
New metadata:        No — rewording existing values is enough
```

**5. Several effects**
```
Current experience:  Works. Add / remove / ↑ / ↓ all present.
Problem:             Order is not visibly meaningful; no numbering.
Severity:            S3
Recommended:         8 (number the steps)
Existing metadata:   Yes
New metadata:        No
```

**6. A random value**
```
Current experience:  Add "Roll a die through the engine RNG" — an engine
                     phrase in the user's face. Then the result is reachable
                     only under the built-in name `dice`.
Problem:             "engine RNG" is internal; the link between rolling and
                     using the roll is invisible.
Severity:            S1
Recommended:         1 (reword the effect) + 6 (say what it remembers)
Existing metadata:   Yes — `stores` already says `dice`
New metadata:        No
```

**7. Use an earlier result**
```
Current experience:  If nothing rolled yet: "Nothing earlier in this card has
                     made one yet." If it did: a picker offering `dice`.
Problem:             The empty message is a dead end — it never says that
                     rolling a die is what creates one.
Severity:            S2
Recommended:         6 (name the effects that would make one)
Existing metadata:   Yes — `stores` is on every effect that keeps a result
New metadata:        No
```

**8. Several abilities**
```
Current experience:  Works, and bindings stay local. But every rule is titled
                     "the rules it follows" and rules are not numbered.
Problem:             Cannot tell rules apart; validation cannot point at one.
Severity:            S1
Recommended:         8 (number and summarise each rule) + 7
Existing metadata:   Yes — trigger + first effect can summarise a rule
New metadata:        No
```

**9. Create a static**
```
Current experience:  "＋ a number this card changes while it is in play", then
                     "by how much" first and "which number it changes" last,
                     with raw values `max_hp`, `loot_plays`, `shop_cost`.
Problem:             Backwards order; identifiers as choices.
Severity:            S1
Recommended:         8 (declared order) + 5 (glosses)
Existing metadata:   Order yes; glosses no
New metadata:        `values_mean` for stats, scopes, forbids
```

**10. Fix a validation error**
```
Current experience:  "Needs at least one effect" — twice, for three rules,
                     with no indication which.
Problem:             Cannot act on it. The engine knew; the layer discarded it.
Severity:            S1 — the worst defect found
Recommended:         7 (carry location) + 8 (show it on the rule)
Existing metadata:   The path exists in the raw message
New metadata:        No — but the message must become structured (see below)
```

---

## Priority

### P0 — the interface is not understandable without these

1. **Restore declared field order** — delete `sorted()` in `capabilities._fields`.
2. **Fix the `unless` sentence** — name the answer, not the label; or hide the
   field entirely when settled by the card kind.
3. **Validation must say *where*** — which rule, which box.
4. **Validation must not quote internal keys** — resolve key → label.
5. **`asks` (question-form label) for every answerable parameter**, plus the
   missing entries (`attack`, and anything else with no `describes`).
6. **`values_mean` for scope, stat, zone, forbids, card type** — no raw
   identifier may reach a dropdown.
7. **Hide kind-settled numbers** rather than greying them.
8. **Remove `id` / `expansion` / "FSME writes this one for you"** from the form.

### P1 — substantially better usability

9. Group the step chooser: what happens vs how it is shaped.
10. Number and summarise each rule ("Rule 1 — when this is played: deal 1 damage").
11. Collapse `cost` until used; collapse Advanced.
12. `chosen_means` — one line confirming what a choice does.
13. Fix the doubled label on dynamic values; put the chooser first.
14. Say what would create a remembered value when none exists.
15. Reword conditions as conditions; reword `roll_dice` without "engine RNG".
16. Verbs on add buttons.

### P2 — polish

17. `deeper` collapsible help for replacement, zone, scope.
18. Replace `NEEDED` with something quieter; drop the duplicate message.
19. Real controls for `tags` and `rewards` instead of JSON.
20. Card kind: offer the six an author uses, the rest behind "less common".
21. Live plain-English restatement of the rule being built.

---

## Architecture recommendation

> **How do we add a human layer on top of metadata-driven UI without turning
> the renderer back into hardcoded exceptions?**

**By widening the metadata's vocabulary, not the renderer's.** The renderer
already asks the metadata *what control to draw*. It must additionally ask
*how to say it*, and get an answer for every parameter — never guess, never
special-case.

Three rules keep it honest:

1. **One slot per purpose.** `asks` (a question), `describes` (a noun phrase),
   `means` (one line of why), `values_mean` (what an option says),
   `chosen_means` (what a choice did), `deeper` (the full story). The failure
   we have now is one slot serving three purposes; adding purposes to the same
   slot again would reproduce it.
2. **Required, and tested.** `asks` must be as mandatory as `role` already is.
   `tests/test_ability_metadata.py` already refuses a parameter with no role;
   the same test refuses one with no question. **A capability with no human
   description is an incomplete capability**, and that is what stops the
   renderer from ever needing a fallback branch.
3. **Composition templates may only use slots built for composition.** The
   `unless` bug is a template reaching for a slot that was never meant for it.
   A template that needs a value must be given a value.

Field importance (`essential` / `occasional` / `advanced`) is genuinely new
information — nothing in the engine knows it, because it is a fact about
authors, not about execution. It belongs beside the descriptions, declared once
per parameter, and the renderer groups by it without knowing any field's name.

### Flagged as architectural, not implemented

Three items need a decision before they can be built. All are noted here and
left alone, per the brief.

- **Structured validation messages.** Today a problem is a sentence, and
  `in_plain_words` reduces it further by discarding the path. To point at a
  rule the page needs the location as *data* — `{where, what, why, try}` —
  which changes the shape of `validate_card`'s return value. That is a
  boundary change and the single highest-value one available.
- **Target-kind checking on the aim.** Aiming `steal_soul` at
  `target_treasure` validates clean today. `TargetShape.yields` already knows
  the kind and `references.py` already compares kinds for bound groups; the aim
  path does not. This is a correctness gap that happens to look like a UX
  complaint.
- **`store` on effect nodes.** The metadata publishes `store` for control nodes
  only, so an author cannot deliberately name a value. Closing it means saying
  in metadata what the interpreter already strips from every node.

### What can be done with metadata alone

P0 items 5, 6 and most of the vocabulary table; P1 items 12, 14, 15; P2 17.
These are new fields on `ParamShape` plus text — no renderer change.

### What needs the renderer

P0 items 1, 2, 7, 8; P1 items 9, 10, 11, 13, 16; P2 18, 20, 21. All are
generic: ordering, grouping, collapsing and template repair. **None requires
naming a field, an effect or a node.**

### What needs an architecture decision first

P0 items 3 and 4 (structured validation), plus the target-kind gap and `store`.
