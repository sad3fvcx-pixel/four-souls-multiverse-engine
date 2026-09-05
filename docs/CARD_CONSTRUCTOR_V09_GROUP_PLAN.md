# Card Constructor v0.9 — several names for one answer

`decoy` swaps this card with an item somebody else controls. Two things are
chosen, and one answer names both of them:

```json
{"group": {"of": ["mine", "theirs"], "as": "decoy_pair"}}
```

The reader refuses it. The question this stage was given is whether that is a
concept the model already has and does not publish, or a new element of the
language — and it is asked together with `values_equal.of`, which writes the
same shape at the other end of the card.

Analysis only. Nothing was changed. Everything below was measured against the
tree at `e165294`, with the desk running.

**The short answer: the concept exists everywhere in the tree except in the
one place that describes the language.** It is a missing *statement*, not a
missing idea — and its absence is already causing a silent defect in a card
that Stage 1A made editable.

---

## 1. Who already knows about it

| | knows | how it knows |
|---|---|---|
| runtime | **yes**, in three places | `target_resolver._group`, `_most_common`, `condition_evaluator._values_equal` |
| card language | **yes** | five shipped cards write it |
| checker | **yes** | accepts every one of them |
| builder | **yes** | writes `decoy` byte for byte, checker clean |
| reader | **no** | refuses `group`, and mistakes `values_equal` for a plain value |
| published model | **no** | nothing it can say means this |
| page | **no** | draws one picker either way |

The runtime knows it the same way twice, in the identical four lines:

```python
names = params.get("of", ())

if isinstance(names, str):
    names = [names]
```

That idiom appears **exactly twice in the whole engine** —
`target_resolver.py:1541` and `condition_evaluator.py:846` — and those are the
two answers this stage is about. `most_common.of` inherits it by calling
`_group`, so three published parameters accept it and content uses two.

---

## 2. The two, side by side

| | `group.of` | `values_equal.of` |
|---|---|---|
| what it names | things the ability chose | values an earlier step stored |
| `refers_to` | `any` | `values` |
| `role` | `names` | `names` |
| `kind` | only a game can judge | only a game can judge |
| `a_list_of` | — | — |
| published `many` | false | false |
| `written_as` | *the name of something the ability chose* | *the name of a value an earlier step stored* |
| `shown` | `group` — a target picker | `form` — a select of stored names |
| shipped uses | 4 cards | 1 card |
| the reader | **refuses** | **lets through as a plain value** |

Both `written_as` sentences are singular. That is the whole of what is wrong
with them: each says *the name of*, and each answer holds two.

The namespaces are already distinguished, and deliberately. From
`condition_evaluator.py`:

> `of` … the one place `of` means the other thing. Everywhere else `of` names
> a group of objects an ability chose. Here it names what an ability
> *stored* … The two namespaces never meet, and a checker that read `of` as
> one thing would be wrong about the other.

So `refers_to` carries the namespace and carries it correctly. What nothing
carries is **how many**. Those are two separate axes, and only one of them is
published.

---

## 3. The five cards

| card | writes | refused for |
|---|---|---|
| `decoy` | `group.of: ["mine", "theirs"]` | **the group itself** |
| `finger` | `group.of: ["mine", "theirs"]` | a step choosing its own target |
| `pestilence` | `group.of: ["first_point", "second_point"]` | a step choosing its own target |
| `incubus` | `group.of: ["mine_card", "their_card"]` | a step choosing its own target |
| `the_bloat` | `values_equal.of: ["first_die", "second_die"]` | **not refused — it opens** |

One card is gated by this alone. Three more hold it behind the step-scope
class, so they need this *and* that. And the fifth is the interesting one.

---

## 4. What it already costs — measured, not predicted

`the_bloat` became editable in Stage 1A. Its branch compares two stored
rolls. The page draws `values_equal.of` from `shown: form`, and what it draws
is one select:

```html
<label>The name an earlier step stored the value under?</label>
<select onchange="setField('p.fields','of',this.value,false)">
  <option value="">— leave it out —</option>
  <option>dice</option><option>first_die</option><option>second_die</option>
</select>
```

It knows the namespace — those are exactly the names this ability stores —
and it offers **one**. The card's answer is a list, so no option is selected:
an author opening `the_bloat` is shown *"— leave it out —"* where the card
says "if the two rolls match".

Touching that select writes one name back. Measured:

```
untouched   {"values_equal": {"of": ["first_die", "second_die"]}}   checker: clean
one chosen  {"values_equal": {"of": "first_die"}}                   checker: clean
```

Both pass the checker, because one name is a legal value for a parameter that
takes one or several. But `_values_equal` returns false when it is given
fewer than two names — so the second card is `the_bloat` with a branch that
can never run, and nothing anywhere says so.

That is the practical shape of the missing statement: **not a card that
cannot be opened, but a card that can be quietly turned into a different
card.** It is reachable today.

`group` does not have this failure because the reader refuses the card
outright. Refusal is the safer of the two behaviours, which is worth noticing:
the answer that is handled *less* is handled *better*.

---

## 5. Why nothing published can say it

Three fields look like candidates. None of them means this, and each is
already load-bearing for something else.

**`a_list_of`** — its own words: *"This parameter holds a list of nodes of one
of the kinds in `NODES`… This says the inside **is** described, and by what."*
Nodes, not names. The builder branches on it to construct nodes
(`_written_inside` → `_written_body` → `_written_one`), so giving it a second
meaning would make one field mean two things at the exact place a branch is
taken on it. Stage 1B has just finished relying on the first meaning.

**`many`** — published, but derived, not declared:
`parameter.kind == A_LIST and bool(parameter.values)`. It means a multi-select
of literal values from a closed set. Neither of these answers has a closed
set; both name things the card invents.

**`refers_to`** — *"this parameter does not carry a value at all — it carries
**the name of** a group the ability bound earlier, or of a value it stored."*
Singular by construction, and rightly: it answers *which namespace*, and the
engine draws exactly one distinction there.

Measured over every published effect, node, target and condition shape:
**38 parameters refer to something; 0 of them combine that with any statement
of plurality.** There is nothing to reuse, because there is nothing there.

---

## 6. So: existing concept, or new element?

**Existing concept, unpublished.** Stated precisely, because the distinction
matters for what happens next:

- It is **not** a new idea. The runtime implements it, the language expresses
  it, five shipped cards use it, and the checker and builder both handle it.
  Nothing about how a card behaves would change.
- It **is** a new field in the model's own vocabulary. `ParamShape` cannot
  currently say "several of what this refers to", and that sentence has to
  exist somewhere before a reader or a page can act on it.

This is the same shape of finding as Stage 1B, one level further in. There,
the registry could not say what a list holds, though `NODES` had named the
answer. Here, `ParamShape` cannot say how many names an answer carries,
though `refers_to` has named the namespace.

The difference from Stage 1A is real and worth keeping: `store` needed
publishing an existing field on more shapes. This needs a field that does not
exist. It is small, and it is still new.

---

## 7. What the statement has to be able to say

Four things, all of them measured requirements rather than guesses:

1. **How many.** One name, or several. Both `group.of` and `most_common.of`
   are meaningful with one; `values_equal.of` is legal with one and always
   false, which the *effect* knows and the model need not.
2. **Of what.** Already answered by `refers_to`, and must stay answered by it
   — the two namespaces must not merge.
3. **Where it is said.** Beside the guard, as in Stage 1B. For `group` and
   `most_common` that is `target_resolver`, where the shapes are declared;
   for `values_equal` it is `condition_evaluator.NAMED_VALUES`. Both already
   construct their `ParamShape` inline, so neither needs a new mechanism —
   only the field.
4. **What it must not say.** It is not a list of nodes, and it is not a
   multi-select of literals. Whatever it is called, it must not be spellable
   as either, or the next reader of the model will merge them.

Three consumers would then have work, and each has a precedent to follow:

- the **reader**, which refuses a group today and mistakes a comparison for a
  value — it already holds exactly one binding per answer (`_as_chosen`);
- the **writer**, which writes exactly one name per answer (`_given`);
- the **page**, which draws exactly one picker per answer (`groupHtml`, and
  the ordinary form select).

The builder needs nothing: it already writes `decoy` correctly when the names
arrive as a plain field.

---

## 8. What it would free

| | |
|---|---|
| `decoy` | refused → editable, on this alone |
| `the_bloat` | editable → **correctly** editable; the live defect in §4 closes |
| `finger`, `pestilence`, `incubus` | still refused, behind step-local bindings |
| everything else | unchanged |

One card opens. One card stops being quietly breakable. That second number is
the one that matters, and it is the reason this is worth doing before the
step-scope stage rather than after — the defect it closes is reachable now.

---

## 9. What this stage does not decide

It does not propose a spelling. Naming the field, deciding whether it carries
a count or only a plurality, and choosing where the reader holds several
bindings where it holds one, are the design stage — and a name chosen to fit
`group` alone would be a name that fits `values_equal` badly, which is the
mistake this analysis was asked to avoid.

It does not touch `promise`: the event-payload question is separate and stays
separate. It does not touch step-local bindings, which remain 17 of the 21
refusals and the largest block. And it changes nothing about how any card
plays: every one of the five behaves today exactly as it will afterwards.
