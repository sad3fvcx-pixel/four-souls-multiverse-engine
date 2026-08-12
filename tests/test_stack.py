"""
Stack invariants from STACK.md section 20.
"""

from __future__ import annotations

import pytest

from fsme.stack import Stack, StackItem, StackItemStatus, StackItemType


def item(label: str) -> StackItem:
    return StackItem(kind=StackItemType.ENGINE_EFFECT, label=label)


def test_resolves_last_in_first_out() -> None:
    stack = Stack()

    stack.push(item("a"))
    stack.push(item("b"))
    stack.push(item("c"))

    assert [stack.pop().label for _ in range(3)] == ["c", "b", "a"]


def test_peek_does_not_remove() -> None:
    stack = Stack()
    stack.push(item("a"))

    assert stack.peek().label == "a"
    assert len(stack) == 1


def test_empty_stack_is_valid_but_pop_raises() -> None:
    stack = Stack()

    assert stack.is_empty()
    assert len(stack) == 0

    with pytest.raises(IndexError):
        stack.pop()


def test_item_lifecycle_states() -> None:
    entry = item("a")

    assert entry.status is StackItemStatus.CREATED

    entry.mark_resolving()
    assert entry.status is StackItemStatus.RESOLVING

    entry.mark_resolved()
    assert entry.status is StackItemStatus.RESOLVED

    entry.fizzle()
    assert entry.status is StackItemStatus.FIZZLED
