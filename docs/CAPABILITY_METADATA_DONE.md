# Capability metadata: what changed

Steps 1–4 of `docs/CAPABILITY_METADATA.md`. Step 5 — the literary pass over
`asks=` — was deliberately not started.

**Every one of the 74 effect parameters now has a role, and every parameter of
every condition and target does too.** Nothing was removed: the two roles the
ordinary form cannot draw are routed to aiming and to the advanced view rather
than dropped.

---

## 1. Domains the engine enforced and never declared

Nine, not the six the audit could prove. Three more were found by reading the
audit's own output: they convert rather than raise, so no guard scan could see
them.

| parameter | was | is |
|---|---|---|
| `lift_limit.what` | free text, one legal value | dropdown from `LIMITS` |
| `expand_slots.area` | free text | dropdown from `AREAS` |
| `copy_card.until` | free text | dropdown from `(TILL_END_OF_TURN, INDEFINITELY)` |
| `pass_hands.direction` | free text | dropdown from `(LEFT, RIGHT)` |
| `require_attack.what` | free text | dropdown from `(MONSTER_DECK,)` |
| `promise.event` | free text | dropdown of all 66 events |
| `watch_for.event` | free text | dropdown of all 66 events |
| `take_card.shuffle` | free text — and it reads like a flag | dropdown of decks |
| `add_modifier.duration` | free text | dropdown from `Duration` |
| `copy_ability.trigger` | free text | dropdown of all 66 events |

Two domains had no name at all: `AREAS` and `LIMITS` are now written at the
branch that enforces them, and the branch reads them, so there is one fact and
not two. `_EVENT_NAMES` and `_TRIGGER_NAMES` name sets the guards used to build
inline.

## 2. Requirements the engine enforced and declared optional

Five. A form built from the old declaration let somebody submit a card that
could not run.

`add_counter.counter`, `add_modifier.stat`, `modify_event.key`,
`promise.event`, `watch_for.event` — all now required, via `needs=` on the
registration, next to the guard that raises.

## 3. Roles

Seven, one word each. **64 of 74 are derived** from what the parameter already
says — a flag is a switch, a number an amount, a closed set a choice — so
nobody writes them down and nothing can drift. The derivation lives in
`ParamShape.__post_init__`, which is why conditions and targets got roles for
free: 224 parameters in all, not 74.

The 10 that cannot be derived are declared, and they are exactly the ones the
audit predicted: nine cards-or-players the engine hands over, and one value
that is genuinely anything.

## 4. Where each role goes

| role | count (effects) | the form does |
|---|---|---|
| `amount` | 32 | a number box, floor applied |
| `which` | 16 | a dropdown of its own domain |
| `switch` | 8 | a checkbox |
| `names` | 4 | a text box |
| `whom` | 9 | **not a field** — the aiming question |
| `structure` | 4 | a sub-form, in the advanced view |
| `open` | 1 | free text, in the advanced view |

Across all three vocabularies: 260 fields in the form, 30 routed to aiming,
7 to advanced. **Nothing is hidden and nothing is lost** — a test asserts every
parameter the engine has still reaches the page, marked with where it belongs.

## 5. Dependencies

Four, read out of the handlers and declared beside them:

| parameter | is meaningless when |
|---|---|
| `heal.amount` | `full` is set |
| `add_counter.amount` | `clear` is set |
| `modify_event.factor` | `delta` is given |
| `move_cards.depth_from` | `position` says otherwise |

## 6. The obligation

Four tests that make this hold rather than merely true today:

- a parameter with no role fails the suite;
- a `which` with no choices fails;
- a domain a handler enforces but does not declare fails;
- a requirement a handler enforces but declares optional fails.

The last two scan the handlers with `ast` and compare against the
declarations, which is what found the original drift.

## 7. Also fixed along the way

A message listing all 66 event names was unreadable. `ParamShape.wants` now
says *"one of the 66 events the engine knows"* past twelve values, and lists
them below that — so nine stats and twelve card types still read as choices.

## 8. Checked

| | result |
|---|---|
| whole suite | **1263 pass** (12 new) |
| `content/` | 1045 cards, unchanged |
| `author-kit` | 5 of 5 |
| 1000 recorded games | **0 changed** |
| ruff, mypy --strict | clean |

## 9. The audit: all 74 effect parameters

| parameter | role | how it is asked | domain | required | meaningless when |
|---|---|---|---|---|---|
| `add_counter.amount` | amount | number | — | — | clear |
| `add_counter.clear` | switch | checkbox | — | — | — |
| `add_counter.counter` | names | text | — | yes | — |
| `add_counter.silences` | switch | checkbox | — | — | — |
| `add_modifier.amount` | amount | number | — | — | — |
| `add_modifier.duration` | which | dropdown | 2 | — | — |
| `add_modifier.stat` | which | dropdown | 9 | yes | — |
| `attach_curse.card` | whom | aiming, not a field | — | — | — |
| `claim_soul.card` | whom | aiming, not a field | — | — | — |
| `copy_ability.trigger` | which | dropdown | 66 | — | — |
| `copy_card.until` | which | dropdown | 2 | — | — |
| `deal_damage.amount` | amount | number | — | — | — |
| `deal_damage.combat` | switch | checkbox | — | — | — |
| `deal_damage.dealt_by` | whom | aiming, not a field | — | — | — |
| `deal_damage.roll` | amount | number | — | — | — |
| `discard_loot.count` | amount | number | — | — | — |
| `divide_damage.dealt_by` | whom | aiming, not a field | — | — | — |
| `divide_damage.each` | amount | number | — | — | — |
| `draw_loot.count` | amount | number | — | — | — |
| `enter_room.count` | amount | number | — | — | — |
| `expand_slots.amount` | amount | number | — | — | — |
| `expand_slots.area` | which | dropdown | 2 | — | — |
| `gain_coins.amount` | amount | number | — | — | — |
| `gain_soul.card` | whom | aiming, not a field | — | — | — |
| `gain_soul.count` | amount | number | — | — | — |
| `gain_soul.earned_from` | whom | aiming, not a field | — | — | — |
| `gain_treasure.count` | amount | number | — | — | — |
| `give_treasure.to` | whom | aiming, not a field | — | — | — |
| `heal.amount` | amount | number | — | — | full |
| `heal.full` | switch | checkbox | — | — | — |
| `lift_limit.what` | which | dropdown | 1 | — | — |
| `lose_coins.amount` | amount | number | — | — | — |
| `lose_soul.count` | amount | number | — | — | — |
| `modify_event.delta` | amount | number | — | — | — |
| `modify_event.factor` | amount | number | — | — | delta |
| `modify_event.key` | names | text | — | yes | — |
| `modify_event.value` | open | free text (advanced) | — | — | — |
| `modify_roll.amount` | amount | number | — | — | — |
| `move_cards.deck` | which | dropdown | 4 | — | — |
| `move_cards.depth_from` | amount | number | — | — | position |
| `move_cards.position` | which | dropdown | 3 | — | — |
| `pass_hands.direction` | which | dropdown | 2 | — | — |
| `place_monster.slot` | names | text | — | — | — |
| `prevent_damage.amount` | amount | number | — | — | — |
| `prevent_next_damage.amount` | amount | number | — | — | — |
| `prevent_next_damage.label` | names | text | — | — | — |
| `promise.changes` | structure | sub-form (advanced) | — | — | — |
| `promise.event` | which | dropdown | 66 | yes | — |
| `promise.unlimited` | switch | checkbox | — | — | — |
| `promise.uses` | amount | number | — | — | — |
| `promise.when` | structure | sub-form (advanced) | — | — | — |
| `require_attack.times` | amount | number | — | — | — |
| `require_attack.what` | which | dropdown | 1 | — | — |
| `require_attack.who` | whom | aiming, not a field | — | — | — |
| `reroll.sides` | amount | number | — | — | — |
| `reveal_cards.count` | amount | number | — | — | — |
| `reveal_cards.deck` | which | dropdown | 4 | — | — |
| `revive.hp` | amount | number | — | — | — |
| `roll_dice.sides` | amount | number | — | — | — |
| `set_coins.amount` | amount | number | — | — | — |
| `set_roll.value` | amount | number | — | — | — |
| `shuffle_deck.deck` | which | dropdown | 4 | — | — |
| `take_card.player` | whom | aiming, not a field | — | — | — |
| `take_card.shuffle` | which | dropdown | 5 | — | — |
| `take_card.to` | which | dropdown | 2 | — | — |
| `transfer_coins.amount` | amount | number | — | — | — |
| `transfer_coins.source_player` | amount | number | — | — | — |
| `watch_for.conditions` | structure | sub-form (advanced) | — | — | — |
| `watch_for.effects` | structure | sub-form (advanced) | — | — | — |
| `watch_for.event` | which | dropdown | 66 | yes | — |
| `watch_for.mine` | switch | checkbox | — | — | — |
| `watch_for.unlimited` | switch | checkbox | — | — | — |
| `watch_for.uses` | amount | number | — | — | — |
| `watch_for.waits` | switch | checkbox | — | — | — |

**74 parameters. Every one has a role, and a domain or a type. Nine are
explicitly not user fields — they are the aiming question — and five are
explicitly advanced.**

## 10. Not done

`asks=` still covers 14 of 74. After the above, the rest read as *role plus
domain* — `copy_card.until` is a dropdown of `end_of_turn` / `game` rather
than a box called "until" — so the remaining work is wording, not
comprehensibility. That was the instruction and it is where this stops.
