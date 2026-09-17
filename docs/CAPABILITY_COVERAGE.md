# Capability coverage: what the form can make

An architecture review, measured rather than assumed. Every claim below was
checked by running the real path — build a card the way the form builds it,
validate it the way the loader validates it, and play it in a real game — not
by reading either side and inferring the other.

Measured at `590add3`, against 1045 shipped cards, 63 effects, 44 conditions,
46 targets, 66 triggers and 7 control nodes.

## The headline

**Every shipped card that carries rules can be walked by the form — 352 of 352.**

The layer this document was first written about is closed. Effects, conditions
and targets were already complete; what was missing was the layer above them —
the ability that holds them and the control nodes that shape them — and the
node shapes now reach the page, carry real kinds, and render through the
machinery that was already there.

| Gate | Result |
| --- | ---: |
| Shipped cards readable | 1045 / 1045 |
| Shipped cards stable through read → write → read | 1045 / 1045 |
| Rule-bearing cards the checker passes | 352 / 352 |
| Rule-bearing cards the walk can reach the end of | 352 / 352 |
| Written corpus after a full rewrite | byte-identical |

What remains is listed in §2 and §3, and it is small: two undeclared domains
and one absent set of suggestions.

---

# 1. Fully supported capabilities

Exists in the engine, has metadata, can be built in the form, survives
read → write → read, and plays.

## Effects — 63 of 63

Every effect carries a sentence about itself; none is bare.

## Conditions — 44 of 44

Including `and`, `or` and `not`, which now have shapes and can be nested
inside a branch, so a test is no longer capped at one.

## Targets — 46 of 46

Plus their own parameters, rendered recursively.

## Control structures — 7 of 7

`if`, `may`, `choose`, `for_each`, `repeat`, `sequence` and `stop`. Each is
offered by the walk under its own sentence, each can be drawn, each can be
finished, and each round-trips and plays. Measured one by one.

## Card abilities — 10 of 10 fields

`trigger`, `effects`, `targets`, `scope`, `conditions`, `cost`, `optional`,
`replacement`, `zone` and `description`. More than one ability per card is
supported.

## Static abilities — 7 of 7 fields

`stat`, `amount`, `scope`, `conditions`, `description`, `forbids` and
`per_counter`. A card may carry statics beside an ability or instead of one.

---

# 2. Engine capabilities not currently authorable

Two, both of the same kind: a domain the engine enforces and the metadata does
not declare, so the form offers a text box where it could offer a list.

| Feature | Where it lives | What happens today | Intentional? |
| --- | --- | --- | --- |
| `card_in_zone.zone` | the handler does `getattr(state, zone)` and answers *false* for anything unknown | the parameter declares no values, so a typo makes a condition that is silently never true | Accidental — the zones are a closed set |
| `place_monster.slot` | the handler reads `unattacked` and treats everything else as `free` | the parameter declares no values, so a typo silently means `free` | Accidental — likewise |

Neither is a Runtime defect: the Runtime does exactly what it says. Both are
metadata gaps, and both are two `values=` declarations away from closing.

---

# 3. Authoring limitations

Places where the path works and the experience does not.

### Open vocabularies with no suggestions

`counter`, `tag`, `named` and `key` are genuinely open — an author's own
counter is a legitimate new word, so a closed list would be wrong. But the
loaded content already contains the answers (`charge`, `egg`, `tear`, `nuke`,
`knot`, `gold`, …; tags `guppy`, `passive`), and nothing offers them. This is a
suggestion gap, not a validation gap: an unknown word is accepted on purpose.

### Available only by hand-editing JSON

Nothing structural. A set made in the form and a set made in a text editor are
the same format, and a card the form cannot describe is now refused rather
than opened and quietly rewritten.

---

# A. Current capability matrix

| Capability | Engine | Metadata | UI | Status |
| --- | :---: | :---: | :---: | --- |
| Effects (63) | ✅ | ✅ | ✅ | Fully supported |
| Conditions (44) | ✅ | ✅ | ✅ | Fully supported |
| `and` / `or` / `not` | ✅ | ✅ | ✅ | Fully supported; branches nest |
| Targets (46) | ✅ | ✅ | ✅ | Fully supported |
| Target parameters | ✅ | ✅ | ✅ | Rendered recursively |
| Effect → target kind | ✅ | ✅ | ✅ | Declared on 27 effects and refused at check time |
| Triggers (66) | ✅ | ✅ | ✅ | Fully supported |
| Control nodes (7) | ✅ | ✅ | ✅ | Fully supported |
| One ability per card | ✅ | ✅ | ✅ | Fully supported |
| Several abilities | ✅ | ✅ | ✅ | Fully supported |
| `ability.scope` | ✅ | ✅ | ✅ | Fully supported |
| `ability.conditions` | ✅ | ✅ | ✅ | Fully supported |
| `ability.replacement` / `cost` / `optional` / `zone` / `description` | ✅ | ✅ | ✅ | Fully supported |
| Statics | ✅ | ✅ | ✅ | Fully supported, with or without an ability |
| Dynamic heads `from` / `count` / `from_event` / `last_result` | ✅ | ✅ | ✅ | Builds, validates and plays |
| `player_of` | ✅ | ✅ | ✅ | Fully supported |
| `previous_target` / `previous_result` / `group` | ✅ | ✅ | ✅ | Fully supported |
| `store` | ✅ | ✅ | ✅ | Declared on `roll_dice`, `reroll` and all seven control nodes |
| `promise` change operations | ✅ | ✅ | ✅ | Six declared; an unknown one is refused |
| `card_in_zone.zone`, `place_monster.slot` | ✅ | ❌ | ⚠️ | Text box; see §2 |
| `counter` / `tag` / `named` / `key` | ✅ | ✅ (open) | ⚠️ | Open on purpose; no suggestions |

---

## Parameter system map

`capabilities.catalogue()` hands the page `kinds`, `triggers`, `effects`,
`conditions`, `targets`, `cards`, `abilities`, `statics` and `structures`.
The fifteen node shapes — `ability`, `card`, `static`, the seven control
nodes, and the nested `change`, `cost`, `mode`, `named_count` and
`worked_out` — all reach it.

Their parameters carry real kinds rather than being uniformly `text`:

| Kind | Parameters |
| --- | ---: |
| text | 47 |
| a whole number | 21 |
| a list | 20 |
| anything the engine can only judge during a game | 14 |
| true or false | 10 |
| a set of named values | 3 |

---

## Metadata completeness

The four gaps this document first recorded:

1. ~~What kind of target an effect accepts~~ — **closed.** 27 effects declare
   it and the checker refuses a wrong aim before play.
2. ~~Node shapes never reach the page~~ — **closed.** All fifteen do.
3. ~~Node-shape parameters are all typed `text`~~ — **closed.** See the table
   above.
4. ~~What a `promise` change may say~~ — **closed.** The six operations are a
   declared shape; an unknown one is refused by the checker and by the reader.

What is still undeclared is in §2: two zone domains.

---

# B. Missing authoring capabilities

The earlier edition of this table counted, for each missing capability, how
many shipped cards it blocked. That method no longer applies: no shipped card
is blocked, so every count would be zero. What is left is measured differently
— by whether the engine enforces something the metadata does not describe.

| Feature | Technical location | Difficulty | Value to authors |
| --- | --- | --- | --- |
| Zone and slot domains | `_card_in_zone`, `place_monster` | **Very low** — two `values=` declarations | Removes two silent-failure typos |
| Counter/tag suggestions from content | `ContentLibrary` | Low | Quality of life; the words are already in the corpus |

---

# C. Recommended roadmap

## Next small improvements

Metadata the engine already has, declared where it is enforced. No new UI
concepts, no DSL change.

1. `card_in_zone.zone` and `place_monster.slot` domains — two declarations,
   two silent failure modes gone.
2. Counter and tag suggestions drawn from loaded content.

Both are listed in §2 and §3 and neither is blocking anything.

## Beyond that

The milestone this document was written to describe — *"the ability, not just
its effects"* — is done. Node shapes carry real metadata, the catalogue hands
them to the page, the renderer draws the ability's own fields from them, and
each effect declares what kind of target it accepts.

Anything further is a question about what the tool should become, not a gap
between what the engine can do and what the form can say. This document does
not guess at it: a capability belongs here once it has been measured, and
nothing beyond the two items above has been.
