import argparse
import atexit
import os
import random
import sys
import time
from functools import cache
from typing import Optional
from urllib.parse import quote_plus

import json
import asyncio
import aiohttp

import optimals
import recipe
import util
from util import int_to_pair, pair_to_int, DEFAULT_STARTING_ITEMS, file_sanitize

init_state: tuple[str, ...] = DEFAULT_STARTING_ITEMS

visited = set()
best_depths: dict[str, int] = dict()
persistent_file: str = "persistent.json"
persistent_temporary_file: str = "persistent2.json"
result_directory: str = "Results"

persistent_config = util.load_json("config.json")

recipe_handler: Optional[recipe.RecipeHandler] = recipe.RecipeHandler(init_state, **persistent_config)
optimal_handler: Optional[optimals.OptimalRecipeStorage] = optimals.OptimalRecipeStorage()
depth_limit = 6
extra_depth = 0
case_sensitive = True
allow_starting_elements = False
resume_last_run = False
write_to_file = True

last_game_state: Optional['GameState'] = None
new_last_game_state: Optional['GameState'] = None
autosave_interval = 500  # Save persistent file every 500 new visited elements
autosave_counter = 0


@cache
def limit(n: int) -> int:
    return n * (n + 1) // 2


class GameState:
    items: list[str]
    state: list[int]
    visited: list[set[str]]
    used: list[int]
    children: set[str]

    def __init__(self, items: list[str], state: list[int], children: set[str], used: list[int]):
        self.state = state
        self.items = items
        self.children = children
        self.used = used

    def __str__(self):
        steps = [self.items[-1] + ":"]
        for i in range(len(self.state)):
            left, right = int_to_pair(self.state[i])
            if (left < 0) or (right < 0):
                continue
            steps.append(f"{self.items[left]} + {self.items[right]} = {self.items[i]}")
        return "\n".join(steps)

    def __repr__(self):
        steps = []
        for i in range(len(self.state)):
            left, right = int_to_pair(self.state[i])
            if (left < 0) or (right < 0):
                continue
            steps.append(f"{self.items[left]}={self.items[right]}={self.items[i]}")
        return "=".join(steps) + "=="

    def __len__(self):
        return len(self.state)

    def __eq__(self, other):
        return self.state == other.state

    def __lt__(self, other):
        for i in range(min(len(self.state), len(other.state))):
            if self.state[i] < other.state[i]:
                return True
            elif self.state[i] > other.state[i]:
                return False
            else:
                continue
        return False  # If it's the same starting elements, we still need to explore this state

    def __hash__(self):
        return hash(str(self.state))

    def to_list(self) -> list[tuple[str, str, str]]:
        l: list[tuple[str, str, str]] = []
        for i in range(len(self.state)):
            left, right = int_to_pair(self.state[i])
            if (left < 0) or (right < 0):
                continue
            l.append((self.items[left], self.items[right], self.items[i]))
        return l

    def get_requests(self) -> Optional[list[int]]:
        pass

    def get_children(self, depth: int) -> Optional[list[int]]:
        unused_items = self.unused_items()
        if len(unused_items) > depth + 1:  # Impossible to use all elements, since we have too few crafts left
            return None
        elif len(unused_items) > depth:  # We must start using unused elements NOW.
            states = []
            for j in range(len(unused_items)):  # For loop ordering is important. We want increasing pair_to_int order.
                for i in range(j):  # i != j. We have to use two for unused_items to decrease.
                    states.append(pair_to_int(unused_items[i], unused_items[j]))
            return states
        else:
            lower_limit = 0
            if depth == 1 and self.tail_index() != -1:  # Must use the 2nd last element, if it's not a default item.
                lower_limit = limit(len(self) - 1)

            return list(range(lower_limit, limit(len(self))))  # Regular ol' searching

    def child(self, i: int, result: str) -> Optional['GameState']:
        # Invalid indices
        if i <= self.tail_index() or i >= limit(len(self)):
            return None

        # Craft the items
        u, v = int_to_pair(i)

        # Invalid crafts / no result
        if result is None or result == "Nothing":
            return None

        # If we don't allow starting elements
        if not allow_starting_elements and result in self.items:
            return None

        # If we allow starting elements to be crafted, such as searching for optimal periodic table entry points
        # We can't craft a used starting element, because that forms a loop.
        if allow_starting_elements:
            if result == self.items[u] or result == self.items[v]:
                return None
            if result in self.items and self.used[self.items.index(result)] != 0:
                return None

        # Make sure we never craft this ever again
        if result in self.children:
            return None
        self.children.add(result)

        # Construct the new state
        new_state = self.state + [i, ]
        new_items = self.items + [result, ]
        new_used = self.used.copy()
        new_used.append(0)
        new_used[u] += 1
        new_used[v] += 1
        return GameState(new_items, new_state, self.children.copy(), new_used)

    def unused_items(self) -> list[int]:
        return [i for i in range(len(init_state), len(self.items)) if 0 == self.used[i]]

    def items_set(self) -> frozenset[str]:
        return frozenset(self.items)

    def tail_item(self) -> str:
        return self.items[-1]

    def tail_index(self) -> int:
        return self.state[-1]


init_gamestate = GameState(
                list(init_state),
                [-1 for _ in range(len(init_state))],
                set(),
                [0 for _ in range(len(init_state))]
            )

print(init_gamestate.get_children(2))
print(init_gamestate.child(0, "Lake"))