# Card Constructor v0.9 — the last three, and what they name

Three cards are still refused: `famine`, `viii_justice`, `the_d4`. This asks
why, and whether they can be supported without changing what any card means.

Analysis only. Nothing was changed. Measured at `b021e94`.

**The answer: one gap, in one place, and it is neither a new concept nor a
missing declaration.** All three name something the ability chose from *inside
a nested node*, and the reader follows a reference at the top of an answer but
not inside one. The model already declares those references, the runtime
already resolves them, and the checker already checks them.

---

## 1. What each card says

| card | the construct | refused by |
|---|---|---|
| `famine` | `discard_loot.count` = `{"count": "loot", "of": "loser"}` | `_refuse_a_working` |
| `viii_justice` | `draw_loot.count` and `gain_coins.amount`, each `{"count": …, "of": "rival", "minus": "controller"}` | `_refuse_a_working` |
| `the_d4` | `for_each` over `{"owned_treasure": {"of": "rerolled_player", …}}` | `_names_one_of`, in the control-node reader |

Both refusals say the same thing in different words, and both were written
when it was true: *reading the answer without the binding would leave a card
counting nobody's hand*, and *folding that up would leave it pointing at
nothing*. The binding used to be dropped. Since `b021e94` it is not.

---

## 2. What is actually named, and by what

Over every shipped card, the answers genuinely written as a worked-out value
that names something the ability bound number **nine**, and they divide on one
line:

| head | cards | today |
|---|---|---|
| `player_of` | `forever_alone`, `jawbone`, `donation_machine`, `baby_haunt`, `daddy_haunt`, `guppy_s_head` | **all readable** |
| `of` / `minus` | `viii_justice` ×2, `famine` | **refused** |

And `for_each` domains that name a binding: **one**, `the_d4`.

The difference is not in the cards. It is in `_points_at`:

```python
if parameter.written_as == BY_PLAYER_OF:
    if isinstance(value, Mapping) and set(value) == {BY_PLAYER_OF}:
        return str(value[BY_PLAYER_OF])
    return None

return str(value) if isinstance(value, str) else None
```

It follows two spellings — a bare name, and the one dynamic head that answers
with a seat. `take_card.player` is declared `written_as = player_of`, so
`{"player_of": "heir"}` is followed, becomes a chosen in author state, and the
writer rebuilds the binding from it. That path works and six cards use it.

`draw_loot.count` is declared a whole number: `refers_to` is empty, so
`_points_at` returns `None` at the first line and the value — `{"count":
"loot", "of": "rival"}` — is kept as an opaque field. The reference is one
level in, inside a node the parameter says it *may be written as*.

**That is the whole of the gap: a reference inside a nested node is not
followed.**

---

## 3. The model already declares it

`worked_out`, published to the page today:

| answer | picks | shown | written |
|---|---|---|---|
| `of` | `any` | **group** | the name of something the ability chose |
| `minus` | `any` | **group** | the name of something the ability chose |
| `player_of` | `players` | group | the name of something the ability chose |
| `from` | `values` | form | the name of a value an earlier step stored |

`shown: group` means the page already routes `of` and `minus` to a binding
picker. Seventy effect answers declare that they may be written this way.

`for_each` likewise: its domain is `shaped_like: "target"`, `role: "nested"` —
a nested target node, and the inner `owned_treasure.of` carries
`refers_to: "players"`, `written_as: "the name of something the ability
chose"`.

So nothing is undeclared. The engine says it, the catalogue publishes it, the
page is ready to draw it, and the checker checks it. Only the reader does not
descend.

---

## 4. Timing, and why nothing may become a literal

Measured at both sites:

| | when |
|---|---|
| the binding `rival` / `loser` / `rerolled_player` is chosen | **before any step runs** — it is in the ability's list, resolved before the ops are built |
| the worked-out value is computed | **when the step runs** — `_resolve_params` is called inside `execute`, per op |
| the `for_each` domain is resolved | **when the loop is expanded** — `_expand_for_each` resolves it against live state, and binds each object under a private `__each:N` of the engine's own |

So `{"count": "loot", "of": "rival"}` is *"as many as that player is holding
at the moment this step runs"*. Turning it into a number at author time would
be a different card, and the measurement below shows it is not turned into
one: the expression is kept verbatim.

---

## 5. What would happen if the guards were simply lifted

Each guard lifted alone, in memory, nothing on disk touched. This proves
nothing about whether lifting is *right*; it shows what the rest of the
pipeline does.

| card | with only the worked-out guard lifted | with only the control-node guard lifted |
|---|---|---|
| `famine` | reads, means the same, **checker clean** | still refused |
| `viii_justice` | reads, means the same, **checker refuses** | still refused |
| `the_d4` | still refused | reads, means the same, **checker clean** |

`famine` and `the_d4` come back correct — the count and the domain are kept as
expressions, and their bindings survive. But they survive **by luck, not by
design**: in both cards a step also *aims* at the same name, so the aim
rebuilds the binding.

`viii_justice` is the proof. `rival` is named only inside worked-out values;
no step aims at it. The rebuilt card is:

```json
"targets": [],
"effects": [
  {"effect": "draw_loot", "count": {"count": "loot", "of": "rival", "minus": "controller"}},
  {"effect": "gain_coins", "amount": {"count": "coins", "of": "rival", "minus": "controller"}}
]
```

and the checker says, correctly, *"'rival' is not a group this ability
binds"*. The value kept its shape and lost the thing it refers to.

**So lifting the guards is not the fix.** It would open two cards that happen
to be rescued by an aim and produce a broken third — and worse, it would leave
the first two depending on a coincidence rather than on the reader.

---

## 6. Scope

The already-established model covers all three with nothing new:

| card | binding made | value read | relation |
|---|---|---|---|
| `famine` | the ability's list | a step in `.effects` | outer → nested (**C**) |
| `viii_justice` | the ability's list | two steps in `.effects` | outer → nested (**C**) |
| `the_d4` | the ability's list | inside `.effects[1].then` | outer → nested (**C**) |

All are C-reads — an outer scope seen from within. `visible = current +
parents` answers every one, and no new scope mechanism is needed. `for_each`'s
own `__each:N` bindings are the engine's, made and used inside the loop, and
no card ever names one.

---

## 7. The table

| card | construct | current blocker | existing concept? | minimal fix |
|---|---|---|---|---|
| `famine` | a count worked out from a bound player | `_refuse_a_working` | **yes** — `worked_out.of`, published, `picks: any`, `shown: group` | follow a reference inside a worked-out node, as `_as_chosen` already follows one inside a target |
| `viii_justice` | the same, twice, and the only mention of the binding | `_refuse_a_working` | **yes** — same declaration | the same, and it is the card that requires it rather than benefiting from it |
| `the_d4` | a `for_each` domain naming a bound player | `_names_one_of` in the control-node reader | **yes** — `for_each.of` is `shaped_like: target`, and `owned_treasure.of` carries `refers_to: players` | follow the reference into the nested target, which `_as_chosen` already knows how to do |

Not one of the three needs a declaration added, and not one needs a new idea.

---

## 8. How to prove it, if it is ever implemented

Checker-passes, JSON-valid and card-opens are all insufficient. Three things
have to be shown per card:

1. **The value is still an expression.** `count` comes back as
   `{"count": "loot", "of": "loser"}`, never as a number — asserted on the
   rebuilt card, not on the state.
2. **The name still points at a binding the card makes**, and that binding is
   at the same level it was: `viii_justice` binds `rival` in the ability's
   list, because that is when the player is asked. The `when_asked` ledger
   from the step-bindings stage already measures this.
3. **The moment is unchanged.** The binding is resolved before any step; the
   value is computed when its step runs; the loop domain when the loop
   expands. A round trip must not move any of the three, and the replay is the
   guard that nothing about play changed.

And one negative test, which is the real one: **a card whose binding is named
only inside a worked-out value must round-trip**, because that is the case an
aim cannot rescue. `viii_justice` is exactly it.

---

## 9. Classification

### A — existing concept, only representation missing

**All three.** The concept is declared in the vocabulary, published in the
catalogue, resolved by the runtime and checked by the checker. What is absent
is that the reader follows a reference at the top of an answer and not inside
a nested one, so the writer never learns the binding is needed.

It is the same shape of finding as every stage in this sequence, one level
further in — and this time the missing piece is not a field but a descent
that already exists next door, in `_as_chosen`.

### B — existing runtime semantics without author-state representation

**None.** Author state already holds exactly this: a choice, inlined, with the
word the card gave it. `player_of` proves it — six cards store a reference
found inside a value and rebuild it correctly today.

### C — a new card-language concept

**None.** Nothing here would add a word to the language, change what a card may
say, or change what any card means.

---

## 10. What this stage does not do

It proposes no change. The fix is not "lift the two guards" — §5 shows that
opens two cards on a coincidence and breaks a third. It is to follow the
reference the model already declares, and then the guards have nothing left to
refuse.

Whether to do that is a separate decision. Three cards is a small prize; the
reason it may be worth it is that the same descent would make the six
`player_of` cards work by design rather than by having taken the one path the
reader happens to follow.
