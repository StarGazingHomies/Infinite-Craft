"""
A* Optimizer for single destination speedrun, or within a savefile
Requires already having a valid route to the destination - TODO: choose how missing recipes are handled.
Based on BRH0208's A*

Note: This is not applicable for high-density recipe books or super-high-generation recipes.
because branching factor will apply rather quickly
"""

from optimizers.optimizer_interface import OptimizerRecipeList, savefile_to_optimizer_recipes
from recipe import RecipeHandler
import heapq


class AStarOptimizerState:
    craft_count: int
    current: set[int]                      # Crafts to do
    crafted: set[int]                      # Crafts already done
    trace: list[tuple[int, int, int]]      # The trace of the state, for giving the final recipe
    heuristic: float                       # Heuristic value

    def __init__(self, recipe_list: OptimizerRecipeList, craft_count: int, current: set[int], crafted=None, trace=None):
        if trace is None:
            trace = []
        if crafted is None:
            crafted = set()
        self.craft_count = craft_count
        self.current = current
        self.crafted = crafted
        self.trace = trace
        self.heuristic = self.calc_heuristic(recipe_list)

    def __str__(self):
        return f"State with {self.craft_count} crafts and {self.current} remaining. Heuristic is {self.heuristic}"

    def pretty_str(self, recipe_list: OptimizerRecipeList):
        todo_crafts = [f"{recipe_list.get_name(x)}" for x in self.current]
        done_steps = "\n".join(
            [f"{recipe_list.get_name(u)} + {recipe_list.get_name(v)} -> {recipe_list.get_name(result)}"
             for u, v, result in self.trace])
        return f"State with {self.craft_count} crafts and {todo_crafts} remaining. Heuristic is {self.heuristic}\n" \
               f"Steps: \n{done_steps}"

    def calc_heuristic_non_admissible(self, recipe_list: OptimizerRecipeList) -> int:
        # Non-admissible heuristic: sum of generation for all elements.
        return self.craft_count + sum([recipe_list.get_generation_id(x) for x in self.current])

    def calc_heuristic_simple(self, recipe_list: OptimizerRecipeList) -> int:
        # Simple admissible heuristic: maximum generation for all elements.
        # Does not take into account repeating generations.
        return self.craft_count + max([recipe_list.get_generation_id(x) for x in self.current])

    def calc_heuristic_complex(self, recipe_list: OptimizerRecipeList) -> float:
        # Better admissible heuristic: generation for all elements.
        # Takes into account repeating generations.
        if len(self.current) == 0:
            return self.craft_count
        generations = [recipe_list.get_generation_id(i) for i in self.current]
        generations.sort()
        for i in range(1, len(generations)):
            generations[i] = max(generations[i], generations[i - 1] + 1)
        return self.craft_count + generations[-1]
        # Can possibly add craft_count in an inconsequential way,
        # such as - 0.001 * self.craft_count for self.craft_count < 1000

    calc_heuristic = calc_heuristic_complex

    def get_children(self, u: int) -> set[int]:
        # Gets all elements that depends on u
        # to check for circular dependencies
        dependency_set = {u}
        for ing1, ing2, result in self.trace[::-1]:
            if ing1 in dependency_set or ing2 in dependency_set:
                dependency_set.add(result)
        return dependency_set

    def crafts(self, recipe_list: OptimizerRecipeList) -> list['AStarOptimizerState']:
        # Returns the possible crafts from the current state
        result = []

        # Craft highest generation item
        item_id = max(self.current, key=lambda x: recipe_list.get_generation_id(x))
        item_children = self.get_children(item_id)
        # print(self.pretty_str(recipe_list))
        # print(f"{recipe_list.get_name(item_id)}: {[recipe_list.get_name(x) for x in item_children]}")

        cur_remaining = self.current.copy()
        cur_remaining.remove(item_id)

        for u, v in recipe_list.get_ingredients_id(item_id):
            # Check for circular dependencies
            if u in item_children or v in item_children:
                continue

            # Make new state
            new_items = cur_remaining.copy()
            new_crafted = self.crafted.copy()
            new_crafted.add(item_id)
            if recipe_list.get_generation_id(u) != 0 and u not in self.crafted:
                new_items.add(u)
            if recipe_list.get_generation_id(v) != 0 and v not in self.crafted:
                new_items.add(v)
            result.append(AStarOptimizerState(recipe_list,
                                              self.craft_count + 1,
                                              new_items,
                                              new_crafted,
                                              self.trace + [(u, v, item_id)]))
        return result

    def is_complete(self) -> bool:
        return len(self.current) == 0

    def __lt__(self, other):
        return self.heuristic < other.heuristic

    def __eq__(self, other):
        return self.heuristic == other.heuristic


def optimize(
        target: str,
        recipe_list: OptimizerRecipeList,
        upper_bound: int,
        initial_crafts: list[str] = None,
        max_deviations: int = 128):
    # Parsing args - TODO: implement deviation counting
    check_deviations = False
    if initial_crafts and max_deviations > 0:
        check_deviations = True

    # Generate generations
    recipe_list.generate_generations()

    target_id = recipe_list.get_id(target)
    if target_id is None:
        raise ValueError(f"Target {target} not found in recipe list")

    # Initialize the starting state
    target_gen = recipe_list.get_generation_id(target_id)
    start = AStarOptimizerState(recipe_list, 0, {target_id})

    # Priority Queue
    priority_queue: list[AStarOptimizerState] = []
    visited: dict[frozenset[int], int] = {}
    processed: set[frozenset[int]] = set()
    heapq.heappush(priority_queue, (start.heuristic, start))

    # Main loop
    while len(priority_queue) > 0:
        _, current_state = heapq.heappop(priority_queue)
        # print(f"Current: {current_state.current}, {current_state.craft_count}, {current_state.heuristic}")

        if current_state.is_complete():
            print(f"Complete! {current_state.craft_count} crafts")
            print(current_state.trace)
            for u, v, result in current_state.trace[::-1]:
                print(f"{recipe_list.get_name_capitalized(u)} + {recipe_list.get_name_capitalized(v)} -> {recipe_list.get_name_capitalized(result)}")
            break

        if frozenset(current_state.current) in processed:
            continue
        processed.add(frozenset(current_state.current))

        # print(f"Current: {current_state}")
        next_state: AStarOptimizerState
        for next_state in current_state.crafts(recipe_list):
            # print(f"Next: {next_state}")
            # Check if next state is already in priority queue? Probably not necessary

            # Check if next states exceeds upper bound (by existing recipe)
            if next_state.heuristic > upper_bound:
                continue
            current_set = frozenset(next_state.current)
            if current_set in visited:
                if visited[current_set] <= next_state.craft_count:
                    continue
            visited[current_set] = next_state.craft_count
            heapq.heappush(priority_queue, (next_state.heuristic, next_state))

        # print("Current state: ", current_state.pretty_str(recipe_list))
        print("Current state:", current_state)
        print("Queue length: ", len(priority_queue))
        # input()


def main():
    optimize("Firebird", savefile_to_optimizer_recipes("../yui_optimizer_savefile.json"), 12)
    # optimize("1444980", savefile_to_optimizer_recipes("../yui_optimizer_savefile.json"), 128)
    pass


if __name__ == "__main__":
    main()
