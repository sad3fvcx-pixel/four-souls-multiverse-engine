# Card Constructor v0.9 — the cards still turned away

The binding stages closed the class of refusals that was about names. This asks
what is left, and answers one question about each: **does the tree already know
enough to support this card, or would supporting it mean deciding something
nobody has decided?**

Analysis only. Nothing was changed. Every number below was measured against
the working tree at `26a6ce4`, with the desk running and the browser walking
the same rule the editor walks.

---

## 1. Where the constructor stands

```
cards with rules   352
  readable         331
    editable       325
    view only        6
  unreadable        21
```

Unchanged from the baseline the stage opened with, as it should be — the
binding stages fixed what a card *kept*, not which cards were let in.

---

## 2. The 21, by the first thing that stopped them

The reader refuses at the first obstacle, so each card here is named by one
reason even where it holds more. Five reasons cover all twenty-one:

| | first blocker | reader |
|---:|---|---|
| 16 | picks something out for itself | `author.py:1574` |
| 2 | works `count` out from something the ability chose | `author.py:1813` |
| 1 | points at something the ability chose | `author.py:1715` |
| 1 | is built out of several things the ability chose | `author.py:1876` |
| 1 | keeps its result under a name for a later step | `author.py:1568` |

Every one of those five is a refusal the reader raises **on purpose**, with a
sentence saying why. None of them is a crash, an unknown key, or an effect the
engine cannot describe.

---

## 3. The table

`I` — implementation gap: the metadata already says everything needed.
`D` — declaration gap: the engine knows the fact; nothing publishes it.
`C` — missing concept: nobody declares it, anywhere.

| card | cat | first blocker | existing metadata | likely fix location |
|---|---|---|---|---|
| `dingle` | I | `add_counter` picks for itself | `target_monster`, named | author state: a step-scoped binding |
| `ultra_greed` | I | `add_counter` picks for itself | `target_player`, named | author state |
| `rainbow_tapeworm` | I | `copy_card` picks for itself | `target_loot`, named | author state |
| `mulliboom` | I | `deal_damage` picks for itself | `target_player`, named | author state |
| `pestilence` (alt) | I | `deal_damage` picks for itself | `target_player_or_monster`, named | author state |
| `brimstone` | I | `deal_damage` picks for itself | `target_player_or_monster`, named | author state |
| `epic_fetus` | I | `deal_damage` picks for itself | `target_player_or_monster`, named | author state |
| `guppy_s_paw` | I | `destroy_treasure` picks for itself | `target_treasure`, named | author state |
| `pestilence` (base) | I | `divide_damage` picks for itself | `target_player`, named | author state |
| `the_lamb` | I | `lose_soul` picks for itself | `target_player`, named | author state |
| `the_habit` | I | `recharge` picks for itself | `target_treasure`, named | author state |
| `the_lost` | I | `recharge` picks for itself | `target_treasure`, named | author state |
| `g_fuel` | I | `recharge` picks for itself | `target_treasure`, named | author state |
| `incubus` | I | `reveal_hand` picks for itself | `target_player`, named | author state |
| `finger` | I | `swap_cards` picks for itself | `target_treasure` ×2, named | author state |
| `dead_bird` | I | `take_card` picks for itself | `target_loot`, named | author state |
| `famine` | I | `discard_loot` works `count` out of `loser` | `worked_out.of` — `refers_to='any'`, `role='names'` | reader `_refuse_a_working` |
| `viii_justice` | I | `draw_loot` works `count` out of `rival` | `worked_out.of`, `.minus` — both declared | reader `_refuse_a_working` |
| `the_d4` | I | `for_each` points at `rerolled_player` | `for_each` is a published node shape | reader `_read_inside` |
| `decoy` | D | `group` is built out of `mine`, `theirs` | `group.of` says `refers_to='any'` but **not** what the list holds | `runtime/vocabulary.py` — `a_list_of` |
| `the_bloat` | D | `roll_dice` keeps its result under a name | `roll_dice.stores = 'dice'` is published; a step's own `store` answer is not | `runtime/vocabulary.py` — declare `store` |

And the six that open but cannot be edited:

| card | cat | blocker | existing metadata | likely fix location |
|---|---|---|---|---|
| `crystal_ball` | D | `watch_for` | `effects` is `'a list'` with `a_list_of=''`; it holds ordinary steps | `runtime/vocabulary.py` |
| `host_hat` | D+I | `watch_for` | same, and its inner step picks for itself | `runtime/vocabulary.py`, then author state |
| `compost` | C | `promise` | `changes` is `'a set of named values'` — nothing more | see §6 |
| `mom_s_bra` | C | `promise` | same | see §6 |
| `two_of_clubs` | C | `promise` | same | see §6 |
| `polycephalus` | C | `promise` | same | see §6 |

**19 I · 3 D · 4 C · 1 card in two categories at once.**

---

## 4. The four checks

### A. `store`

Of the 63 published effect shapes, **none** declares a `store` answer. Of the
14 published node shapes, **seven** do — every control node: `sequence`, `if`,
`repeat`, `for_each`, `stop`, `may`, `choose`. The interpreter accepts `store`
on *any* step: it is in `_MODIFIER_KEYS`, beside `target`, `as`, `optional`,
`description`, `prompt`.

So the engine takes the answer everywhere and declares it in half the places.
Two more things are already published and point the same way:

- `EffectShape.stores` — `roll_dice` publishes `'dice'`, `reroll` likewise, and
  `capabilities.py:291` sends it to the page. The engine already says *that*
  these effects produce a value and what it is called by default.
- `worked_out.from` — `refers_to='values'`, written as *"the name of a value an
  earlier step stored"*. **Reading** a stored value is fully declared.

Writing one is the half that is missing. This is the same shape of finding as
the replacement pairing: a fact enforced in `runtime/interpreter.py` and
declared beside only some of the things it governs. One card depends on it.

### B. Target selection — the 16

These sixteen are the largest class and the one worth being precise about.

| | |
|---|---|
| steps carrying their own `targets` | 20 |
| …with one spec | 17 |
| …with two | 3 |
| target specs in total | 23 |
| specs that are a **published standing target** | **23 of 23** |
| specs that are **named** (`as`) | **23 of 23** |
| cards where the step binding is the only one | 12 |
| cards that also bind at ability level | 4 |

By spec: `target_treasure` 9, `target_player` 5, `target_player_or_monster` 3,
`target_loot` 3, `target_monster` 2, `target_character` 1. Nothing exotic.

`incubus`, inside one arm of a `choose`:

```json
{"effect": "reveal_hand",
 "targets": [{"target_player": {"exclude_controller": true, "as": "shown"}}],
 "target": "shown"}
```

That is structurally what an ability does, one level down. The reader's own
sentence says why it refuses:

> Folding that up to the ability would let a later step reuse the choice, and
> two separate choices of the same thing become one.

Which is true, and is the same hazard the binding-scope analysis measured: four
cards already reuse one word across sibling branches. The refusal is not about
missing metadata. It is that **author state has one place to hold bindings —
the ability — and these cards need one per step.**

That makes this an implementation gap of a particular size: not a reader patch,
a shape change in author state, with the writer and the page following it.

### C. Advanced answers

Exactly six cards open but do not edit, and they split two–four:

`watch_for` — `crystal_ball`, `host_hat`. Its `effects` answer is declared
`kind='a list'` with `a_list_of=''`. It holds ordinary steps; ten answers
elsewhere already declare `a_list_of='step'`, and four declare
`a_list_of='condition'`, which is what its `conditions` answer holds. Nothing
is missing but the sentence. `crystal_ball`'s inner step is `{"draw_loot": 3}`
and would be editable the moment that sentence exists; `host_hat`'s inner step
carries its own `targets` and would then land in class B.

`promise` — `compost`, `mom_s_bra`, `two_of_clubs`, `polycephalus`. Its `event`
answer is fully published (66 values). Its `changes` answer is not published at
all. What the four cards actually write:

```
compost        {"source": {"value": "discard"}}
mom_s_bra      {"amount": {"cap": 1}}
two_of_clubs   {"count":  {"factor": 2}}
polycephalus   {"value":  {"flip": 7}}
```

A map from **a field the event carries** to **one way of changing it**.

`shown: advanced` means "the effect's own nested data, shown as what it is" —
so the page shows these honestly and stops, which is correct behaviour for an
answer nothing describes.

### D. Replacement leftovers

**None.** Zero of the 21 refusals and zero of the 6 view-only cards blame a
replacing effect. That class closed completely when `ParamShape.allows` was
published, and nothing is left over from it.

---

## 5. Validating the count

```
21 unreadable  =  19 implementation  +  2 declaration
 6 view only   =   2 declaration     +  4 concept
```

`host_hat` is counted once, under declaration, though it needs both — noted so
the arithmetic is not read as a promise that one change frees it.

Two numbers that should stay in tests, because they are different and both
true: **21** cards are refused; **five** distinct reasons refuse them. The
sixteen-card class is one reason, not sixteen problems.

---

## 6. The four questions, answered

**1. What are the final 21?** Sixteen cards whose steps choose their own
target, two that count from a chosen player, one whose `for_each` walks a
chosen player's items, one built from a `group` of two chosen things, and one
that names a die roll for a later step. §3 lists them.

**2. Which are implementation gaps?** Nineteen. For all nineteen the metadata
is already complete and already published — the standing targets are declared
and named, `worked_out.of` and `.minus` are declared as naming something the
ability chose, `for_each` is a published node shape. Nothing has to be decided
to support them; something has to be built. The nineteen are not equal in cost:
the sixteen need a step-scoped binding in author state, the other three are
reader work on top of names the binding stages now preserve.

**3. Which require new language concepts?** Four — the `promise` cards. And
this needs stating carefully, because it is half true. `state/promises.py`
already declares the six ways a promised change can work, each with a sentence:

```python
VALUE = "value"    # replace what the event carries outright
DELTA = "delta"    # add to a number the event carries
FACTOR = "factor"  # multiply — "they loot double that number"
CAP = "cap"        # lower to at most this — "reduced to 1"
FLOOR = "floor"    # raise to at least this
FLIP = "flip"      # read from the other side
CHANGES = (VALUE, DELTA, FACTOR, CAP, FLOOR, FLIP)
```

That half is a publication gap of the familiar kind: enforced in `state/`,
declared nowhere `content/vocabulary.py` can carry it. The other half is a real
question nobody has answered — **what fields does an event carry?** `source`,
`amount`, `count`, `value` are written by these cards and enumerated by nothing.
`promise.when` asks the same question a second time (`polycephalus` writes
`{"attack": true}`), and so does the `event_value` condition. Until an event's
payload is described, offering a box for `changes` would mean asking an author
to type a field name the engine cannot check — which is guessing what the author
meant, spelled as a form.

**4. Which should intentionally remain unsupported?** The four `promise` cards,
until the payload question above is decided on its own merits — as a question
about events, not as a Card Constructor errand. Nothing else on the list
requires guessing. That is the honest count: **of 27 cards not fully editable,
23 are work and 4 are a decision.**

---

## 7. Suggested order, if the stages continue

Smallest first, and each stops on its own:

1. **`watch_for` says what its lists hold.** One line each for `effects` and
   `conditions` in `runtime/vocabulary.py`. Frees `crystal_ball`. Costs
   nothing, and is the cheapest proof that a declaration gap is a declaration
   gap.
2. **`group` says what its list holds.** Same file, same shape of change.
   Frees `decoy`.
3. **A step may keep its result.** Declare `store` where the interpreter
   already accepts it. Frees `the_bloat`.
4. **Worked-out values may name a binding.** Reader only, resting on names the
   binding stages preserve. Frees `famine`, `viii_justice`; `the_d4` is the
   same question inside a control node.
5. **Steps may choose for themselves.** The big one: a binding scope per step
   in author state, then the writer, then the page. Frees sixteen, and
   `host_hat` behind step 1.
6. **Events describe what they carry.** Not a Card Constructor stage. Until it
   happens, `promise` stays view-only and correctly so.

Steps 1–3 are three files and no new ideas. Step 5 is the only one that changes
the shape of author state, and it should get its own analysis before any code —
in particular, whether a step-scoped binding is a new scope or the existing one
narrowed, which the binding-scope analysis raised and did not settle.

---

## 8. What this stage does not claim

352 of 352 is not the goal and is not the measure. Twenty-three of the
twenty-seven remaining cards can be supported without inventing anything, and
that is worth doing in the order above. The other four are refused because the
engine has not said what an event carries — and a card that would need the
author to guess is a card the constructor is right to turn away.
