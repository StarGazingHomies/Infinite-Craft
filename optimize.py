# Speedrun Optimizer
import os

import aiohttp

import recipe
import speedrun
import util
import optimizers.a_star as a_star
import optimizers.simple_generational as simple_generational
from optimizers.optimizer_interface import OptimizerRecipeList


# TODO: 2 types of optimization
# 1. In-place: No new elements, only look at subsets of original that can be crafted
# 2. Limited-depth: Allow new elements up to a certain deviation from the original path
# Algorithms:
# a) iddfs (top-down - low depth ONLY!)
# b) A* (bottom-up, single destination)

# The actual algorithms are implemented in the `optimizers/` folder
# The interface is implemented in `optimizer_interface.py`


def parse_craft_file(filename: str):
    with open(filename, 'r') as file:
        crafts_file = file.readlines()

    # Format: ... + ... -> ...
    current = {"Earth": 0,
               "Fire": 0,
               "Water": 0,
               "Wind": 0}
    craft_count = 0
    crafts: list[tuple[str, str, str]] = []
    for i, craft in enumerate(crafts_file):
        # print(craft)
        if craft == '\n' or craft[0] == "#":
            continue
        ingredients, results = craft.split(' -> ')
        ing1, ing2 = ingredients.split(' + ')
        crafts.append((ing1.strip(), ing2.strip(), results.strip()))
        craft_count += 1

        if ing1.strip() not in current:
            print(f"Ingredient {ing1.strip()} not found in line {i + 1}")
        else:
            current[ing1.strip()] += 1

        if ing2.strip() not in current:
            print(f"Ingredient {ing2.strip()} not found in line {i + 1}")
        else:
            current[ing2.strip()] += 1

        if results.strip() in current:
            print(f"Result {results.strip()} already exists in line {i + 1}")

        current[results.strip()] = 0
        # print(f'{ing1} + {ing2} -> {results}')
    return crafts


async def request_extra_generation(session: aiohttp.ClientSession, rh: recipe.RecipeHandler, current: list[str]):
    # Only one generation for now, maybe iddfs or recursion later
    new_items = set()
    for item1 in current:
        for item2 in current:
            new_item = await rh.combine(session, item1, item2)
            if new_item and new_item != "Nothing" and new_item not in current:
                new_items.add(new_item)
    return new_items


async def get_all_recipes(session: aiohttp.ClientSession, rh: recipe.RecipeHandler, items: list[str]):
    total_recipe_count = len(items) * (len(items) + 1) // 2
    current_recipe = 0
    # Only store valid recipes
    recipes = []
    items_set = set([item.lower() for item in items])
    for u, item1 in enumerate(items):
        for item2 in items[u:]:
            new_item = await rh.combine(session, item1, item2)
            if new_item.lower() in items_set:
                recipes.append((item1, item2, new_item))
            current_recipe += 1

            cur_precentage = int(current_recipe / total_recipe_count * 100)
            last_precentage = int((current_recipe - 1) / total_recipe_count * 100)
            if cur_precentage != last_precentage:
                print(f"Progress: {cur_precentage}% ({current_recipe}/{total_recipe_count})")
    return recipes


async def initialize_optimizer(
        session: aiohttp.ClientSession,
        rh: recipe.RecipeHandler,
        items: list[str],
        extra_generations: int = 1) -> OptimizerRecipeList:
    # Get extra generations
    for i in range(extra_generations):
        new_items = await request_extra_generation(session, rh, items)
        items.extend(new_items)
        print(f"Generation {i + 1} complete with {len(new_items)} new items.")

    # Get all recipes
    recipes = await get_all_recipes(session, rh, items)
    recipe_list = OptimizerRecipeList(items)
    for recipe_data in recipes:
        recipe_list.add_recipe_name(recipe_data[2], recipe_data[0], recipe_data[1])
    return recipe_list


async def main():
    # Parse crafts file
    crafts = parse_craft_file("speedrun.txt")
    craft_results = [crafts[2] for crafts in crafts]
    target = craft_results[-1]
    max_crafts = len(crafts)
    final_items_for_current_recipe = list(util.DEFAULT_STARTING_ITEMS) + craft_results
    print(final_items_for_current_recipe)

    # Request and build items cache
    headers = recipe.load_json("headers.json")["default"]
    with recipe.RecipeHandler(util.DEFAULT_STARTING_ITEMS) as rh:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://neal.fun/infinite-craft/", headers=headers) as resp:
                pass
            optimizer_recipes = await initialize_optimizer(session, rh, final_items_for_current_recipe, 1)

    # Generate generations
    optimizer_recipes.generate_generations()
    print(optimizer_recipes.gen)
    # print(optimizer_recipes.bwd)
    for result, recipes in optimizer_recipes.bwd.items():
        for i, j in recipes:
            print(f"{optimizer_recipes.get_name_capitalized(i)} + {optimizer_recipes.get_name_capitalized(j)} -> {optimizer_recipes.get_name_capitalized(result)}")
    print(optimizer_recipes)
    print(target)
    print(optimizer_recipes.get_id(target))
    print(optimizer_recipes.get_generation_id(optimizer_recipes.get_id(target)))

    # Run the optimizer
    a_star.optimize(target, optimizer_recipes, max_crafts)


if __name__ == '__main__':
    import asyncio

    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
