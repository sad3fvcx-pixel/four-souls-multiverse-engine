# Author Experience: analysis and design

Stage 1 — no code. The question is not "does the UI work" but:

> A Four Souls player who has never programmed downloads one `.exe`. Nobody
> explains anything. What does he do to make a card?

Everything below was measured against the engine and the existing interface.

---

## 1. The journey as it is today

Walked step by step, as somebody with only the executable.

**He double-clicks it.** This part already works and is better than it looks:
launching with no arguments runs `desk --open`, which starts a local server and
opens a browser at it. He sees a page.

The page says:

```
FSME
  Play a game        seed / players / who plays        [Play]
  Run a study        games / players / cores           [Study]
  Test a card        games / players / cores           [Test]
  Open a report                                        [Open]
```

**And here it stops, permanently.** There is no "make a card" and no path that
leads to one. Every remaining problem is downstream of this one, but each is
real on its own, so here they all are:

| # | where he stops | why |
|---|---|---|
| 1 | the first screen | four options, all things the *engine* does; none is the thing he came for |
| 2 | "Test a card" — the closest guess | a list of 1045 cards that already exist. His is not among them and cannot be added |
| 3 | looking for where to create one | the desk has no write path at all: `/api/cards` reads, nothing writes |
| 4 | finding the documentation | `GETTING_STARTED.md` is in the repository, which he does not have. He has an `.exe` |
| 5 | if he found it anyway | it tells him to make a folder with a `manifest.json`. A frozen build reads its cards from **inside itself** (`sys._MEIPASS`), a temporary directory wiped when the program closes. There is nowhere for his set to live |
| 6 | writing the card | JSON, by hand, in Notepad. Braces, quotes, trailing commas |
| 7 | choosing what it does | the vocabulary is in `REFERENCE.md`, also not in the `.exe` |
| 8 | reading an error | `abilities[0].effects[0].amount` names a path through a file he cannot see |
| 9 | testing it | "Test a card" plays 200 games with and without it and reports statistics. One new card in a 1045-card deck usually never gets dealt — measured: a card tested this way came back *"never reached the table in 40 games"*. He wanted "does my card work", and this answers a different question |
| 10 | saving | undefined |

Ten places to ask "what now?", the first of them immediate.

## 2. What is already right, and must be kept

This is the larger half, and the design should change none of it.

- **The double-click already opens a browser.** No terminal, no flags.
- **The engine already knows the vocabulary**, and — the decisive fact for
  everything below — **63 of 63 effects carry a plain-language description in
  their own registration**: `gain_coins` → "Give a player cents",
  `add_modifier` → "Give a player a bonus that lasts beyond its card". A card
  builder does not need a table of its own. It needs to read this one.
- **The shapes describe every parameter**: kind, domain, floor, whether it is
  required. That is a form specification already — a `WHOLE` with `least=0` is
  a number box that starts at zero, a parameter with `values` is a dropdown,
  a `FLAG` is a checkbox.
- **`needs_target`, `primary` and `yields`** say whether an effect needs
  something to act on, which parameter a shorthand fills, and what a target
  hands back.
- **Validation is thorough and its messages are good** — the set, the file, the
  card, the path, and the nearest spelling.
- **The Workbench** already runs long jobs off the request thread and reports
  progress. Testing a card is plumbing that exists.

## 3. What the first journey should be

Six steps, and the author should be able to guess every one.

```
open FSME  →  "Make a card"  →  pick a kind  →  say what it does
           →  it checks itself as you go  →  "Try it"  →  it is saved
```

No file, no folder, no JSON, no command. The set is created for him the first
time he saves, in a place that survives the program closing.

## 4. The shape of the interface

Replace the four engine functions on the home screen with three things a
person came to do. The engine functions do not disappear; they move behind
the task that needs them.

```
FSME — cards for Four Souls

  ▸ Make a card            start something new
  ▸ My cards               12 cards in 2 sets            [open]
  ▸ Watch a game           see the engine play, with your cards in it
                                                       Advanced ▾
```

`Advanced` unfolds to today's page unchanged: Play a game, Run a study, Test a
card, Open a report, and a JSON view of whatever is on screen.

### The screens

| screen | what it is for | what it shows |
|---|---|---|
| **Home** | choosing a task | the three above |
| **My cards** | everything he has made | sets and their cards; a card shows green (works), amber (unfinished), red (has a problem) |
| **New card** | choosing a kind | six tiles with a sentence each — Loot, Treasure, Monster, Character, Room, Curse. Ordered by how common they are in real content: treasure and monster and loot first |
| **The card** | name, art-less card face, printed text, numbers the kind needs | a monster asks for HP, attack and difficulty; a loot card asks for none of them. The kind decides the form |
| **What it does** | the mechanic | §5 — the heart of the design |
| **Check** | problems, in his words | §6 |
| **Try it** | seeing it work | §7 |

### One card face, always visible

The right half of the editor is the card as it would be printed: name, type,
numbers, and the rules text **written by the engine from what he has built** —
not typed by him. If the sentence the engine writes back does not match what he
meant, he has built the wrong thing, and he finds out while building it rather
than after a game.

## 5. How he describes a mechanic

The one screen that decides whether this works. Three questions, in order,
each a sentence he completes.

> **When does this happen?**
> ( ) When it is played
> ( ) When somebody activates it   ↷
> ( ) When a monster dies
> ( ) At the start of a turn
> …more

> **Does anything have to be true?**  *(optional — most cards skip it)*
> ( ) Only if …

> **What happens?**
> [ Give a player cents ▾ ]  how many [ 3 ]  to [ whoever played it ▾ ]
> ＋ and then …

Every list on that screen is **generated from the engine**:

| the list of | comes from | measured |
|---|---|---|
| triggers | `EventType`, grouped by the comments already in it | 8 triggers cover most cards; the rest behind "more" |
| effects | `EffectRegistry`, labelled with `EffectSpec.description` | **63 of 63 already have one** |
| an effect's fields | its `ParamShape`s — kind picks the widget, `values` fills a dropdown, `least` sets the minimum | 74 parameters |
| the "to" list | `TargetResolver`, filtered by `needs_target` and `yields` | 46 targets |
| conditions | `ConditionEvaluator` | 44 |

Ordered by how often real cards use each — measured across the 352 implemented
cards, **15 effects cover 75% of everything they do**, so the common list is
short and the long tail is one click away.

"and then …" adds another effect. That is how a complicated card is built:
several simple things in order, which is what the DSL already is.

### The branch, without the word "branch"

`if` is the single most used construct in real cards — 108 uses, more than any
effect. It appears as a choice on the effect list like any other:

> [ Roll a die ▾ ]
> [ Depending on the roll ▾ ]
>   on **1–3** → [ Lose cents ▾ ] how many [ 1 ]
>   on **4–6** → [ Give a player cents ▾ ] how many [ 4 ]

Same for "the player may choose to…" (`may`, 33 uses) and "choose one of…"
(`choose`, 22).

### Naming something, without the word "alias"

A card that chooses a player and then does something to them needs a name for
that player. The engine calls it `as`; the author never types it. When he adds
a target, the form offers it back by description in every later "to" list —
*"the player chosen above"* — and the UI writes the `as` and the reference.
The reference layer already refuses a name used wrongly, so this cannot
produce a card the engine will reject.

## 6. Checking, in his words

Validation runs on every change, and its findings are shown **on the field
that caused them**, not as a path:

| the engine says | he sees |
|---|---|
| `abilities[0].effects[0].amount: 'gain_coins' takes a whole number of at least 0 here, and the card gives text ('lots')` | on the *how many* box: **"This needs a number."** |
| `unknown effect 'gain_coinz' — did you mean 'gain_coins'?` | cannot happen — he picked from a list |
| `abilities[0].scope: 'contoller' is not one of…` | cannot happen — he picked from a list |
| `'nobody' is not a group this ability binds` | cannot happen — the list only offers what exists |

Most of the validation layer becomes **unreachable**, which is the point: a
form that offers only valid choices cannot produce most of the mistakes. What
remains reachable is the numbers he types and the combinations he assembles,
and those keep their messages, rephrased and attached to a field.

The full engine message stays available under "details" — for us, when he
reports something.

## 7. Trying it

"Test a card" today is a *statistical* tool: 200 games with the card and 200
without, then a verdict about measurable difference. That is a real question
and not his first one. His first one is **"does it do what I meant?"**

So *Try it* does what the tutorial already tells an author to do by hand — a
small world where the card is guaranteed to be dealt — and shows the moment it
happened:

```
Turn 4 — Alice played Lucky Penny
         Alice gained 3¢  (2¢ → 5¢)
```

That is a journal, which the engine already produces and already renders.

"Does it change the game?" stays where it is, under Advanced, for when he
wants it.

## 8. What must be added to the engine

Five things. **None is a new table** — each is a field beside a registration
that already exists, in the pattern effects already follow.

| # | what | size | why |
|---|---|---|---|
| 1 | `description` on condition and target registrations | 90 lines | a dropdown of `target_player_or_monster` with no words beside it is not usable. Effects already have this; conditions and targets do not |
| 2 | `description` on `ParamShape` | 74 | a form needs a label. "amount" is not one; "how many cents" is |
| 3 | a sentence per trigger | 66 | `EventType` has grouping comments, no per-member text |
| 4 | **a writable content directory** | small, and blocking | a frozen build reads from inside itself and loses everything on exit. The author's sets need a real home — the platform's documents directory — found automatically and never typed |
| 5 | a write path in the desk | new endpoints | today it can only read |

Items 1–3 are the same work as `EffectSpec.description`, done for the other
three vocabularies, and they improve `REFERENCE.md` at the same time — it is
generated, so it gains the text for free.

**Item 4 is the one that blocks everything else**, and it is worth saying
plainly: until an author's set has somewhere to live, no interface can help
him.

## 9. What stays advanced

Not hidden — one click away, and everything already built stays reachable.

- The JSON of whatever is on screen, editable, with the same validation.
- Statics, replacements, `watch_for`, `promise`, costs, zones, scopes.
- Scenarios, studies, reports, journals, replay.
- The four things the desk does today, unchanged.

The first card does not need any of it. A card with statics or a replacement
is a second card, not a first one.

## 10. What is kept

- The whole `Workbench` — jobs, progress, cancellation.
- The game server and its board page.
- Every validation message, as the source of what the form says.
- `docs/REFERENCE.md` and its generator, which gains from item 8.
- The card format. **Unchanged.** The UI writes exactly what an author would
  have typed, so a set made in the UI and one made in an editor are the same
  thing, and `author-kit` examples open in it.

## 11. When to call the focus group back

Not "the UI works". These, in order:

1. Somebody who has never seen FSME, given only the executable, makes a loot
   card that gains cents — **without asking anything and without opening any
   file**.
2. He never sees the word JSON, a file path, or a command.
3. He makes a card with a die roll and a branch — the commonest real shape.
4. Every error he meets names a thing on his screen, not a path into a file.
5. He closes the program, reopens it, and his cards are still there.
6. A card he made in the UI loads through the ordinary pipeline with no
   special case, and one from `author-kit` opens in the UI.
7. The three timings hold: something on screen he understands in under a
   minute, a first card in under ten, and seeing it played in under fifteen.

Item 1 is the whole test. The others are how it fails if it fails.

---

## Recommendation

The engine is ready and the interface is pointed at the wrong audience: it
shows what FSME *can do* rather than what a person *came to do*. Nothing in
the engine needs rebuilding, and the data a card builder needs is almost
entirely there already — the descriptions on 63 effects are the proof.

The order to build in:

1. **A writable home for an author's sets** (§8.4). Blocking; nothing else
   matters until a set can be saved.
2. **Descriptions for conditions, targets, parameters and triggers** (§8.1–3).
   Beside the registrations, no new table.
3. **Write endpoints on the desk** (§8.5).
4. **The three-task home screen, the card editor and the mechanic form**
   (§4–5), driven entirely from the registries.
5. **"Try it"** (§7), on the Workbench that already exists.
6. **Advanced mode**, which is today's page moved rather than rewritten.

Steps 1–3 are engine work with no interface at all, and they are the ones with
the risk in them. Steps 4–6 are the interface, and by then the interface is
mostly a rendering of data the engine already hands over.
