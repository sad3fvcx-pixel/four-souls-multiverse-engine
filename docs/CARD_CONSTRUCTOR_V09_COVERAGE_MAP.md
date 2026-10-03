# Card Constructor — what is left, after 188e36f

Analysis only. Nothing here was implemented, and nothing here proposes a change
to the card language or to the runtime.

The question this answers is the one that has been implicit since the binding
stages closed: **what is actually still missing from the tooling?** Every prior
stage started from a card the Constructor turned down. There are no longer any
such cards, so this one starts from the language instead, and asks the whole of
it at once.


## 1. How the limitations are classified

Six kinds, because the measurements fell into six kinds. The letters matter
less than the distinction between the last two and everything before them.

| | what it means | what fixing it costs |
|---|---|---|
| **A** | Nothing is missing. The limitation was assumed, not measured. | Nothing. |
| **B** | A second copy that drifted. The fact is already published; something wrote it again by hand and the copy fell behind. | Delete the copy. |
| **C** | A rendering gap. Everything is declared; one control does not exist. | A control. |
| **D** | A declaration gap. The engine enforces a fact and nothing publishes it. | Metadata beside the guard. |
| **E** | A deliberate decision, now in the way. It works exactly as written, and what it was written to do has become the obstacle. | A decision, not code. |
| **F** | A real architectural gap. The language or the engine would have to gain something. | Design. |

Nothing measured in this pass landed in **F**.


## 2. The inventory

Every card in `content/`, by kind, and how far each gets through the desk.
"Rules" means the card has `abilities` or `statics`; "clean" means `check_card`
returns nothing, which is what `save_card` requires.

| kind | cards | with rules | checker-clean |
|---|---|---|---|
| treasure | 287 | 121 | 121 |
| monster | 283 | 96 | 96 |
| loot | 159 | 62 | 62 |
| character | 97 | 30 | 30 |
| starting_item | 71 | 16 | 16 |
| room | 68 | 0 | 0 |
| event | 56 | 19 | 19 |
| curse | 15 | 5 | 5 |
| bonus_soul | 9 | 3 | 3 |
| **all** | **1045** | **352** | **352** |

Three things follow from the last two columns.

**Every card that has rules is checker-clean.** Not most of them, and not the
352 the binding stages worked through — all of them, at every kind. There is no
card in the shipped content whose rules the Constructor cannot open, edit and
save back.

**The 693 without rules are refused, and refused for one reason.** Every one of
them fails on the same sentence, and it is not a validation message at all —
`author.py:474`:

> This card does not do anything yet — say what happens when it is played.

**No kind is empty of shipped content except three.** `soul`, `token` and
`other` are in `CardType` and in nothing under `content/`.


## 3. The decisive measurement: does the language fit through the pipeline?

Every construct the engine declares was put through `read_card` → `build_card`
→ `read_card`, on a minimal synthesised card written in that construct's own
spelling. The bar is the one the test suite uses: the reading of the writing
must equal the reading of the original — *means the same* — and writing twice
must write the same card.

| | declared | held | refused | unstable | meaning changed |
|---|---|---|---|---|---|
| effects (incl. the 7 control nodes) | 70 | **70** | 0 | 0 | 0 |
| conditions | 44 | **44** | 0 | 0 | 0 |
| targets | 46 | **46** | 0 | 0 | 0 |
| other nodes (`cost`, `mode`, `worked_out`, `named_count`) | 4 | **4** | 0 | 0 | 0 |
| **total** | **164** | **164** | **0** | **0** | **0** |

**Author state holds every construct the engine has.** Not the constructs the
shipped cards happen to use — every one the vocabulary declares, including the
ten effects, eighteen conditions, nine targets and thirty-eight triggers that no
shipped card exercises at all.

This is the finding that decides the shape of the rest of this document. After
the binding stages there is **no representation gap anywhere in the reader, the
writer, or author state**. Everything below is about what a person is *offered*,
not about what the pipeline can carry.

The card-level shape is complete on the same terms: of every key any shipped
card writes, exactly one is not described — `schema_version`, which the builder
writes and no author types. Nothing described goes unused.


## 4. Card kinds: a second copy, not a missing capability — **B**

`CardType` has twelve members. The desk offers six. That much was known. What
the measurement adds is *where* the six live and what the other six cost.

`cards/types.py` already carries `TYPE_WORDS`, all twelve of them, in a
person's own words, with a docstring that settles the policy outright:

> The engine accepts all twelve. Six of them are what an author usually makes,
> and the rest exist because the shipped content has them — so they are
> described rather than hidden, and whatever offers them decides how prominent
> to be.

`runtime/vocabulary.py` publishes them on the card's own `type` field —
`values` is `tuple(str(kind) for kind in CardType)`, `values_mean` is
`TYPE_WORDS` — and `catalogue()` ships that field to the page in the same
payload as everything else. Measured in the browser, the editor's type control
draws all twelve, labelled with the engine's words:

```
opts   ['', 'character', 'treasure', 'loot', 'monster', 'room', 'bonus_soul',
        'event', 'curse', 'starting_item', 'soul', 'token', 'other']
labels ['— nothing yet —', 'a character somebody plays as', … 'something else']
```

And `check_card` accepts a card of every one of the twelve.

So the six are not a capability the desk lacks. They are one screen:
`chooseKind()` draws `can.kinds`, and `can.kinds` comes from `CARD_KINDS` in
`capabilities.py` — a hand-written six-entry tuple that re-words descriptions
`TYPE_WORDS` already carries, sitting in the same response as the correct list.

The consequence is narrow and worth stating precisely: **a new card cannot be
*started* as one of six kinds, though it can be switched to any of the twelve
one screen later, and an existing card of any kind opens, edits and saves.**
136 shipped cards are of a kind the opening screen does not offer — 56 event,
71 starting_item, 9 bonus_soul, 38 of them carrying rules — and all 136 open
and save today.

This is the exact pattern every stage since `3e3c802` has removed: *a fact
enforced in one place and declared in another is a second copy that drifts.*
Here the first copy is not merely present, it is already delivered to the page.

One related silence, deliberate and documented: `PRINTED_NUMBERS` describes six
kinds, and `_printed_on` says so as an absence, so a kind nobody has described
is refused nothing. An event card is therefore asked for hit points. That is
the documented behaviour — "silence about `starting_item` is silence, not a
claim that it has no cost" — and it is a content question (which kinds print
which numbers), not a tooling one.


## 5. `promise` — the one genuine declaration gap — **D**

`promise` is the only effect the guided walk cannot finish for a reason that is
about metadata rather than about the walk. Measured in the page:

| | `finishable` | `drawable` | why not |
|---|---|---|---|
| `promise` | no | yes | `changes` is required and `shown: "advanced"` |
| `watch_for` | no | yes | `effects` is required and `shown: "body"` |

Both are drawable, so the expert editor draws them in full and the four shipped
`promise` cards read, mean the same, and save. `changes` is drawn as what the
metadata says it is — a set of named values, in a JSON box, under the honest
label *"this one is a piece of the card's own rules, so it is written the way a
card file writes it."*

What is not published is what may go in that box.

`state/promises.py` names six operations and applies them in a fixed order:

```
VALUE   replace what the event carries outright
DELTA   add to a number the event carries
FACTOR  multiply a number the event carries
CAP     lower a number to at most this
FLOOR   raise a number to at least this
FLIP    read a number from the other side: the flip value less what it was
```

`CHANGES = (VALUE, DELTA, FACTOR, CAP, FLOOR, FLIP)` — a closed set, beside the
`apply_to` that enforces it. Of the six, `value`, `delta` and `factor` are also
declared as `modify_event` parameters. **`cap`, `floor` and `flip` are declared
nowhere.** Every shipped `promise` uses one of the three that are not:

```
polycephalus  {"event": "roll_modified", "when": {"attack": true},
               "changes": {"value": {"flip": 7}}}
compost       {"event": "before_loot_draw",
               "changes": {"source": {"value": "discard"}}}
mom_s_bra     {"event": "before_damage", "changes": {"amount": {"cap": 1}}}
two_of_clubs  {"event": "before_loot_draw", "changes": {"count": {"factor": 2}}}
```

So the shape of the gap is exact. `changes` is *a map from an event field to a
change*, and the language already has a word for "a list of X" — `a_list_of`,
landed in Stage 1B — but no word for "a map of names to X". `when` is the same
shape with a simpler value: a map from an event field to what it must equal.

Two things this is **not**:

- It is **not** a card-language change. The four cards already write this and
  the engine already reads it; nothing about the JSON would move.
- It is **not** a question about event field names. `event_value.key` and
  `modify_event.key` are both free text with no closed set, because the events
  a card may name are not a closed set. `promise.changes` keys are the same
  kind of thing and should stay free text, exactly as `modify_event` already
  does. The gap is the *operations*, which are closed and enforced, and the
  *shape* — a set of named values, each shaped like a change.

`watch_for`'s exclusion is different and smaller — see §6.


## 6. The guided walk asks only form questions — **C**

`putable(f)` returns `f.asked !== "never" && f.shown === "form"`, and
`finishable(e)` offers only effects whose every required field is putable. Two
effects in the whole vocabulary fail it, and `watch_for` fails it because
`effects` is `shown: "body"` — a nested list of steps, which the walk has no
way to ask for.

That is a rendering gap and nothing more. `watch_for` is drawable, the expert
editor draws it, and Stage 1B taught the reader and writer to carry it. Every
other effect the walk turns down, it turns down correctly.

Worth naming separately because "unfinishable" reads as one problem in the
page's own report and is in fact two: one effect held back by an undeclared
shape (§5), one by a control the walk does not have.


## 7. What is offered versus what exists

| | declared | offered by the desk | where the rest are |
|---|---|---|---|
| card kinds | 12 | 6 on the opening screen, 12 in the editor | §4 |
| effects | 63 | 63 drawable, 58 offered in the walk | §5, §6 |
| control nodes | 7 | 7, as `structures` | — |
| conditions | 44 | 44 | — |
| targets | 46 | 46, all aimable | — |
| triggers | 66 | 66 | — |

Everything not covered by §4–§6 is already offered. The page reported no
JavaScript errors and no undrawable node.


## 8. Never exercised by shipped content

Not a limitation — a measurement of where the tooling is untested by real
cards. These names appear nowhere in `content/`, as a key or as a value:

- **10 effects**: `attach_curse`, `copy_effect`, `duplicate`, `enter_room`,
  `gain_soul`, `leave_room`, `revive`, and the three control nodes `repeat`,
  `sequence`, `stop`.
- **18 conditions**: `card_in_zone`, `dice_even`, `dice_not_equals`,
  `dice_odd`, `first_turn`, `game_finished`, `item_charged`, `item_depleted`,
  `monster_alive`, `monster_boss`, `monster_dead`, `player_alive`,
  `player_dead`, `player_has_souls`, `player_not_active`, `stack_empty`,
  `stack_not_empty`, `stack_size`.
- **9 targets**: `all_treasures`, `another_player`, `current_player`,
  `event_source`, `none`, `previous_result`, `previous_target`, `target_soul`,
  `top_stack`.
- **38 triggers**, including every stack trigger and most of the purchase and
  loot ones.

All of them held in §3, so the Constructor carries them; nothing has ever asked
it to.


## 9. The 693 — a decision, not a defect — **E**

This is the largest number in the document by an order of magnitude, and the
only finding whose fix is a decision rather than a change.

`check_card` refuses a card with no `abilities` and no `statics`, and it
`return`s that refusal **before** `validate_card` is called. `save_card` refuses
on any problem. So a card with no rules can be opened, read, edited and never
saved back — 693 of the 1045 shipped cards, including all 68 rooms.

The docstring says why, and says it deliberately:

> Plus one thing the engine does not mind and a person would: a card with no
> rules at all. That is perfectly valid content — the shipped sets are full of
> cards whose text has not been implemented — but somebody who has just filled
> in a form did not mean to make one, and telling them it is ready would be
> telling them their card works.

Both halves of that are true, and they now point in opposite directions. The
nudge is right for a person filling in a blank form. It is wrong for a person
who opened a shipped card to fix its name, its cost, or its printed text — the
engine does not mind, the content is full of such cards, and the desk will not
let them put one back.

Nothing about this is a gap in the language, in the metadata, or in the
pipeline. It is one `return` placed before `validate_card`, doing exactly what
it was written to do. Whether an author editing an existing card should meet it
is the user's call, and this document does not make it.


## 10. Priority

| | what | kind | cards affected | intervention |
|---|---|---|---|---|
| **CURRENT** | `CARD_KINDS` — delete the second copy, offer the kinds the catalogue already publishes | B | 136 shipped, all future | one hand-written tuple, the pattern four prior stages already used |
| **NEXT** | `promise.changes` — publish the six operations and the "a set of named values, each shaped like X" shape | D | 4 shipped, all future promises | new declaration capability; no runtime and no card-language change |
| **LATER** | the walk cannot ask for a nested list, so `watch_for` is not offered in it | C | 0 shipped (the editor draws it) | a control |
| **LATER** | the no-rules refusal that short-circuits `validate_card` | E | 693 | a decision first |
| **OUT OF SCOPE** | event field names as a closed set; `PRINTED_NUMBERS` for the other six kinds; anything that would add a mechanic | — | — | — |

**CURRENT is recommended first** on the same grounds every prior stage was
chosen: the largest effect for the smallest, most familiar intervention, and it
removes a hardcoded list rather than adding one. It is also the only item where
the correct answer is already computed and already on the wire.

**NEXT is the only item that adds a capability**, and it adds it to the
declaration language, not the card language — the same kind of step as
`a_list_of` in Stage 1B and `names_at_least` in Stage 1C. It should not be
started until the shape is analysed separately, because "a map of names to X"
is a genuinely new thing to be able to say and there is more than one way to say
it.


## 11. So what is really left?

Three things, and none of them is a card the Constructor cannot represent.

1. **Six card kinds are missing from one screen** because a six-entry list was
   written by hand next to a twelve-entry list that was already published.
2. **`promise` has one required answer nothing describes** — six closed
   operations enforced in `state/promises.py` and declared nowhere, in a shape
   the declaration language cannot yet spell.
3. **693 cards are held back by a nudge that is right for new cards and wrong
   for old ones**, and that is a decision rather than a defect.

Everything else measured in this pass is already done.


## Files studied

- `src/fsme/cards/types.py` — `CardType`, `TYPE_WORDS`, `PRINTED_NUMBERS`
- `src/fsme/runtime/vocabulary.py` — `_card_field`, `_printed_on`,
  `_EVERY_PRINTED_NUMBER`, `_node_shapes`
- `src/fsme/lab/desk/capabilities.py` — `CARD_KINDS`, `catalogue`, `_nodes`,
  `_fields`, `ABOUT_NODES`, `STRUCTURE_NODES`
- `src/fsme/lab/desk/author.py` — `check_card`, `save_card`, `read_card`,
  `build_card`
- `src/fsme/lab/desk/static/author.html` — `chooseKind`, `pickKind`, `cardHtml`,
  `putable`, `finishable`, `drawable`, `structureHtml`, `catalogues`
- `src/fsme/state/promises.py` — `CHANGES`, `Promise.apply_to`
- `src/fsme/effects/builtin/` — `modify_event`, `event_value`, `watch_for`
- `tests/test_card_rehydration.py` — `round_trip`, for the means-the-same bar
- `content/` — all 1045 card definitions

## Existing extension points, used by nothing new here

- `ParamShape` on the plain-data side of `content/vocabulary.py` — where
  `a_list_of`, `names_at_least` and `shaped_like` already live, and where a map
  shape would go.
- `EffectRegistry.register(..., holds=, holding=)` — how an effect already says
  its own nested shape.
- `catalogue()` — publishes whatever the vocabulary publishes; the page's
  `catalogues()` finds any section whose entries have `fields`, so a shape the
  language gains draws itself.
- `TYPE_WORDS` — already the single description of all twelve kinds.

## Counts

- 1045 cards; 352 with rules, **352 checker-clean**; 693 without rules, **0
  saveable**.
- 136 cards of a kind the opening screen does not offer, 38 of them with rules;
  all 136 open and save.
- 164 language constructs measured, **164 held, 0 refused, 0 unstable, 0
  changed meaning**.
- 12 card kinds declared, 12 offered in the editor, 6 on the opening screen.
- 2 effects the guided walk cannot finish, for two different reasons.
- 6 promise operations enforced; 3 declared; 3 declared nowhere.
- 1 card key not described by the shape (`schema_version`, written by the
  builder).

## Representation gaps versus architectural gaps

**Representation gaps: none.** The reader, the writer and author state carry
every construct the engine declares, and carry it without changing what it
means. This was the thing worth checking, and it came back clean.

**Architectural gaps: none.** Nothing measured requires the card language, the
engine, or the runtime to gain anything.

**What is left is publication and one decision:** one hand-written list to
delete (§4), one enforced set and one shape to declare (§5), one control the
walk does not have (§6), and one deliberate refusal to revisit (§9).

## Recommended next stage

`CARD_KINDS` — analysis first, as always. It is a **B**: the correct list is
already computed, already published on the card's `type` field, and already in
the same response the page reads its six from. Removing the copy is the same
move as removing the hardcoded `values_equal` in Stage 1C, and it is the only
item on the list where the alternative to a fix is a list that will drift again
the next time `CardType` grows.
