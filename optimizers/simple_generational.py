from optimizers.optimizer_interface import *


def get_children(trace: list[tuple[int, int, int]], u: int) -> set[int]:
    # Gets all elements that depends on u
    # to check for circular dependencies
    dependency_set = {u}
    for ing1, ing2, result in trace[::-1]:
        if ing1 in dependency_set or ing2 in dependency_set:
            dependency_set.add(result)
    return dependency_set


def optimize(
        target: str,
        recipe_list: OptimizerRecipeList,
        nonexistent_generation: int):
    # Generate generations
    recipe_list.generate_generations()

    todo: set[int] = {recipe_list.get_id(target)}
    done: set[int] = set()
    missing: set[int] = set()
    trace: list[tuple[int, int, int]] = []

    while len(todo) > 0:
        cur_id = max(todo, key=lambda x: recipe_list.get_generation_id(x))
        todo.remove(cur_id)

        if cur_id in done:
            continue
        done.add(cur_id)

        if recipe_list.get_generation_id(cur_id) == 0:
            continue

        if cur_id not in recipe_list.bwd:
            missing.add(cur_id)
            continue

        min_recipe: Optional[tuple[int, int]] = None
        min_cost: float = float('inf')

        # Circular dependency checking
        children = get_children(trace, cur_id)

        for u, v in recipe_list.get_ingredients_id(cur_id):
            if u in children or v in children:
                continue

            cost_u: int = 0
            cost_v: int = 0
            if u not in done and u not in todo:
                if recipe_list.get_generation_id(u) is None:
                    cost_u = nonexistent_generation
                else:
                    cost_u = recipe_list.get_generation_id(u)
            if v not in done and v not in todo:
                if recipe_list.get_generation_id(v) is None:
                    cost_v = nonexistent_generation
                else:
                    cost_v = recipe_list.get_generation_id(v)

            this_cost = max(cost_u, cost_v)  # - 1 / (min(cost_u, cost_v) + 1)

            if this_cost < min_cost:
                min_cost = this_cost
                min_recipe = (u, v)

        if min_recipe is not None:
            trace.append((min_recipe[0], min_recipe[1], cur_id))
            todo.add(min_recipe[0])
            todo.add(min_recipe[1])
        else:
            print(f"Missing {cur_id}: {recipe_list.get_name_capitalized(cur_id)}")
            missing.add(cur_id)

    print(f"Steps: {len(trace)} | {len(missing)} Missing: {missing}")
    for u, v, result in trace[::-1]:
        print(
            f"{recipe_list.get_name_capitalized(u)} + {recipe_list.get_name_capitalized(v)} -> {recipe_list.get_name_capitalized(result)}")

    # TODO: Post-processing - make sure the ordering is valid


def main():
    optimize("Firebird", savefile_to_optimizer_recipes("../yui_optimizer_savefile.json"), 1000)
    optimize("1444980", savefile_to_optimizer_recipes("../yui_optimizer_savefile.json"), 1000)
    pass


if __name__ == "__main__":
    main()
