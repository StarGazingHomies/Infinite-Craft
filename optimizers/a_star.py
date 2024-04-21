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
    trace: list[tuple[int, int, int]]      # The steps to trace back the recipe
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
            [f"{recipe_list.get_name_capitalized(u)} + {recipe_list.get_name_capitalized(v)} -> {recipe_list.get_name_capitalized(result)}"
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
        generations = [recipe_list.get_best_minimum_bound(i) for i in self.current]
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
        while True:
            new_items = set()
            for ing1, ing2, result in self.trace[::-1]:
                if result in dependency_set:
                    continue
                if ing1 in dependency_set or ing2 in dependency_set:
                    new_items.add(result)
            if len(new_items) == 0:
                break
            dependency_set.update(new_items)
        return dependency_set

    def get_deviations(self, initial_crafts: list[int]) -> int:
        # Returns the number of deviations from the initial crafts
        return len((self.current | self.crafted).difference(initial_crafts))
        # Note that currently, the initial_crafts are nicely the first items in terms of ID,
        # so passing in the initial_crafts is not necessary. However, just in case
        # something changes, this will be kept.

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
        # print(f"Expanding element {recipe_list.get_name_capitalized(item_id)}")
        # print(f"{[recipe_list.get_name_capitalized(x) for x in item_children]} are dependent on {recipe_list.get_name_capitalized(item_id)}.")

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
            # print(f"Crafting {recipe_list.get_name_capitalized(u)} + {recipe_list.get_name_capitalized(v)} -> {recipe_list.get_name_capitalized(item_id)}")
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
        targets: list[str],
        recipe_list: OptimizerRecipeList,
        upper_bound: int,
        initial_crafts: list[int] = None,
        max_deviations: int = 128,
        *,
        print_status: bool = True,
        self_generate_heuristic: bool = False) -> list[AStarOptimizerState]:
    # Parsing args
    check_deviations = False
    if initial_crafts and max_deviations >= 0:
        check_deviations = True

    # Generate generations
    recipe_list.generate_generations()

    # Generate heuristics using the algorithm itself, for multiple targets
    # TODO: Experimental, refine this
    if self_generate_heuristic:
        # Sort by generation
        items = list(recipe_list.ids)
        items.sort(key=lambda x: recipe_list.get_generation_id(recipe_list.get_id(x)))

        for i, item in enumerate(items):
            progress = int(i / len(items) * 100)
            last_progress = int((i - 1) / len(items) * 100)
            if progress != last_progress:
                print(f"Generating heuristic: {progress}%")
            if recipe_list.get_generation_id(recipe_list.get_id(item)) == 0:
                # print(f"Skipping {item}")
                continue
            # Optimize for each individual item to get the depth
            # print(f"Optimizing for {item}")
            LIMIT = 6
            optimals = optimize(
                [item],
                recipe_list,
                LIMIT,
                initial_crafts,
                max_deviations,
                print_status=False,
                self_generate_heuristic=False)
            if len(optimals) == 0:
                print(f"Failed to optimize for {item}")
                recipe_list.depth[recipe_list.get_id(item)] = LIMIT
                continue
            depth = optimals[0].craft_count
            recipe_list.depth[recipe_list.get_id(item)] = depth
            print(f"Optimal depth for {item} is {depth}")

    # Check if targets are valid
    target_ids = [recipe_list.get_id(target) for target in targets]
    for i, target_id in enumerate(target_ids):
        if target_id is None:
            raise ValueError(f"Target {targets[i]}not found in recipe list!")
        if recipe_list.get_generation_id(target_id) is None:
            raise ValueError(f"Target {targets[i]} has no generation ID!")

    # Initialize the starting state
    start = AStarOptimizerState(recipe_list, 0, set(target_ids))

    # Priority Queue
    priority_queue: list[tuple[float, AStarOptimizerState]] = []
    visited: dict[frozenset[int], int] = {}
    processed: set[frozenset[int]] = set()
    heapq.heappush(priority_queue, (start.heuristic, start))

    # Stats
    processed_states = 0
    min_heuristic = 0
    final_states: list[AStarOptimizerState] = []
    completed = False
    completed_steps = 0

    # Main loop
    while len(priority_queue) > 0:
        _, current_state = heapq.heappop(priority_queue)
        # Stop if completed and if we are no longer optimal
        if completed and current_state.heuristic > completed_steps:
            break

        # Information
        processed_states += 1
        if print_status:
            if current_state.heuristic > min_heuristic:
                min_heuristic = current_state.heuristic
                print(f"Processed: {processed_states}, Queue length: {len(priority_queue)}, Min heuristic in queue: {min_heuristic}")
            if processed_states % 10000 == 0:
                print(f"Processed: {processed_states}, Queue length: {len(priority_queue)}, Min heuristic in queue: {min_heuristic}")

        # Save all optimal-steps states
        if current_state.is_complete():
            if print_status:
                print("Found first solution!")
            final_states.append(current_state)
            completed_steps = current_state.craft_count
            upper_bound = completed_steps
            completed = True
            continue

        # Check if the current state is already processed
        if frozenset(current_state.current) in processed:
            continue
        processed.add(frozenset(current_state.current))

        # print("Current state: ", current_state.pretty_str(recipe_list))
        # print("Current state:", current_state)
        # print("Queue length: ", len(priority_queue))
        # input()

        next_state: AStarOptimizerState
        for next_state in current_state.crafts(recipe_list):
            # Check if next state is already in priority queue? Probably not necessary

            # Check if next states exceeds upper bound (by existing recipe)
            if next_state.heuristic > upper_bound:
                continue

            # Check if the next state exceeds deviation limit
            # print(next_state.current, next_state.crafted, initial_crafts, next_state.get_deviations(initial_crafts))
            deviations = next_state.get_deviations(initial_crafts)
            if check_deviations and deviations > max_deviations:
                continue

            # Check if the next state is already visited
            current_set = frozenset(next_state.current)
            if current_set in visited:
                if visited[current_set] <= next_state.craft_count:
                    continue
            visited[current_set] = next_state.craft_count
            heapq.heappush(priority_queue, (next_state.heuristic, next_state))

    if print_status:
        print(f"Complete! {completed_steps} crafts")
        print(f"Found {len(final_states)} optimal recipes.")

        # Post-processing - make sure the ordering is correct
        for final_state in final_states:
            crafted = {0, 1, 2, 3}
            steps_copy = final_state.trace.copy()
            new_steps = []
            while len(steps_copy) > 0:
                for u, v, result in steps_copy:
                    # print(u, v, result, u in crafted, v in crafted, result in crafted)
                    if u in crafted and v in crafted:
                        crafted.add(result)
                        # print("Crafted", recipe_list.get_name_capitalized(result))
                        steps_copy.remove((u, v, result))
                        new_steps.append((u, v, result))

            for u, v, result in new_steps:
                print(
                    f"{recipe_list.get_name_capitalized(u)} + {recipe_list.get_name_capitalized(v)} -> {recipe_list.get_name_capitalized(result)}")
        print("\n---------------------------------------------------\n")

        print("Optimization complete!")

    return final_states


def main():
    # optimize("Firebird", savefile_to_optimizer_recipes("../yui_optimizer_savefile.json"), 12, self_generate_heuristic=True)
    # optimize("1444980", savefile_to_optimizer_recipes("../yui_optimizer_savefile.json"), 128)
    pass


if __name__ == "__main__":
    main()
