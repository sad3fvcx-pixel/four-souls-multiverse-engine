# Official Card Coverage

Этот документ генерируется из содержимого `content/`.
Не редактируйте его руками: `python tools/coverage_report.py`.

Он отвечает на два разных вопроса, и их важно не путать:

1. **Лежит ли карта в репозитории.**
2. **Знает ли движок, что она делает.**

Карта получает 🟩 только тогда, когда у неё есть поведение — способности
или статики. Напечатанные числа, текст и количество копий импортированы у
всех карт, но сами по себе они ничего не делают.

Есть и третий ответ: ▪️ — на карте нет правил. Монстр с хитами, атакой и
цитатой из Библии закончен в тот момент, когда импортирован. Это утверждение
делает человек, прочитавший карту, а не импорт: пометка `"vanilla": true`
ставится руками в `_abilities.json`.

---

# Итог

Импортировано официальных карт: **1014**. Реализовано: **246**. Без правил: **17**. Осталось: **751**.

| Набор | Карт | Реализовано | Без правил | Осталось |
|---|---:|---:|---:|---:|
| `base_game` | 287 | 246 | 17 | 24 |
| `requiem` | 246 | 0 | 0 | 246 |
| `warp_zone` | 99 | 0 | 0 | 99 |
| `four_souls` | 90 | 0 | 0 | 90 |
| `gold_box` | 64 | 0 | 0 | 64 |
| `alt_art` | 62 | 0 | 0 | 62 |
| `the_summer_of_isaac` | 50 | 0 | 0 | 50 |
| `the_unboxing_of_isaac` | 40 | 0 | 0 | 40 |
| `star_promos` | 25 | 0 | 0 | 25 |
| `anniversary` | 16 | 0 | 0 | 16 |
| `tapeworm` | 7 | 0 | 0 | 7 |
| `anniversary_booster_pack` | 4 | 0 | 0 | 4 |
| `g_fuel` | 4 | 0 | 0 | 4 |
| `mewgenics` | 4 | 0 | 0 | 4 |
| `target` | 3 | 0 | 0 | 3 |
| `gish` | 2 | 0 | 0 | 2 |
| `nendoroid` | 2 | 0 | 0 | 2 |
| `retro` | 2 | 0 | 0 | 2 |
| `the_legend_of_bum_bo` | 2 | 0 | 0 | 2 |
| `youtooz` | 2 | 0 | 0 | 2 |
| `challenges` | 1 | 0 | 0 | 1 |
| `dick_knots` | 1 | 0 | 0 | 1 |
| `star` | 1 | 0 | 0 | 1 |
| **всего** | **1014** | **246** | **17** | **751** |

---

# base_game

| Тип | Карт | Реализовано | Без правил |
|---|---:|---:|---:|
| treasure | 105 | 88 | 0 |
| monster | 85 | 65 | 17 |
| loot | 51 | 50 | 0 |
| event | 17 | 16 | 0 |
| character | 11 | 9 | 0 |
| starting_item | 10 | 10 | 0 |
| curse | 5 | 5 | 0 |
| bonus_soul | 3 | 3 | 0 |


## Characters

| Card | Status | Notes |
|------|--------|-------|
| Blue Baby | 🟩 |  |
| Cain | ⬜ |  |
| Eden | ⬜ |  |
| Eve | 🟩 |  |
| Isaac | 🟩 |  |
| Judas | 🟩 |  |
| Lazarus | 🟩 |  |
| Lilith | 🟩 |  |
| Maggy | 🟩 |  |
| Samson | 🟩 |  |
| The Forgotten | 🟩 |  |

## Starting Items

| Card | Status | Notes |
|------|--------|-------|
| Blood Lust | 🟩 |  |
| Book of Belial | 🟩 |  |
| Forever Alone | 🟩 |  |
| Incubus | 🟩 |  |
| Lazarus' Rags | 🟩 |  |
| Sleight of Hand | 🟩 |  |
| The Bone | 🟩 |  |
| The Curse | 🟩 |  |
| The D6 | 🟩 |  |
| Yum Heart | 🟩 |  |

## Treasure

| Card | Status | Notes |
|------|--------|-------|
| Baby Haunt | ⬜ |  |
| Battery Bum | 🟩 |  |
| Belly Button | 🟩 |  |
| Blank Card | ⬜ |  |
| Bob's Brain | 🟩 |  |
| Book of Sin | 🟩 |  |
| Boomerang | 🟩 |  |
| Box! | ⬜ |  |
| Breakfast | 🟩 |  |
| Brimstone | 🟩 |  |
| Bum Friend | 🟩 |  |
| Bum-bo! | 🟩 |  |
| Cambion Conception | 🟩 |  |
| Champion Belt | 🟩 |  |
| Chaos | 🟩 |  |
| Chaos Card | 🟩 |  |
| Charged Baby | 🟩 |  |
| Cheese Grater | 🟩 |  |
| Compost | 🟩 |  |
| Contract from Below | ⬜ |  |
| Crystal Ball | ⬜ |  |
| Curse of the Tower | 🟩 |  |
| Dad's Lost Coin | 🟩 |  |
| Daddy Haunt | ⬜ |  |
| Dark Bum | 🟩 |  |
| Dead Bird | 🟩 |  |
| Decoy | 🟩 |  |
| Dinner | 🟩 |  |
| Diplopia | 🟩 |  |
| Donation Machine | 🟩 |  |
| Dry Baby | 🟩 |  |
| Eden's Blessing | 🟩 |  |
| Empty Vessel | 🟩 |  |
| Eye of Greed | 🟩 |  |
| Fanny Pack | 🟩 |  |
| Finger! | 🟩 |  |
| Flush! | 🟩 |  |
| Glass Cannon | 🟩 |  |
| Goat Head | 🟩 |  |
| Godhead | 🟩 |  |
| Golden Razor Blade | 🟩 |  |
| Greed's Gullet | 🟩 |  |
| Guppy's Collar | ⬜ |  |
| Guppy's Head | 🟩 |  |
| Guppy's Paw | 🟩 |  |
| Host Hat | ⬜ |  |
| Ipecac | 🟩 |  |
| Jawbone | 🟩 |  |
| Lucky Foot | 🟩 |  |
| Meat! | 🟩 |  |
| Mini Mush | 🟩 |  |
| Modeling Clay | 🟩 |  |
| Mom's Box | 🟩 |  |
| Mom's Bra | 🟩 |  |
| Mom's Coin Purse | ⬜ |  |
| Mom's Purse | ⬜ |  |
| Mom's Razor | 🟩 |  |
| Mom's Shovel | 🟩 |  |
| Monster Manual | ⬜ |  |
| Monstro's Tooth | 🟩 |  |
| Mr. Boom | 🟩 |  |
| Mystery Sack | 🟩 |  |
| No! | 🟩 |  |
| Pandora's Box | 🟩 |  |
| Pay to Play | 🟩 |  |
| Placebo | ⬜ |  |
| Polydactyly | 🟩 |  |
| Portable Slot Machine | 🟩 |  |
| Potato Peeler | 🟩 |  |
| Razor Blade | 🟩 |  |
| Remote Detonator | ⬜ |  |
| Restock | 🟩 |  |
| Sack Head | 🟩 |  |
| Sack of Pennies | 🟩 |  |
| Sacred Heart | ⬜ |  |
| Shadow | ⬜ |  |
| Shiny Rock | 🟩 |  |
| Smelter | 🟩 |  |
| Spider Mod | 🟩 |  |
| Spoon Bender | 🟩 |  |
| Starter Deck | 🟩 |  |
| Steamy Sale! | 🟩 |  |
| Suicide King | 🟩 |  |
| Synthoil | 🟩 |  |
| Tarot Cloth | 🟩 |  |
| Tech X | 🟩 |  |
| The Battery | 🟩 |  |
| The Blue Map | 🟩 |  |
| The Chest | 🟩 |  |
| The Compass | 🟩 |  |
| The D10 | ⬜ |  |
| The D100 | 🟩 |  |
| The D20 | 🟩 |  |
| The D4 | 🟩 |  |
| The Dead Cat | 🟩 |  |
| The Habit | 🟩 |  |
| The Map | 🟩 |  |
| The Midas Touch | 🟩 |  |
| The Polaroid | 🟩 |  |
| The Poop | 🟩 |  |
| The Relic | 🟩 |  |
| The Shovel | 🟩 |  |
| There's Options | ⬜ |  |
| Trinity Shield | 🟩 |  |
| Two of Clubs | 🟩 |  |

## Loot

| Card | Status | Notes |
|------|--------|-------|
| 2 Cents! | 🟩 | ×12 |
| 3 Cents! | 🟩 | ×15 |
| 4 Cents! | 🟩 | ×9 |
| A Dime!! | 🟩 |  |
| A Nickel! | 🟩 | ×5 |
| A Penny! | 🟩 | ×6 |
| Blank Rune | 🟩 |  |
| Bloody Penny | 🟩 |  |
| Bomb! | 🟩 | ×4 |
| Broken Ankh | ⬜ |  |
| Butter Bean! | 🟩 | ×3 |
| Cain's Eye | 🟩 |  |
| Counterfeit Penny | 🟩 |  |
| Curved Horn | 🟩 |  |
| Dagaz | 🟩 |  |
| Dice Shard | 🟩 | ×3 |
| Ehwaz | 🟩 |  |
| Gold Bomb!! | 🟩 |  |
| Golden Horseshoe | 🟩 |  |
| Guppy's Hairball | 🟩 |  |
| I. The Magician | 🟩 |  |
| II. The High Priestess | 🟩 |  |
| III. The Empress | 🟩 |  |
| IV. The Emperor | 🟩 |  |
| IX. The Hermit | 🟩 |  |
| Lil Battery | 🟩 | ×4 |
| Lost Soul | 🟩 |  |
| Mega Battery | 🟩 |  |
| O. The Fool | 🟩 |  |
| Pills! | 🟩 |  |
| Pills! | 🟩 |  |
| Pills! | 🟩 |  |
| Purple Heart | 🟩 |  |
| Soul Heart | 🟩 | ×2 |
| Swallowed Penny | 🟩 |  |
| V. The Hierophant | 🟩 |  |
| VI. The Lovers | 🟩 |  |
| VII. The Chariot | 🟩 |  |
| VIII. Justice | 🟩 |  |
| X. Wheel of Fortune | 🟩 |  |
| XI. Strength | 🟩 |  |
| XII. The Hanged Man | 🟩 |  |
| XIII. Death | 🟩 |  |
| XIV. Temperance | 🟩 |  |
| XIX. The Sun | 🟩 |  |
| XV. The Devil | 🟩 |  |
| XVI. The Tower | 🟩 |  |
| XVII. The Stars | 🟩 |  |
| XVIII. The Moon | 🟩 |  |
| XX. Judgement | 🟩 |  |
| XXI. The World | 🟩 |  |

## Monsters

| Card | Status | Notes |
|------|--------|-------|
| Big Spider | 🟩 |  |
| Black Bony | 🟩 |  |
| Boom Fly | 🟩 |  |
| Carrion Queen | 🟩 |  |
| Chub | 🟩 |  |
| Clotty | ▪️ | нет правил на карте |
| Cod Worm | ▪️ | нет правил на карте |
| Conjoined Fatty | ▪️ | нет правил на карте |
| Conquest | 🟩 |  |
| Cursed Fatty | 🟩 |  |
| Cursed Gaper | 🟩 |  |
| Cursed Horf | 🟩 |  |
| Cursed Keeper Head | 🟩 |  |
| Cursed Mom's Hand | 🟩 |  |
| Cursed Psy Horf | 🟩 |  |
| Daddy Long Legs | 🟩 |  |
| Dank Globin | 🟩 |  |
| Dark One | 🟩 |  |
| Death | 🟩 |  |
| Delirium | 🟩 |  |
| Dinga | ⬜ |  |
| Dip | ▪️ | нет правил на карте |
| Dople | 🟩 |  |
| Envy | 🟩 |  |
| Evil Twin | 🟩 |  |
| Famine | 🟩 |  |
| Fat Bat | ▪️ | нет правил на карте |
| Fatty | ▪️ | нет правил на карте |
| Fly | ▪️ | нет правил на карте |
| Gemini | 🟩 |  |
| Gluttony | 🟩 |  |
| Greed | 🟩 |  |
| Greedling | 🟩 |  |
| Gurdy | ▪️ | нет правил на карте |
| Gurdy Jr. | 🟩 |  |
| Hanger | 🟩 |  |
| Holy Dinga | 🟩 |  |
| Holy Dip | 🟩 |  |
| Holy Keeper Head | 🟩 |  |
| Holy Mom's Eye | 🟩 |  |
| Holy Squirt | 🟩 |  |
| Hopper | 🟩 |  |
| Horf | 🟩 |  |
| Keeper Head | 🟩 |  |
| Larry Jr. | 🟩 |  |
| Leaper | 🟩 |  |
| Leech | ▪️ | нет правил на карте |
| Little Horn | ▪️ | нет правил на карте |
| Lust | 🟩 |  |
| Mask of Infamy | 🟩 |  |
| Mega Fatty | 🟩 |  |
| Mom! | 🟩 |  |
| Mom's Dead Hand | 🟩 |  |
| Mom's Eye | 🟩 |  |
| Mom's Hand | 🟩 |  |
| Monstro | ▪️ | нет правил на карте |
| Mulliboom | 🟩 |  |
| Mulligan | 🟩 |  |
| Pale Fatty | ▪️ | нет правил на карте |
| Peep | ⬜ |  |
| Pestilence | ⬜ |  |
| Pin | 🟩 |  |
| Pooter | ▪️ | нет правил на карте |
| Portal | 🟩 |  |
| Pride | 🟩 |  |
| Psy Horf | 🟩 |  |
| Rag Man | 🟩 |  |
| Rage Creep | 🟩 |  |
| Red Host | ▪️ | нет правил на карте |
| Ring of Flies | 🟩 |  |
| Satan! | 🟩 |  |
| Scolex | 🟩 |  |
| Sloth | 🟩 |  |
| Spider | ▪️ | нет правил на карте |
| Squirt | ▪️ | нет правил на карте |
| Stoney | 🟩 |  |
| Swarm of Flies | 🟩 |  |
| The Bloat | 🟩 |  |
| The Duke of Flies | 🟩 |  |
| The Haunt | 🟩 |  |
| The Lamb | 🟩 |  |
| Trite | ▪️ | нет правил на карте |
| War | 🟩 |  |
| Wizoob | 🟩 |  |
| Wrath | 🟩 |  |

## Events

| Card | Status | Notes |
|------|--------|-------|
| Ambush! | ⬜ |  |
| Chest | 🟩 |  |
| Chest | 🟩 |  |
| Cursed Chest | 🟩 |  |
| Dark Chest | 🟩 |  |
| Dark Chest | 🟩 |  |
| Devil Deal | 🟩 |  |
| Gold Chest | 🟩 |  |
| Gold Chest | 🟩 |  |
| Greed! | 🟩 |  |
| I Can See Forever! | 🟩 |  |
| Mega Troll Bomb! | 🟩 |  |
| Secret Room! | 🟩 |  |
| Shop Upgrade! | 🟩 |  |
| Troll Bombs | 🟩 |  |
| We Need to Go Deeper! | 🟩 |  |
| XL Floor! | 🟩 |  |

## Curses

| Card | Status | Notes |
|------|--------|-------|
| Curse of Amnesia | 🟩 |  |
| Curse of Greed | 🟩 |  |
| Curse of Loss | 🟩 |  |
| Curse of Pain | 🟩 |  |
| Curse of the Blind | 🟩 |  |

## Bonus Souls

| Card | Status | Notes |
|------|--------|-------|
| Soul of Gluttony | 🟩 |  |
| Soul of Greed | 🟩 |  |
| Soul of Guppy | 🟩 |  |
