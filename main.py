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

# For people who want to start with a lot more things, which makes using CLIs impractical
elements = ["Hydrogen", "Helium", "Lithium", "Beryllium", "Boron", "Carbon", "Nitrogen", "Oxygen", "Fluorine", "Neon",
            "Sodium", "Magnesium", "Aluminium", "Silicon", "Phosphorus", "Sulfur", "Chlorine", "Argon", "Potassium",
            "Calcium", "Scandium", "Titanium", "Vanadium", "Chromium", "Manganese", "Iron", "Cobalt", "Nickel",
            "Copper", "Zinc", "Gallium", "Germanium", "Arsenic", "Selenium", "Bromine", "Krypton", "Rubidium",
            "Strontium", "Yttrium", "Zirconium", "Niobium", "Molybdenum", "Technetium", "Ruthenium", "Rhodium",
            "Palladium", "Silver", "Cadmium", "Indium", "Tin", "Antimony", "Tellurium", "Iodine", "Xenon", "Cesium",
            "Barium", "Lanthanum", "Cerium", "Praseodymium", "Neodymium", "Promethium", "Samarium", "Europium",
            "Gadolinium", "Terbium", "Dysprosium", "Holmium", "Erbium", "Thulium", "Ytterbium", "Lutetium",
            "Hafnium", "Tantalum", "Tungsten", "Rhenium", "Osmium", "Iridium", "Platinum", "Gold", "Mercury",
            "Thallium", "Lead", "Bismuth", "Polonium", "Astatine", "Radon", "Francium", "Radium", "Actinium",
            "Thorium", "Protactinium", "Uranium", "Neptunium", "Plutonium", "Americium", "Curium", "Berkelium",
            "Californium", "Einsteinium", "Fermium", "Mendelevium", "Nobelium", "Lawrencium", "Rutherfordium",
            "Dubnium", "Seaborgium", "Bohrium", "Hassium", "Meitnerium", "Darmstadtium", "Roentgenium", "Copernicium",
            "Nihonium", "Flerovium", "Moscovium", "Livermorium", "Tennessine", "Oganesson"]

letters = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
           "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T",
           "U", "V", "W", "X", "Y", "Z"]

rearrange_words = ["Anagram", "Reverse", "Opposite", "Scramble", "Rearrange", "Palindrome", "Not"]

speedrun_current_words = ["Lake", "Plant", "Lily", "Volcano", "Island", "Continent",
                          "America", "USA", "Tea", "Taxes", "Filing", "File "]

letters2 = []
for l1 in letters:
    for l2 in letters:
        letters2.append(l1 + l2)

letters3 = []
for l1 in letters:
    for l2 in letters:
        for l3 in letters:
            letters3.append(l1 + l2 + l3)

# init_state = tuple(list(init_state) + elements + ["Periodic Table",])
# init_state = tuple(list(init_state) + letters + letters2)
# init_state = tuple(list(init_state) + letters + letters2 + letters3)
# init_state = tuple(list(init_state) + letters)
# init_state = tuple(list(init_state) + speedrun_current_words)
# init_state = ["Water"]

# best_recipes: dict[str, list[list[tuple[str, str, str]]]] = dict()
visited = set()
best_depths: dict[str, int] = dict()
persistent_file: str = "persistent.json"
persistent_temporary_file: str = "persistent2.json"
result_directory: str = "Results"

persistent_config = util.load_json("config.json")

recipe_handler: Optional[recipe.RecipeHandler] = recipe.RecipeHandler(init_state, **persistent_config)
optimal_handler: Optional[optimals.OptimalRecipeStorage] = optimals.OptimalRecipeStorage()
depth_limit = 3
extra_depth = 0
case_sensitive = True
allow_starting_elements = True
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

    async def child(self, session: aiohttp.ClientSession, i: int) -> Optional['GameState']:
        # Invalid indices
        if i <= self.tail_index() or i >= limit(len(self)):
            return None

        # Craft the items
        u, v = int_to_pair(i)
        craft_result = await recipe_handler.combine(session, self.items[u], self.items[v])

        # Invalid crafts / no result
        if craft_result is None or craft_result == "Nothing":
            return None

        # If we don't allow starting elements
        if not allow_starting_elements and craft_result in self.items:
            return None

        # If we allow starting elements to be crafted, such as searching for optimal periodic table entry points
        # We can't craft a used starting element, because that forms a loop.
        if allow_starting_elements:
            if craft_result == self.items[u] or craft_result == self.items[v]:
                return None
            if craft_result in self.items and self.used[self.items.index(craft_result)] != 0:
                return None

        # Make sure we never craft this ever again
        if craft_result in self.children:
            return None
        self.children.add(craft_result)

        # Construct the new state
        new_state = self.state + [i, ]
        new_items = self.items + [craft_result, ]
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


def save_optimal_recipe(state: GameState):
    # print(len(visited))
    optimal_handler.add_optimal(state.tail_item(), repr(state))


def process_node(state: GameState):
    global autosave_counter

    tail_item = state.tail_item()
    if not case_sensitive:
        tail_item = tail_item.upper()

    if tail_item not in visited:
        visited.add(tail_item)
        autosave_counter += 1
        if autosave_counter >= autosave_interval:
            autosave_counter = 0
            save_last_state()

    # Multiple recipes for the same item at same depth
    depth = len(state) - len(init_state)
    if state.tail_item() not in best_depths:
        best_depths[state.tail_item()] = depth

    if write_to_file and depth <= best_depths[state.tail_item()] + extra_depth:
        save_optimal_recipe(state)


# Depth limited search
async def dls(session: aiohttp.ClientSession, state: GameState, depth: int) -> int:
    """
    Depth limited search
    :param session: The session to use
    :param state: The current state
    :param depth: The depth remaining
    :return: The number of states processed
    """
    global last_game_state, new_last_game_state

    # Resuming
    if last_game_state is not None and len(last_game_state) >= len(state) + depth and state < last_game_state:
        # print(f"Skipping state {state}")
        return 0

    if depth == 0:  # We've reached the end of the crafts, process the node
        new_last_game_state = state
        process_node(state)
        return 1

    # 30 char limit, according to PB and laurasia
    if len(state.tail_item()) > recipe.WORD_COMBINE_CHAR_LIMIT:
        return 0

    # Even if we allowed starting element results, we're still not going to continue from such a state
    if allow_starting_elements and state.tail_item() in state.items[:-1]:
        return 0

    count = 0  # States counter
    unused_items = state.unused_items()  # Unused items
    if len(unused_items) > depth + 1:  # Impossible to use all elements, since we have too few crafts left
        return 0
    elif len(unused_items) > depth:  # We must start using unused elements NOW.
        for j in range(len(unused_items)):  # For loop ordering is important. We want increasing pair_to_int order.
            for i in range(j):  # i != j. We have to use two for unused_items to decrease.
                child = await state.child(session, pair_to_int(unused_items[i], unused_items[j]))
                if child is not None:
                    count += await dls(session, child, depth - 1)
    else:
        lower_limit = 0
        if depth == 1 and state.tail_index() != -1:  # Must use the 2nd last element, if it's not a default item.
            lower_limit = limit(len(state) - 1)

        for i in range(lower_limit, limit(len(state))):  # Regular ol' searching
            child = await state.child(session, i)
            if child is not None:
                count += await dls(session, child, depth - 1)

    return count


async def iterative_deepening_dfs(session: aiohttp.ClientSession):

    curDepth = 1
    start_time = time.perf_counter()
    if last_game_state is not None:
        curDepth = len(last_game_state) - len(init_state)
        print(f"Resuming from depth {curDepth}")
        print(last_game_state.state)

    while True:
        prev_visited = len(visited)
        print(await dls(
            session,
            GameState(
                list(init_state),
                [-1 for _ in range(len(init_state))],
                set(),
                [0 for _ in range(len(init_state))]
            ),
            curDepth))

        print(f"{curDepth}   {len(visited)}     {time.perf_counter() - start_time:.4f}")
        if curDepth >= depth_limit > 0:
            break
        # Only relevant for local files - if exhausted the outputs, stop
        if len(visited) == prev_visited and curDepth > len(last_game_state) - len(init_state):
            break
        curDepth += 1


async def main():
    # tracemalloc.start()
    if resume_last_run:
        load_last_state()
    else:
        optimal_handler.clear()

    async with aiohttp.ClientSession() as session:

        await iterative_deepening_dfs(session)


def load_last_state():
    global new_last_game_state, last_game_state, visited, best_depths
    try:
        with open(persistent_file, "r", encoding="utf-8") as file:
            last_state_json = json.load(file)
        last_game_state = GameState(
            [],
            last_state_json["GameState"],
            set(),
            []
        )
        new_last_game_state = last_game_state
        visited = set(last_state_json["BestDepths"].keys())
        best_depths = last_state_json["BestDepths"]
    except FileNotFoundError:
        last_game_state = None


@atexit.register
def save_last_state():
    print("Autosaving progress...")
    if new_last_game_state is None:
        return
    last_state_json = {
        "GameState": new_last_game_state.state,
        "BestDepths": best_depths
    }
    with open(persistent_temporary_file, "w", encoding="utf-8") as file:
        json.dump(last_state_json, file, ensure_ascii=False, indent=4)
    os.replace(persistent_temporary_file, persistent_file)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--starting-items", nargs="+", default=DEFAULT_STARTING_ITEMS, help="Starting items")
    parser.add_argument("-d", "--depth", type=int, default=10, help="Depth limit")
    parser.add_argument("-ed", "--extra_depth", type=int, default=0, help="Extra depth for laternate paths")
    parser.add_argument("--case-sensitive", action="store_true", help="Case sensitive")
    parser.add_argument("--allow-starting-elements", action="store_true", help="Allow starting elements")
    parser.add_argument("--resume-last-run", action="store_true", help="Resume last run")
    return parser.parse_args()


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
