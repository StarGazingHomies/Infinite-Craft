"""
Interfaces for optimizers to use
Provides an in-memory recipe list with O(1) lookup in both directions,
and converting from IDs to names and vice versa.

Also includes generation of each element's generation
as well as converting from a save file.
"""
from collections import deque
from typing import Optional
from bidict import bidict
import json
from util import int_to_pair, pair_to_int, DEFAULT_STARTING_ITEMS


class OptimizerRecipeList:
    # Maps item name (lower case) to item id
    ids: bidict[str, int]
    # Maps ID to item name (capitalized same as items)
    id_capitalized: dict[int, str]
    # Forward recipe list
    # int_to_pair(ingredient1, ingredient2) -> result
    fwd: dict[int, int]
    # Backward recipe list
    # result -> [(ingredient1, ingredient2), (ingredient1, ingredient2)]
    bwd: dict[int, list[tuple[int, int]]]
    # Generation of each element
    # item_id -> generation
    gen: Optional[dict[int, int]]
    # Whether the generation has been generated, so nothing happens again
    gen_generated: bool = False
    # Hybrid generation of each element
    # item_id -> generation
    hybrid_gen: Optional[dict[int, int]]
    hybrid_gen_generated: bool = False
    # Depth of each element, provided by external algorithm
    depth: Optional[dict[int, int]]

    def __init__(self, items: list[str]):
        self.fwd = {}
        self.bwd = {}
        self.ids = bidict()
        self.id_capitalized = {}
        for i, item in enumerate(items):
            self.ids[item.lower()] = i
            self.id_capitalized[i] = item
        self.gen = None
        self.hybrid_gen = None
        self.depth = {}

    def __str__(self):
        return f"OptimizerRecipeList with {len(self.ids)} items and {len(self.fwd)} recipes"

    def add_item(self, item: str) -> int:
        self.ids[item.lower()] = len(self.ids)
        self.id_capitalized[len(self.ids) - 1] = item
        return len(self.ids) - 1

    def get_name(self, item_id: int) -> str:
        return self.ids.inv[item_id]

    def get_name_capitalized(self, item_id: int) -> str:
        return self.id_capitalized[item_id]

    def get_id(self, name: str) -> int:
        try:
            return self.ids[name.lower()]
        except KeyError:
            # Silently ignore, because borked savefiles yay
            # print(f"{name} not found!")
            return self.add_item(name)

    def get_generation_id(self, item_id: int) -> Optional[int]:
        if self.gen is None:
            return None
        return self.gen.get(item_id)

    def get_hybrid_generation_id(self, item_id: int) -> Optional[int]:
        if self.hybrid_gen is None:
            return None
        return self.hybrid_gen.get(item_id)

    def get_depth_id(self, item_id: int) -> Optional[int]:
        if self.depth is None:
            return None
        return self.depth.get(item_id)

    def get_best_minimum_bound(self, item_id: int) -> Optional[int]:
        bounds = []
        depth = self.get_depth_id(item_id)
        if depth:
            bounds.append(depth)
        hybrid_generation = self.get_hybrid_generation_id(item_id)
        if hybrid_generation:
            bounds.append(hybrid_generation)
        generation = self.get_generation_id(item_id)
        if generation:
            bounds.append(generation)

        if len(bounds) == 0:
            return None
        return max(bounds)

    def add_recipe_id(self, result: int, ingredient1: int, ingredient2: int):
        # Add to backward
        if result not in self.bwd:
            self.bwd[result] = [(ingredient1, ingredient2)]
        else:
            self.bwd[result].append((ingredient1, ingredient2))

        # Add to forward
        self.fwd[pair_to_int(ingredient1, ingredient2)] = result

    def add_recipe_name(self, result: str, ingredient1: str, ingredient2: str):
        self.add_recipe_id(self.get_id(result), self.get_id(ingredient1), self.get_id(ingredient2))

    def get_ingredients_id(self, result: int) -> list[tuple[int, int]]:
        try:
            return self.bwd.get(result)
        except KeyError:
            return []

    def get_result_id(self, ingredient1: int, ingredient2: int) -> int:
        try:
            return self.fwd[pair_to_int(ingredient1, ingredient2)]
        except KeyError:
            return -1

    def generate_generations(self, init_items: list[str] = DEFAULT_STARTING_ITEMS) -> None:
        # O(V^2) time complexity
        # TODO: Make this cleaner by not using a queue
        # Don't generate if it's already generated
        if self.gen_generated:
            return
        self.gen_generated = True

        self.gen: dict[int, int] = {}          # The generation of each element
        visited: list[int] = []                # Already processed elements
        for item in init_items:
            self.gen[self.get_id(item)] = 0
            visited.append(self.get_id(item))

        queue = deque()

        def enqueue(u: int, v: int):
            # What the fuck happened?
            if u not in self.gen:
                raise ValueError(f"Item {u} not in generation list")
            if v not in self.gen:
                raise ValueError(f"Item {v} not in generation list")

            # New generation is the old generation + 1
            new_generation: int = max(self.gen[u], self.gen[v]) + 1
            # The crafting result of u + v
            new_item: int = self.get_result_id(u, v)

            # Only add if the item isn't visited. Generation will always be increasing since it's effectively bfs.
            if new_item and new_item >= 0 and new_item not in self.gen:
                self.gen[new_item] = new_generation
                queue.append(new_item)

        # Initialize based on what items are available
        for i, item1 in enumerate(init_items):
            for j, item2 in enumerate(init_items[i:]):
                enqueue(self.get_id(item1), self.get_id(item2))

        while len(queue) > 0:
            cur = queue.popleft()
            visited.append(cur)
            for other in visited:
                enqueue(cur, other)

        return

    def generate_hybrid_generations(self, num_steps: int = 5, init_items: list[str] = DEFAULT_STARTING_ITEMS) -> None:
        # TODO: Hybrid - IDDFS for full steps until num_steps, then generate generations
        # Likely a better heuristic than simple generations.
        # Trading a bit more precompute for faster algorithm execution / better heuristic.
        ...


def savefile_to_optimizer_recipes(file: str) -> OptimizerRecipeList:
    with open(file, "r", encoding='utf-8') as file:
        data = json.load(file)

    recipes_raw: dict[str, list[dict]] = data["recipes"]
    elements_raw = data["elements"]

    optimizer = OptimizerRecipeList([element['text'] for element in elements_raw])

    for result, recipe_list in recipes_raw.items():
        for recipe in recipe_list:
            optimizer.add_recipe_name(result, recipe[0]['text'], recipe[1]['text'])

    return optimizer


def main():
    savefile_name = "../yui_optimizer_savefile.json"
    optimizer_recipes = savefile_to_optimizer_recipes(savefile_name)
    print(optimizer_recipes)
    optimizer_recipes.generate_generations()
    for item_id, generation in optimizer_recipes.gen.items():
        print(f"{optimizer_recipes.get_name(item_id)}: {generation}")
    print(optimizer_recipes.gen)


if __name__ == '__main__':
    main()
