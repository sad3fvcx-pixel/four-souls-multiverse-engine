# What it is like to write an expansion

The question: **can somebody who has never seen this code write their own set
without opening it?**

Measured rather than guessed. Five example sets were written using only what
is in `docs/`, loaded through the real pipeline, and played in real games;
every name they use was then checked for whether it can be found in the
documentation; and the tutorial's own example was extracted from the markdown
and run verbatim.

**The answer is yes, with five things to fix first.** None of them is large and
none needs an architectural change.

---

## 1. The path an author walks today

| step | what they use | works? |
|---|---|---|
| find out what a set is | `docs/GETTING_STARTED.md` §5 | yes |
| copy a skeleton | — | **nothing to copy** (now `author-kit/templates/`) |
| write a card | `CARD_SCHEMA.md` + the four registries | mostly — see §3 |
| find an effect | the registries | **less than half is there** |
| check it without playing | `fsme cards --content …` | yes, and exits non-zero |
| read the error | the message | yes — names set, file, card, path, and a suggestion |
| see it matter | `fsme test-card` | yes |

The two ends are in good shape. `GETTING_STARTED.md` opens with "no knowledge
of how FSME is built is needed, and nothing here asks you to read source code",
and that promise very nearly holds. The error messages are the strongest part
of the whole experience:

```
[semantic] my_set .../cards/loot.json: my_set-loot-oops: ability 0:
    unknown effect 'gain_coinz' — did you mean 'gain_coins'?
```

## 2. What was built for this stage

`author-kit/` — a template and five worked examples, each one set that can be
copied out on its own:

| example | shows |
|---|---|
| `simple_loot` | one effect, nothing else |
| `simple_treasure` | a static: a number that is simply always on |
| `conditional_card` | `roll_dice`, `if` / `then` / `else`, a condition |
| `choice_card` | `target_player`, and choosing |
| `reference_card` | `as`, `of`, `chooser` — naming what you chose |

Every one is **loaded, validated and played** by `tests/test_author_kit.py`.
Playing matters: a card can pass every check in the pipeline and still do
nothing, which is the exact mistake the examples exist to teach people to
avoid. The test asserts the coins arrive, the bonus applies, one branch runs,
the damage lands on somebody else, and the stolen card moves rather than
appears.

**The proposed structure was changed in one place.** It listed an
`author-kit/REFERENCE.md`. That would be a second copy of `docs/REFERENCE.md`,
and the registries have already shown what happens to a second copy — they
drifted until 40 of 70 effects were missing. The kit links instead, and a test
asserts the file does not exist.

## 3. What still needs the source

Four things, in the order an author meets them.

### 3.1 Six mistakes still load in silence

Decided in `docs/CARD_LANGUAGE_DECISIONS.md` and **not yet implemented**. Each
loads cleanly today and then quietly does something other than what was
written:

| written | what happens |
|---|---|
| `"scope": "contoller"` on an ability | loads; the ability fires under different rules |
| `"scope": "contoller"` on a static | loads; falls through to "controller" |
| `"stat": "atack"` | loads; the static contributes nothing |
| `"stat": "max_hp"` with `"scope": "all_monsters"` | loads; nothing reads it |
| an unknown key on an ability | loads; ignored |
| an unknown key on a static | loads; ignored |

This is the largest remaining obstacle and the cheapest to remove: both
domains and both key sets already exist in the engine, and both dry-runs came
back clean against all 1045 cards.

### 3.2 More than half the vocabulary is not explained

The four registries describe what a name is *for*, and between them they cover:

| | engine has | has a section |
|---|---|---|
| effects | 70 | 31 |
| conditions | 44 | 29 |
| targets | 46 | 28 |
| triggers | 66 | 51 |

`docs/REFERENCE.md` closes the *discovery* half — it is generated, lists
everything, and says what each takes — and it now reports its own shortfall in
each section. But an author who finds `take_card` in the reference still has
nowhere to read what it means. One of the five examples uses exactly that
effect, and it has no registry section.

### 3.3 The documentation taught a field that does nothing

`GETTING_STARTED.md` §5 put the card's printed words in a top-level `"text"`.
No shipped card does — all 1014 that have text use `metadata.text`, which is
where `api/view.py` and the desk read it from. A top-level `text` is not an
error, because unknown fields at the top level of a card are kept on purpose,
so an author following the tutorial got a card whose text never appeared
anywhere and no message about it.

**Fixed in this pass**, along with the missing `schema_version`, and the guide's
example is now extracted from the markdown and loaded by a test so it cannot
drift again.

### 3.4 Fixing one error can reveal another

The engine cannot check what was given to `gain_coinz` until it knows what
`gain_coinz` is, so a misspelled name hides every mistake inside it. That is
correct and unavoidable, but it surprises somebody who expects one run to list
everything. Now stated in the kit's README.

## 4. What does *not* need the source

Worth recording, because it is the larger half.

- **The data/logic boundary holds.** Nothing an author writes is executed.
  `content/` and `cards/` import nothing from the engine.
- **Every parameter the examples use is real**, and every one is described in
  the generated reference with its kind, its domain and its floor.
- **The whole vocabulary is discoverable** from one generated file.
- **Validation covers structure, names, arguments and references.** An author
  who misspells anything the engine knows about gets a message naming the set,
  the file, the card and the path, with the nearest spelling.
- **Checking needs no game.** `fsme cards --content …` validates fully and
  exits 2 on failure, so it works in a script.
- **A set is refused whole or accepted whole.** Half-valid content never
  reaches a game.

## 5. The minimum before a focus group

1. **Implement the two decided rules** (§3.1). Six silent failures become six
   messages. Both dry runs are already clean; the work is small and its shape
   is written down.
2. **Signpost the documentation.** `docs/` holds 41 files, most of them engine
   internals. An author needs five, and nothing says which five. The kit's
   README is one answer; an index in `docs/` would be better.
3. **Say in `GETTING_STARTED.md` that an expansion cannot add behaviour** —
   only combine what exists. Somebody will try, and finding out by failing is
   a poor first lesson.

That is the whole list. Everything else can wait.

## 6. What can wait

- Writing the 89 missing registry sections. The reference makes them
  discoverable; prose makes them *understandable*, and that is a real cost with
  a smaller return than §5.
- A `fsme validate` command. `fsme cards` already does it, exits correctly,
  and says so in its own failure message. A second command for the same
  behaviour is a second thing to document.
- Enforcing the id convention. It is a convention; making it a rule is a
  language change, and the collision it prevents is already caught by name.
- Any editor, any UI, any generator.

## 7. The first external test

What to hand somebody, and what to measure.

**They get:** the repository, `docs/GETTING_STARTED.md`, and `author-kit/`.

**The task:** one loot card that does something on being played, in their own
set, appearing in `fsme cards`.

**Measure four things:**

1. **Time to the first card that loads.** The target is the twenty minutes the
   guide promises.
2. **Every error message they hit, and whether they could act on it alone.**
   The suggestions are the strongest part of the system and the least tested
   on somebody who does not already know the answer.
3. **Every time they open a file under `src/`.** That is the failure the whole
   stage exists to prevent, and each instance names something §3 missed.
4. **Which of the 41 documents they open, and in what order.** If they open
   more than five, the signposting is the problem rather than the content.

Do not help while they work. A question asked out loud is a documentation gap
that would otherwise go unrecorded.
