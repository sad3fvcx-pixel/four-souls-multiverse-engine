# Four Souls Multiverse Engine
# Effect DSL Specification

Version: 1.0 (Draft)

---

# Цель

Effect DSL — это универсальный язык описания поведения карт.

Движок не знает конкретных карт.
Он знает только операции, триггеры, условия и эффекты.

Любая карта должна быть описываема средствами DSL.

---

# Общая структура

Карта состоит из одной или нескольких способностей.

Ability

↓

Trigger

↓

Condition (необязательно)

↓

Target (необязательно)

↓

Effect

↓

Следующий Effect

---

# Ability

Каждая способность имеет структуру

{
    "trigger": "...",
    "conditions": [],
    "targets": [],
    "effects": []
}

Карта может иметь любое количество способностей.

---

# Trigger

Способность начинается с триггера.

Примеры:

activate

passive

enter

leave

purchase

destroy

death

turn_start

turn_end

attack_start

attack_end

before_damage

after_damage

before_roll

after_roll

before_payment

after_payment

before_loot

after_loot

before_treasure

after_treasure

stack_push

stack_resolve

monster_killed

player_died

---

# Condition

Условие определяет,
можно ли выполнить способность.

Условия объединяются через AND.

Позже добавится OR.

Примеры:

controller_alive

target_alive

monster_alive

has_coins

has_loot

has_treasure

has_souls

is_active_player

is_owner

dice_equals

dice_greater

hp_less

hp_greater

item_charged

monster_boss

room_open

stack_not_empty

...

---

# Target

Цель определяется отдельно.

Возможные цели

self

controller

owner

target_player

target_monster

target_item

target_room

random_player

random_monster

all_players

all_monsters

all_items

stack_item

last_stack_item

chosen_card

...

---

# Effect

Эффект является атомарной операцией.

Каждый эффект выполняет одну задачу.

Например

gain_coins

lose_coins

gain_hp

lose_hp

deal_damage

heal

kill

destroy

discard

draw_loot

draw_treasure

gain_soul

lose_soul

recharge

tap

untap

roll_dice

reroll

cancel

copy_effect

choose

search

shuffle

spawn

transform

move

pay

prevent_damage

...

---

# Sequence

Эффекты выполняются сверху вниз.

effects

↓

effect

↓

effect

↓

effect

---

# Branch

Любая способность может содержать

if

else

---

# Loop

DSL поддерживает

repeat

repeat_until

for_each

while

(если понадобится)

---

# Choice

Игрок может выбирать.

choose_player

choose_monster

choose_item

choose_room

choose_card

choose_effect

---

# Random

DSL поддерживает

random_player

random_card

random_loot

random_treasure

random_item

random_monster

---

# Stack

Любой эффект может

push

resolve

cancel

copy

peek

---

# Future

Планируется поддержка

variables

temporary values

macros

custom effects
