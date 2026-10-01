# Capability coverage: what the form can make

An architecture review, measured rather than assumed. Every claim below was
checked by running the real path — build a card the way the form builds it,
validate it the way the loader validates it, and play it in a real game — not
by reading either side and inferring the other.

Measured at `75a070b`, against 1045 shipped cards, 63 effects, 44 conditions,
46 targets, 66 triggers, 15 node shapes and 7 control nodes.

Brought up to date at `c65699d` for the nine changes made since: `10af2e4`,
which refuses a blank required parameter of an effect or a condition,
`55c450f`, which draws a card's `tags` as a list of words, `8df552b`, which
refuses a blank `card.id`, `card.name` or `card.expansion`, `36666fd`, which
refuses a card's own field written as a different kind from the one its shape
declares, `d763217`, which refuses `true` or `false` as the value of a
reward, `67f9744`, which refuses an item of a list written as a different kind
from the one the metadata declares for its items, `10863bd`, which refuses
an item of a list of text written as `""`, `b76482b`, which writes a
`repeat` count left blank as `null` rather than `0`, so the checker refuses it,
and `c65699d`, which makes `player_has_*` read its number under any of its
three spellings with an operator as it already did without one, and refuses
two spellings written together. Only the entries those nine touch were
changed. Nothing was remeasured for that update, so every figure below is
still the one taken at `75a070b`; the corpus still checks 1045 of 1045 and the
replay of 1000 games is unchanged.

## The headline

**Every shipped card that carries rules can be walked by the form — 352 of 352,
and a card can be made from nothing by clicking.**

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
| Games replayed against the previous commit | 1000 / 1000 identical |

The whole of a card can now be made by clicking: a set, a kind, a starter
effect, a counter nobody has used before, a chosen target, an `if` with a
condition and a nested effect — checked clean, saved, reopened, and identical.
Measured in a real browser, with no page errors.

What remains is listed in full in §6. None of it stops a card being made; most
of it is the engine knowing something the metadata does not say.

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

# 2. What the engine knows and the metadata does not say

The two domains this section used to list are closed. What is left is of the
same kind and is listed here because it is the same lesson: a fact the engine
enforces in one place and declares in another is a second copy, and the form
reads the copy.

## Closed

| Feature | Closed at | What was done |
| --- | --- | --- |
| `card_in_zone.zone` | `2bf8049` | declares the 12 zones, derived from the state's own fields; a misspelling is refused instead of sitting silently false |
| `place_monster.slot` | `2bf8049` | declares `free` and `unattacked`; a misspelling is refused instead of silently meaning `free` |
| Defaults on conditions and targets | `75a070b` | 21 parameters declare the default their handler already applies |
| The number `player_has_*` compares with | `c65699d` | read as `amount`, then `count`, then `value` whether or not an operator is written; two spellings written together are refused |

## Undeclared on purpose — defaults no single value can state

`75a070b` declared every default that was unconditional. What it deliberately
left alone is the set where the engine reads the same parameter differently
depending on what else the card wrote, so that no single declared value would
be true. One reading among them contradicted the metadata — `player_has_*`
dropped an `amount` or `count` written beside an operator — and was fixed at
`c65699d`. What is left reads one way each, and is undeclared because that way
is not one value.

| Feature | What the engine does |
| --- | --- |
| `operator` on 12 conditions | One shared shape, read per condition. The four `player_has_*`, with no operator, compare `>=` and take a missing number as 1; with an operator, they use that operator and take a missing number as 0, which is what every other comparison takes. `nth_time_this_turn` reads `== 1`, and `last_effect_did` `> 0`, when the card wrote nothing at all. |
| `value` / `amount` / `count` on the four `player_has_*` | Three spellings of one number, declared `instead_of` one another and read in that order — `amount`, then `count`, then `value` — with or without an operator, since `c65699d`. Writing more than one is refused by the checker, and so by the Constructor's check; one alone loads and reads back as written. |
| `minimum` / `maximum` on 11 targets | Default to whatever `count` turned out to be — an answer, not a literal, and `default=` cannot say it. |
| `player` on 10 conditions | Defaults to the ability's controller, which is not a value at all. All 10 that declare it read it that way. |
| `event_value.value` | Whatever the event carried; no default. |
| `as` on 46 targets | Three site-dependent values. Never asked, since FSME writes it. |
| 23 boolean flags | Default to `False`. Truthful but invisible: an unchecked box already says "off". |

No shipped card is affected by any of them. A test pins each as undeclared, so
none can be given a value without somebody deciding first.

---

# 3. Authoring limitations

Places where the path works and the experience does not.

### Open vocabularies — suggested since `cb128d3`

`counter`, `tag` and `named` are genuinely open: an author's own counter is a
legitimate new word, so a closed list would be wrong and would turn every new
set into a validation error. What was missing was a way to *offer* the words
already written without insisting on them, and `suggest_from` is it — 17
parameters name a pool, the words are gathered from the loaded content, and the
form draws a `datalist` on a box that is still an ordinary text box. Measured
against the shipped corpus: 9 counters, 16 tags, 892 card names.

Nothing validating reads it. A word in no pool is as good a card as a word in
all of them, and the checker's verdicts are byte-identical to before.

`key` is deliberately excluded. `modify_event` and `event_value` name a field of
the event being replaced, and which fields exist depends on the trigger the
*ability* names — not in the node and not declared anywhere in the engine. A
pooled list of the eight keys cards happen to use would offer `cents` to
somebody editing a damage watcher, which is worse than an empty box.

### Structured data the form can only show as raw JSON

Three parameters render as a text area holding JSON. Two of them are data the
engine understands and could be asked for field by field; the third is
free-form on purpose and is right as it is.

| Parameter | What it holds | Cards carrying it | Should it stay raw? |
| --- | --- | ---: | --- |
| `card.rewards` | three keys the engine reads: `cents`, `loot`, `treasure` | 255 | No. Every monster has them. |
| `promise.when` | a condition on the replaced event's values | 1 | No, though it is much the rarest of the two. |
| `card.metadata` | notes the engine keeps and never reads | 1018 | **Yes.** Genuinely free-form; a box is the honest control. |

This section previously read *"Nothing structural"*, which was measured wrong.
A set made in the form and a set made in a text editor are still the same
format, and a card the form cannot describe is still refused rather than
quietly rewritten — but two fields above are structure the form does not yet
draw.

`card.tags` was the fourth row of this table until `55c450f`. A list of family
names is now asked as what it is — one box a word, in the order they were
written, with a way to add one and a way to take one out — and every box offers
the `tags` pool it feeds. A blank word and a word already there are not kept,
a family nobody has used before is as good as one everybody has, and a card
opened and kept without a change says the same families in the same order.

---

# 4. Three things that are not the same

This document used to say "the written corpus comes back byte-identical" and
leave it there. That sentence is true of one of the three questions below and
false of another, and running them together is how a real difference went
unnoticed for several commits.

### File fidelity — **no**

**Not one of the 1045 shipped cards comes back from the desk identical to its
file.** Opening a card and saving it rewrites it, always:

| What changes | Cards |
| --- | ---: |
| The `id` is regenerated from expansion + type + name | **1045** |
| An inline aim becomes a named binding (`target: "self"` → a bound group) | 170 |
| A shorthand effect is written out in full (`{"draw_loot": 2}`) | 116 |
| `schema_version` is added | 31 |

The id is the one worth knowing about: a *shipped* card opened in the desk and
saved is saved under a different identifier. An author's own cards were written
by the desk in the first place, so they are unaffected.

### Round-trip stability — **yes, 1045 / 1045**

read → write → read is a fixed point. What comes back the second time is what
came back the first. This is what the gate table at the top measures, and what
"byte-identical written corpus" means in the commit messages: identical *to the
previous commit's writeback*, which is a regression check on the writer. It is
not a claim about the file.

### Runtime neutrality — **yes, proven**

The rewriting above changes no game. Measured by rebuilding the whole content
directory out of the desk's own writeback, keeping the original ids, and
replaying: **58 of 1000 games differed**. Replaying those same 58 seeds with the
thinking bots removed: **58 of 58 identical, entry for entry.**

So the engine plays the rewritten card exactly as it plays the original, and
the divergence is entirely in `fsme.lab.bot` — see §5.

---

# 5. The bot observer is a tooling gap, not an engine one

`appraisal.py::_destroys_itself` decides whether using an ability takes the card
off the board, and it does so by matching the card's *text*: an entry whose
`target` is the literal `"self"`. The desk writes the same meaning as a named
binding, so:

- 8 shipped abilities destroy the card that uses them; the observer recognises
  **8 of 8** as shipped and **0 of 8** after a desk round trip.
- That is the whole of the 58/1000 replay divergence. Without bots the games are
  identical.

Nothing about the Constructor or the Runtime is wrong here. What is wrong is
that the lab's *advice* about a card depends on which of two equivalent
spellings the card is written in — and every card an author makes in the desk
gets the spelling the observer does not recognise. It is listed as an open
tooling gap in §6 and is not fixed in this document's scope.

---

# 6. Everything still open, in one place

Nothing here stops a card being made, and the create-from-nothing path in the
headline was measured with every one of them open. The first is the form
telling an author something untrue; the last four sit outside the
Constructor. `repeat` with no count was here too, and is closed by `b76482b`;
so were branching defaults, closed by `c65699d` — what is still undeclared in
§2 is undeclared on purpose.

| Open | Where | Kind |
| --- | --- | --- |
| `promise.when` shown as raw JSON | §3 | The form does not draw structure it understands. `card.tags` was here too, and is drawn as a list of words since `55c450f` |
| Two modes described identically are accepted | `cards/validator.py` | 0 occurrences in the corpus; the player sees two options they cannot tell apart |
| Two `may` nodes under one name are answered together | `runtime/interpreter.py` | 33 `may` nodes in the corpus, 7 name one and none share a name; telling them apart needs the nodes to be identifiable |
| The bot observer reads a card's spelling | §5 | `fsme.lab.bot` — playtesting advice, not rules |
| `runtime.py:122` names `_where_it_stands`, a function that has never existed | `runtime/runtime.py` | One word of documentation; the method is `_where_it_works` |

## Decided, and waiting on a second use

**`card.rewards` stays a box of card text.** What a monster pays out is an open
set of names with whole numbers under them: the model calls it a mapping of
integers, the checker asks only that each value be one, and the reader and the
writer return the whole thing as written. The runtime is the narrow one — it
pays `cents`, `loot` and `treasure` and ignores the rest — and that is about
the game, not about what a card may say.

Describing that interior is not something this layer can do. A container says
what it holds by naming a shape, and a shape is a closed set of keys, so a
description would refuse a card the engine accepts; it would also settle, as a
side effect, whether an empty `{}` survives a round trip. Both are decisions
worth taking deliberately, and neither is worth taking for one field. It is
revisited when a second field of the same shape exists to design against — a
mechanism drawn from a single use is a special case wearing a general name.
Pinned by `test_a_monsters_rewards_stay_the_data_they_are`.

## Closed, and not to be reopened

The `v0.9.0` tag is on the remote (`f9d8f9f`, peeled to `a363d8d`) and matches
the local one; the HTTP 403 that once blocked it no longer applies. The four
metadata gaps under "Metadata completeness" are closed. So are the two zone
domains, the vocabulary suggestions, and the unconditional defaults.

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
| `card_in_zone.zone`, `place_monster.slot` | ✅ | ✅ | ✅ | Domains declared and offered as a list; `2bf8049` |
| `counter` / `tag` / `named` | ✅ | ✅ (open) | ✅ | Open on purpose, and suggested from loaded content; `cb128d3` |
| `key` on `modify_event` / `event_value` | ✅ | ✅ (open) | ⚠️ | Open on purpose; no honest source of suggestions — see §3 |
| Unconditional defaults on conditions and targets | ✅ | ✅ | ✅ | 21 parameters say what a blank box means; `75a070b` |
| Branching defaults (`operator`, `value`, `minimum`…) | ✅ | ❌ | ⚠️ | Read one way each since `c65699d`, and undeclared on purpose; see §2 |
| `card.tags` | ✅ | ✅ | ✅ | A list of words, one box each, offering the `tags` pool; `55c450f` |
| `card.rewards`, `promise.when` | ✅ | ✅ | ⚠️ | Structure shown as raw JSON; see §3 |
| `card.metadata` | ✅ | ✅ | ✅ | Free-form on purpose; a box is the honest control |

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

All four are closed, and two more have closed since: the zone and slot domains
at `2bf8049`, and the unconditional defaults on conditions and targets at
`75a070b`. What is still undeclared is in §2, and it is undeclared on purpose —
the engine reads each of those parameters one way, but that way depends on
what else the card wrote or is not a literal, so there is no one value to
write down.

---

# B. Missing authoring capabilities

The earlier edition of this table counted, for each missing capability, how
many shipped cards it blocked. That method no longer applies: no shipped card
is blocked, so every count would be zero. What is left is measured differently
— by whether the engine enforces something the metadata does not describe, and
whether a person can say it by clicking.

| Feature | Technical location | Difficulty | Value to authors |
| --- | --- | --- | --- |
| `card.rewards` as real fields | `capabilities._fields`, the renderer | Low — three known keys | 255 cards; every monster has them |
| `promise.when` as real fields | the renderer | Medium | 1 card |

---

# C. Recommended roadmap

## Done since this section was last written

1. ~~`card_in_zone.zone` and `place_monster.slot` domains~~ — **closed**,
   `2bf8049`.
2. ~~Counter and tag suggestions drawn from loaded content~~ — **closed**,
   `cb128d3`, as `suggest_from`.
3. ~~Defaults the engine applies and the metadata does not state~~ — **closed
   for the unconditional ones**, `75a070b`.
4. ~~Refusing an empty required value~~ — **closed for the parameters of
   effects and conditions**, `10af2e4`: `add_counter.counter`,
   `modify_event.key` and `event_value.key` written as `""` are refused as
   missing. **Closed for the card's own** `card.id`, `card.name` and
   `card.expansion`, `8df552b`: written as `""` by hand, each is refused as
   missing, the same as when it is left out.
5. ~~`card.tags` as a real field~~ — **closed**, `55c450f`, as a list of words
   offering the `tags` pool.
6. ~~A card's own field written as the wrong kind~~ — **closed**, `36666fd`.
   Found after this list was last written, not carried on it before. The
   checker now reads what each of a card's own fields is from the card's shape
   and refuses a field written as something else — `tags` as one word, `name`
   or `id` as a number, `true` where a number belongs, and `metadata` or
   `statics` as text, both of which used to pass the checker and then fail
   inside the loader with an `AttributeError` that named no card and no file.
   The fields the checker already judged in words of their own — the kind of
   card, the printed numbers, `rewards`, `abilities` — keep those words and are
   not told twice. No shipped card is written as the wrong kind. What the
   words inside `tags` may be was open here and not part of it, and is closed:
   `[1, 2]` by `67f9744`, `[""]` by `10863bd`.
   A reward written as `true` was open here too, and is closed by `d763217`.
7. ~~A reward written as `true` or `false`~~ — **closed**, `d763217`. A
   reward's value is now read the way the printed numbers are, so `true` and
   `false` are no longer taken for whole numbers. The message is the one it
   always was, `reward '<name>' must be an integer`, and which names a reward
   may have is as open as before. No shipped card pays a reward of `true` or
   `false`.
8. ~~An item of a list written as the wrong kind~~ — **closed**, `67f9744`.
   A list's own shape may now say what each of its items is, as `item_kind`,
   and the checker reads it from there and refuses an item written as
   something else: `must be a list of text, and item <n> is <kind>`, once,
   for the first such item. `card.tags` is the only field that says so today,
   as a list of text. No shipped card has a tag that is not text.
9. ~~A word in a list of text written as nothing~~ — **closed**, `10863bd`.
   An item of a list of text written as `""` is refused, `must be a list of
   text, and item <n> is blank`. Only `""` is blank: a word of spaces and a
   word with spaces round it still pass, and nothing is trimmed or rewritten.
   No shipped card has a blank tag.
10. ~~A contract for `repeat` with no count~~ — **closed**, `b76482b`. A count
    left blank in the form used to be written as `0`, which the checker had to
    accept, so a repeat of no times was saved as finished. It is now written
    as `null`, which the checker refuses as it refuses `null` anywhere a whole
    number belongs, and the card is reported unfinished. An explicit `0` is
    still written and accepted and means no times; `1` and above are as they
    were. The runtime and the metadata are unchanged. What changed is the
    placeholder the form writes for any whole-number key that names its node,
    and `repeat` is the only such key. `repeat` has no uses in the shipped
    corpus.
11. ~~Branching defaults~~ — **closed**, `c65699d`. The four `player_has_*`
    read their number as `amount`, then `count`, then `value` — three
    spellings of one parameter, declared `instead_of` one another — and now
    read it that way whether or not an operator is written. Before, an
    operator made them read `value` alone, so `{"operator": "<", "amount": 3}`
    compared with 0 and meant "fewer than none". With no operator the
    comparison is `>=` and a missing number is 1; with one, the comparison is
    the one written and a missing number is 0. Those two defaults are not
    changed. Writing two or three of the spellings together is refused by the
    checker, which reads which keys are spellings of which from `instead_of`
    rather than from any name, and the Constructor's check refuses it with
    it. The runtime outside that branch, the metadata and the Constructor are
    unchanged. No shipped card writes an operator beside `amount` or `count`,
    or two spellings together: the corpus still checks 1045 of 1045, and the
    replay of 1000 games is unchanged, MD5 `e64103a4013de99a2cf09f9ed44443b5`.
    The defaults in §2 that are still undeclared are undeclared on purpose.

## Next small improvements

Still metadata the engine already has, or a contract that needs stating. No new
UI concepts, no DSL change.

1. **`card.rewards` as real fields.** `card.tags` was here too, and is done.
   So was a contract for `repeat` with no count, closed by `b76482b`.

It does not block a card being made.

## Beyond that

The milestone this document was written to describe — *"the ability, not just
its effects"* — is done. Node shapes carry real metadata, the catalogue hands
them to the page, the renderer draws the ability's own fields from them, and
each effect declares what kind of target it accepts.

Anything further is a question about what the tool should become, not a gap
between what the engine can do and what the form can say. This document does
not guess at it: a capability belongs here once it has been measured.
