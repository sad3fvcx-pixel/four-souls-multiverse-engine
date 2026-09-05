# Card Constructor v0.9 — where a name is visible

Seventeen cards are refused because a step chooses something for itself. This
asks whether they can be supported without changing what any card means, and
answers a prior question first: **what is the real scope of a name?**

Analysis only. Nothing was changed. Everything below was measured against the
tree at `bcf7b4a`; no earlier assumption is carried forward.

**The short answer.** The scope model is not ability-level, and it is not
step-local either. It is *arm-scoped, forward-only, inherited inward* — and it
already exists: implemented, enforced, documented, and obeyed by every shipped
card. What is missing is that nothing publishes it, and author state has one
binding container per ability where the rule implies one per arm.

No new concept in the card language is required. One is required in author
state, and it is the shape the existing rule already describes.

---

## 1. The twenty refusals

| | first blocker | cards |
|---:|---|---|
| 17 | a step picks something out for itself | `dingle` `ultra_greed` `rainbow_tapeworm` `mulliboom` `pestilence` `host_hat` `epic_fetus` `brimstone` `guppy_s_paw` `pestilence` `the_lamb` `the_lost` `g_fuel` `the_habit` `incubus` `finger` `dead_bird` |
| 2 | `count` worked out from a binding | `famine` `viii_justice` |
| 1 | `for_each` points at a binding | `the_d4` |

The last three are the same question one layer out: a value or a domain that
names a binding. They are listed apart because they fail at a different
sentence, not because they are a different problem.

---

## 2. What the seventeen actually bind

Twenty-eight bindings across them.

| where it is made | |
|---|---|
| in a step's own list | 24 |
| in the ability's own list | 4 |

| what encloses it | |
|---|---|
| nothing — a step of the ability | 16 |
| inside a `may` | 8 |
| inside a `choose` | 1 |
| inside a `choose` then a `may` | 2 |
| inside an `if` | 1 |

**Every one of the twenty-eight is read back at least once** — twenty-five once,
three twice. Not one is decoration. And every one of them is a published
standing target, named with `as`, structurally identical to what an ability
binds one level up.

---

## 3. The scope question, measured

The instruction was not to assume ability scope is right. It is not.

Over **every** shipped card, counting every place a name is said again:

| | |
|---|---|
| read from the ability's own list | 113 |
| **read by the step that made it** | **26** |
| read by a later step | 1 |
| read sideways, in a sibling arm | **0** |

The single "later step" is `incubus`: a mode binds `shown` in its first step
and reads it in a `may` that is its second step. The read is *inside* the arm
that bound it, one level deeper — forward and inward, not across.

And the case that settles what "arm" has to mean:

| card | name | bound | in how many arms |
|---|---|---|---|
| `the_curse` | `top` | 3× | 3 |
| `the_curse` | `raised` | 3× | 3 |
| `sleight_of_hand` | `ordered` | 3× | 3 |
| `sack_head` | `top` | 3× | 3 |

Four names, each bound three times, each time in a different arm of a
`choose`. Only one arm ever runs, so the card is right. **Any model that puts
these in one namespace merges three choices into one.**

So the model the content actually obeys:

> A name is visible from where it is bound to the end of the arm that bound
> it, and inside everything nested in that arm. Nowhere else.

Not global. Not the ability. Not the step. **The arm.**

---

## 4. This model already exists

It is not something to invent. `cards/references.py` states it:

```python
BRANCHES = ("then", "else", "may", "choose", "modes", "effects")
"""
Keys holding effects that may or may not run.

Their contents share the context at run time, but *whether they ran* is not a
fact about the text. So a name bound inside one is visible inside it and after
it there, and not outside — which is the strictest reading, and the one every
shipped card already obeys.
"""
```

and enforces it in one line — entering a branch copies what is visible, so
nothing bound inside escapes:

```python
elif key in BRANCHES:
    self._walk(value, dict(groups), set(values), f"{path}.{key}")
```

Names accumulate as the walk proceeds, which is the "forward-only" half. The
checker's own error message says the rest out loud: *"a name is visible after
the target that binds it, and only inside the branch that bound it."*

The engine agrees. A step's own `targets` is taken off the node before the
effect is looked at, and resolved like any other — `targets` is in the
checker's `_NOT_A_VALUE` for exactly that reason. **A step may bind. It always
could.**

---

## 5. Where the information is lost

Three ways to write a binding, and shipped content uses all three:

| how it is written | | author state |
|---|---:|---|
| in the ability's own list | 98 | **kept** |
| written where it is used | 57 | kept as a choice, **name discarded** |
| in a step's own list | 24 | **card refused** |
| | **179** | |

So the constructor represents **98 of 179 bindings** faithfully. Of the rest,
57 lose the author's word and 24 stop the card being opened at all. This is
not a seventeen-card problem; it is 45% of every binding in the content.

The path of a name, and where each stage drops it:

| stage | what it does |
|---|---|
| card text | binds anywhere: ability list, step list, or inline |
| `_bound_by` | reads **only** the ability's `targets`; never descends |
| `_read_step` | refuses a step that binds; discards an inline name |
| author state | one binding container, on the ability |
| walk / editor | offers a choice only where author state holds one |
| `_pick_out` | gathers every choice into the ability's one list |
| `_written_part` | writes that list back at ability level |
| checker | applies the real arm rule to the result |
| rebuilt card | correct, and flatter than what was read |

Two places do the losing, and they are the same decision twice: the reader has
one place to look, and the writer has one place to put things.

---

## 6. `chosen_N`, classified

It is **this program's handwriting** — the file says so:

> A target has to be named to be pointed at, so one is made up for a choice
> written where it is used. Such a name is this program's handwriting and not
> anything the card said.

Measured over the readable cards:

| | |
|---|---|
| cards whose rebuild contains an invented name | **163** |
| cards where an invented name **replaces a word the card gave** | **37** |
| names a card gave that survive a round trip | 104 |

So it is two things at once. For a card that never named its choice, it is a
temporary name and harmless. For **37 cards it is lost information** — the
author's word, discarded and replaced. `the_curse` is the plainest: it writes
`top` three times and `raised` three times, and gets back `chosen_1..3` twice
over.

That loss is deliberate and documented, and the reason is exactly the scope
gap:

> The builder gathers every choice into one list for the ability, where a name
> has to mean one thing — and a card may call two choices in two different
> branches by the same word.

Which is true *only because* the writer flattens to ability level. Under the
real arm rule, three arms may each have a `top`, and nothing has to be
renamed. **The invented name is a symptom of the missing scope, not a
separate defect.**

---

## 7. Is the concept missing, or only unpublished?

Asked of each declaration in turn.

| | state |
|---|---|
| `written_as == BY_BINDING` | published, 55 answers — *this name is written for you* |
| `refers_to` | published, 38 answers — which namespace a name comes from |
| `names_at_least` | published, 3 answers — how many names an answer holds |
| `role == defines` | published, 16 answers — this invents a name |
| `store` | published since Stage 1A — a step may name its result |
| `a_list_of == "target"` | published — **but only `ability` declares one** |
| `own_names` | published — true for `ability` and `static` only |
| **where a name is visible** | **published nowhere.** No key in the catalogue mentions scope, visibility, branch or arm |

So:

- **A (unpublished, not missing).** The visibility rule — implemented in
  `references.py`, documented there, obeyed by all content, invisible to the
  model. And a step's ability to bind — accepted by the interpreter, resolved
  by the runtime, declared by no node shape.
- **B (genuinely new).** Nothing in the *card language*. In *author state*,
  one thing: a place to hold bindings other than the ability. That is not a
  new idea about cards — it is the shape the rule in §4 already describes,
  which author state does not yet have.

The honest summary: **no new language concept is required.** The single new
structure is in the editor's own model, and it is derived from a rule that is
already written down.

`own_names` deserves a note. It says a boundary exists and where — but it is
binary and lives only on `ability` and `static`. The real rule needs a
boundary at every arm. `own_names` is the right idea measured at the wrong
granularity, and is the closest thing published to what is wanted.

---

## 8. What must not be done

Making the seventeen "work" by hoisting their bindings to the ability would be
pretending a local name is an ability name. The four cards in §3 prove what
that costs: three arms of `the_curse` each name a deck `top`, and one
namespace turns three choices into one — a card that draws three times from
the loot deck. That is not a hypothetical; it is the defect that produced
`chosen_N` in the first place.

So the order below never widens a name's visibility. It narrows the
constructor's model until it matches the rule the checker already applies.

---

## 9. A possible order, if implementation is approved

Each stage stands alone and each is measurable.

1. **Publish where a node binds.** A node shape says it holds a list of
   targets; today only `ability` does. Say it of the control nodes and of a
   step, read off what the interpreter already accepts. Declaration only —
   nothing changes yet.
2. **Publish the visibility rule.** `BRANCHES` is the fact; it should be read
   rather than restated. This is what lets the page and the reader agree about
   scope without either of them knowing the word `may`.
3. **Reader: gather per arm.** `_bound_by` walks one list; it should
   accumulate forward and copy on entering an arm — the same three lines the
   checker already uses. Nothing about meaning changes; more cards open.
4. **Writer: leave a binding where it was written.** Stop hoisting into the
   ability's list. **This step alone closes the 37 cards in §6**, independently
   of the seventeen, because a name kept in its own arm never needs renaming.
5. **Page: offer a choice at the step.** Once author state holds bindings per
   arm, the editor draws them where they are, and `walkable` follows.
6. **Then the last three fall out.** `famine`, `viii_justice` and `the_d4`
   refuse because a worked-out value or a domain names a binding the reader
   would drop. Once a binding survives where it was made, there is nothing to
   drop.

Steps 1 and 2 are declarations. Step 4 is worth doing for its own sake and
pays for itself before any of the seventeen open. Steps 3 and 5 are the real
work, and step 3 should be measured against the four cards in §3 before
anything else, because they are the ones a wrong model breaks silently.

---

## 10. What this stage does not claim

It proposes no field, no name and no data shape — the scope model had to be
established first, and it now is. It does not touch `promise`, which remains a
question about what an event carries. And it makes no claim that all seventeen
will open: three of them (`incubus`, `finger`, `dead_bird`) bind at two levels
at once and read across a nesting boundary, and whether the reader can follow
that faithfully is the thing step 3 has to prove rather than assume.
