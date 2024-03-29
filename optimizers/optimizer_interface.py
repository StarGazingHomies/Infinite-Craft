"""
Interfaces for optimizers to use
Provides an in-memory recipe list with O(1) lookup in both directions,
and converting from IDs to names and vice versa.

Also includes methods to quickly generate the generation of each element.
"""
from collections import deque
from typing import Optional
from bidict import bidict
import json
from util import int_to_pair, pair_to_int, DEFAULT_STARTING_ITEMS


class OptimizerRecipeList:
    ids: bidict[str, int]
    fwd: dict[int, int]
    bwd: dict[int, list[tuple[int, int]]]
    gen: Optional[dict[int, int]]

    def __init__(self, items: list[str]):
        self.fwd = {}
        self.bwd = {}
        self.ids = bidict()
        for i, item in enumerate(items):
            self.ids[item] = i
        self.gen = None

    def __str__(self):
        return f"OptimizerRecipeList with {len(self.ids)} items and {len(self.fwd)} recipes"

    def get_name(self, item_id: int) -> str:
        return self.ids.inv[item_id]

    def get_id(self, name: str) -> int:
        return self.ids[name]

    def add_recipe_id(self, result: int, ingredient1: int, ingredient2: int):
        # Add to backward
        if result not in self.bwd:
            self.bwd[result] = [(ingredient1, ingredient2)]
        else:
            self.bwd[result].append((ingredient1, ingredient2))

        # Add to forward
        self.fwd[pair_to_int(ingredient1, ingredient2)] = result

    def add_recipe_name(self, result: str, ingredient1: str, ingredient2: str):
        self.add_recipe_id(self.ids[result], self.ids[ingredient1], self.ids[ingredient2])

    def get_ingredients_id(self, result: int) -> list[tuple[int, int]]:
        try:
            return self.bwd.get(result)
        except KeyError:
            return []

    def get_result_id(self, ingredient1: int, ingredient2: int) -> int:
        try:
            return self.fwd.get(pair_to_int(ingredient1, ingredient2))
        except KeyError:
            return -1

    def generate_generations(self, init_items: list[str] = DEFAULT_STARTING_ITEMS) -> None:
        # O(V^2) time complexity

        self.gen: dict[int, int] = {}  # The generation of each element
        visited: list[int] = []        # Already processed elements
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

            # New Item Stats
            new_generation = max(self.gen[u], self.gen[v]) + 1
            new_item = self.get_result_id(u, v)

            # Only add if the item isn't visited. Generation will always be increasing since it's effectively bfs.
            if new_item and new_item >= 0 and new_item not in self.gen:
                self.gen[new_item] = new_generation
                queue.append(new_item)

        for i, item1 in enumerate(init_items):
            for j, item2 in enumerate(init_items[i:]):
                enqueue(self.get_id(item1), self.get_id(item2))

        while len(queue) > 0:
            cur = queue.popleft()
            visited.append(cur)
            for other in visited:
                enqueue(cur, other)

        return


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


if __name__ == '__main__':
    savefile_name = "../yui_optimizer_savefile.json"
    optimizer_recipes = savefile_to_optimizer_recipes(savefile_name)
    print(optimizer_recipes)
    optimizer_recipes.generate_generations()
    for item_id, generation in optimizer_recipes.gen.items():
        print(f"{optimizer_recipes.get_name(item_id)}: {generation}")
    # print(optimizer_recipes.gen)
