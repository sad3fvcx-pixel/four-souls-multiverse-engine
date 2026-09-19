# The form the metadata describes

The engine has carried a capability metadata layer since 0.4.0: every
parameter of every effect, condition and target says what kind of question it
is, what values it takes, whether it is needed, what another answer overrides,
and what it names. The Author UI did not read it. This is what was lost between
the two, and what the renderer does now.

## 1. What the metadata said and the page threw away

`capabilities._fields()` emitted eight facts per parameter. `fieldsHtml()` read
two of them — whether there were `choices`, and the `kind` — and branched three
ways: a single `<select>`, a checkbox, or an `<input>`. Everything else fell
through to a text box.

| Fact | Parameters carrying it | What the page did |
| --- | --- | --- |
| `shown` | all 297 | never read; the routing `_fields` computed was ignored |
| `role` | all 297 | never read; seven roles collapsed into three controls |
| `picks` | 24 target parameters | **filtered the field out entirely** — `chooser`, `of`, `exclude` were unreachable |
| `role == whom` | 9 effect parameters | fell through to a plain text box |
| `role == structure` | 4 | fell through to a plain text box |
| `kind == "a list"` | 4 | drawn as a single `<select>`, producing `"loot"` where the card needs `["loot"]` |
| `required` | 8 | never read; an empty needed box looked like an empty optional one |
| `unless` | 4 | never read; both halves of an either/or shown as independent questions |
| `least` | 61 | applied only in the number branch |
| the effect's default | nowhere | not in the metadata at all, so a blank box could not say what it meant |

Two further losses were not in any single field:

- **Aiming and naming were the same question.** `aimHtml` offered one target
  per effect. `give_treasure.to`, `require_attack.who` and the rest are a
  *second* concept — who receives, who owes — and there was nowhere to put
  them. `require_attack` could name the monster or the player, never both.
- **The path walk started at the window.** `at()` reduced from `window`, and
  `state` is a `let` binding rather than a window property, so every answer
  landed in a second object of the same name. The form looked like it worked
  and the card kept none of it. Nothing caught this because the HTTP tests post
  state directly and never run the page.

Downstream, the validator skipped every parameter whose kind is "anything the
engine can only judge during a game". `{"who": "the loser"}` loaded and then
failed the first time somebody played the card.

## 2. What the renderer does now

One dispatch, on `shown`, and then on `role`. No effect is named anywhere in
the page — a test asserts that.

- **`engine`** — a sentence, not a control. Four parameters take a card the
  engine already holds and no card file can name one.
- **`group`** — the engine's own targets, filtered by what the parameter names
  (`players`, `cards`, or anything the ability chose), with that target's own
  parameters rendered underneath, recursively. The bound group and the
  reference to it are written behind the author.
- **`advanced`** — a disclosure holding the structure as a structure. What is
  typed is parsed; what does not parse is **not stored**, so a half-written
  structure never becomes a string.
- **`form`** — by role: `switch` a checkbox, `amount` a number with its floor,
  `which` a selection from its domain, `names` text, `open` text read as JSON
  and kept as words when it is not. A parameter whose kind is a list gets a
  multiple selection and produces a list.

On top of that: required parameters are marked and say so before the server
does; a parameter another one overrides is greyed out with the reason, and the
overriding parameter redraws the form when it changes; and every empty box
shows what the effect does when it is left empty.

## 3. Which metadata classes are supported

| Class | Where it is read | Control |
| --- | --- | --- |
| `role: amount` (107) | `valueHtml` | number, `min` from `least`, placeholder from the default |
| `role: which` (43) | `valueHtml` | selection from `choices` |
| `role: switch` (31) | `valueHtml` | checkbox |
| `role: names` (80) | `valueHtml` | text |
| `role: whom` (30) | `groupHtml` / `engineHtml` | target picker, or a sentence |
| `role: structure` (4) | `structureHtml` | parsed structure editor |
| `role: open` (2) | `valueHtml` | text read as JSON |
| `kind: a list` with a domain (4) | `valueHtml` | multiple selection → a list |
| `required` (8) | everywhere | marked, and said when blank |
| `unless` + `unless_when` (4) | `moot` | disabled, with the reason |
| `picks` (`players`/`cards`/`any`) | `fits` | which targets are offered |
| `written_as` (33) | `groupHtml`, `author.py` | how the name is written into the card |

Three facts were added to the metadata, because the renderer needed them and
nothing said them:

- **`written_as`** — how a card writes a parameter that names somebody. Four
  answers: a bare group name, `{"player_of": name}`, the name of a stored
  value, or nothing a card may write. Derived from `refers_to` for targets and
  conditions; declared at registration for effects, because the split is real
  — a target reads a bound group by name, an effect is handed seat numbers.
- **`default`** — what the effect does when a box is left empty. Read off the
  handler's signature, never declared.
- **`unless_when`** — which values of the overriding parameter actually make
  this one moot. `move_cards.depth_from` is meaningless when `position` is
  `bottom`, which is also the default; without the value named, a form would
  offer a depth the effect will not read.

`picks` was widened from a target-only fact to one the nine effect parameters
carry too, which made their `roles={...: WHOM}` declarations derivable and
removed them.

## 4. What the engine can still do that the form cannot draw

- **Nested rules inside a structure.** `promise.changes` and `watch_for.effects`
  are shown as structures and edited as structures, not built with the same
  step-by-step editor the ability uses. That is an editor of its own and was
  out of scope.
- **`store` and the values it writes.** `values_equal.of` names a value an
  earlier step stored, and there is no way to write a `store` in the form, so
  the box is text and the author has to know the name. It is labelled as what
  it is rather than hidden.
- **More than one ability per card, `may`, `choose`, `for_each`, statics.** The
  editor still builds one ability with one trigger; unchanged by this pass.
- **`watch_for.conditions` outer shape.** The other three structures now
  declare whether they hold a list or a set of named values and are checked
  against it. `conditions` is left alone because a card may legitimately write
  one condition where a list is expected.
- **Labels.** 116 of 297 parameters now carry human words, up from 14. The rest
  are their own names, which for `count`, `amount`, `deck` and `player` reads
  correctly; renaming the remainder blindly would be renaming for its own sake.

## 5. Where validation was tightened

Never loosened. Three things that used to load and fail during a game are now
refused at load time, all read off the metadata and none naming an effect:

- a parameter that names a player, given anything but a seat number or
  `{"player_of": name}`;
- a parameter the engine supplies, written by a card at all;
- a parameter an effect keeps as written, given something that is not the
  shape it keeps — `{"effects": "gain_coins"}` where a list belongs.

All 1045 shipped cards still load unchanged, and 1000 recorded games replay
identically.
