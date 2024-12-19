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
depth_limit = 4
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
        if self.state[-1] < 0:
            return "<Initial State>"
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

    def get_children(self, depth: int) -> list[int]:
        unused_items = self.unused_items()
        if len(unused_items) > depth + 1:  # Impossible to use all elements, since we have too few crafts left
            return []
        elif len(unused_items) > depth:  # We must start using unused elements NOW.
            states = []
            for j in range(len(unused_items)):  # For loop ordering is important. We want increasing pair_to_int order.
                for i in range(j):  # i != j. We have to use two for unused_items to decrease.
                    states.append(pair_to_int(unused_items[i], unused_items[j]))
            return states
        else:
            lower_limit = 0
            if self.tail_index != -1:
                if depth == 1:  # Must use the 2nd last element, if it's not a default item.
                    lower_limit = limit(len(self) - 1)
                else:
                    lower_limit = self.tail_index() + 1

            return list(range(lower_limit, limit(len(self))))  # Regular ol' searching

    def request_limit(self) -> int:
        return limit(len(self) - 1)

    def get_requests_index(self, depth: int) -> list[int]:
        r = self.get_children(depth)
        if self.tail_index() != -1:
            return list(filter(lambda x: x >= self.request_limit(), r))
        return r

    def get_requests(self, depth: int) -> list[tuple[str, str]]:
        r = []
        for i in self.get_requests_index(depth):
            u, v = int_to_pair(i)
            r.append((self.items[u], self.items[v]))
        return r

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


# print(init_gamestate.get_children(3))
# print(init_gamestate.get_requests_index(3))
# print(init_gamestate.get_requests(3))
# state2 = init_gamestate.child(0, "Lake")
# print(state2.get_children(2))
# print(state2.get_requests_index(2))
# print(state2.get_requests(2))


async def dls(session: aiohttp.ClientSession, init_state: GameState, depth: int):
    # Maintain the following
    new_states: list[tuple[int, GameState]] = [(depth, init_state), ]
    waiting_states: list[tuple[int, GameState]] = []
    # There is a counter for duplicate requests, so they are only requested once, but multiple states can use it
    # until it falls out of cache
    request_list: dict[tuple[str, str], int] = {}
    finished_requests: dict[tuple[str, str], tuple[str, int]] = {}

    dls_results = set()

    while len(new_states) > 0 or len(request_list) > 0:
        print("----------- New Loop ------------")
        print(new_states, waiting_states, request_list, finished_requests, sep="\n")

        if len(new_states) > 0:
            print("> Processing new state")
            # Process new states' tail
            cur_depth, cur_state = new_states.pop(-1)
            print(cur_depth, cur_state)

            if cur_depth == 0:
                print("> Found leaf state")
                print(str(cur_state))
                dls_results.add(cur_state.tail_item())
                # TODO: Process state
                continue

            # Get the requests
            requests = cur_state.get_requests(depth)
            print("Requests:", requests)
            if requests is None:
                continue

            # Add the requests to the list
            for r in requests:
                if r in finished_requests:
                    finished_requests[r] = (finished_requests[r][0], finished_requests[r][1] + 1)
                elif r in request_list:
                    request_list[r] = request_list[r] + 1
                else:
                    request_list[r] = 1

            waiting_states.append((cur_depth, cur_state))

        # Don't process requests if there's less than a single batch
        if len(new_states) != 0 and len(request_list) <= util.BATCH_SIZE:
            continue

        # Process the requests
        print("Requesting results...")
        print("Request list:", request_list)
        print("Already finished:", finished_requests)
        requests = list(request_list.keys())[-util.BATCH_SIZE:]
        print("Requests:", requests)
        results = await recipe_handler.combine_batch(session, requests)
        print("Results:", results)
        for i, r in enumerate(results):
            finished_requests[(r[0], r[1])] = (r[2], request_list[(r[0], r[1])])

        request_list = {k: v for k, v in request_list.items() if k not in requests}

        print("New finished:", finished_requests)

        new_waiting_states = []
        # Process the results
        for depth, state in waiting_states[::-1]:
            print("Matching results:", state, state.get_requests(depth), state.get_children(depth), sep="\n")
            finished = True
            for i in state.get_children(depth):
                u, v = util.int_to_pair(i)
                combination_result = None
                if i < state.request_limit():
                    # Local result
                    combination_result = await recipe_handler.combine(session, state.items[u], state.items[v])
                else:
                    try:
                        combination_result, count = finished_requests[(state.items[u], state.items[v])]
                        # print(combination_result, count)
                        if count == 1:
                            finished_requests.pop((state.items[u], state.items[v]))
                        else:
                            finished_requests[(state.items[u], state.items[v])] = (combination_result, count - 1)
                    except KeyError:
                        finished = False
                        break

                if combination_result:
                    new_state = state.child(i, combination_result)
                    if new_state:
                        new_states.append((depth - 1, new_state))

            if not finished:
                new_waiting_states.append((depth, state))

        waiting_states = new_waiting_states

    return dls_results


init_gamestate = GameState(
                list(init_state),
                [-1 for _ in range(len(init_state))],
                set(),
                [0 for _ in range(len(init_state))]
            )


async def main():
    async with aiohttp.ClientSession() as session:
        r = await dls(
            session,
            init_gamestate,
            depth_limit)
        print(len(r), r)


if __name__ == "__main__":
    # Parse arguments
    # args = parse_args()
    # init_state = tuple(args.starting_items)
    # recipe_handler = recipe.RecipeHandler(init_state)
    # depth_limit = args.depth
    # extra_depth = args.extra_depth
    # case_sensitive = args.case_sensitive
    # allow_starting_elements = args.allow_starting_elements
    # resume_last_run = args.resume_last_run

    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
