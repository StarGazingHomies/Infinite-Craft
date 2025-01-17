# Speedrun Optimizer
import json
import os, sys
import asyncio
import argparse
import time

import aiohttp
import urllib3.util
import yarl

import recipe
import speedrun
import util
import optimizers.a_star as a_star
import optimizers.simple_generational as simple_generational
from optimizers import addition_deletion
from optimizers.optimizer_interface import OptimizerRecipeList, optimizer_recipes_to_dict, optimizer_recipes_from_dict


# A* (bottom-up, single destination)

# The actual algorithms are implemented in the `optimizers/` folder
# The interface is implemented in `optimizer_interface.py`


async def _get_all_recipes(session: aiohttp.ClientSession, rh: recipe.RecipeHandler, current: list[str]):
    total_recipe_count = len(current) * (len(current) + 1) // 2
    completed_count = 0

    def progress_addn(n: int = 1):
        nonlocal completed_count
        completed_count += n
        cur_precentage = int(completed_count / total_recipe_count * 100)
        last_precentage = int((completed_count - n) / total_recipe_count * 100)
        if cur_precentage != last_precentage:
            print(f"Recipe Progress: {cur_precentage}% ({completed_count}/{total_recipe_count})")

    async def batch_combine(session: aiohttp.ClientSession, batch: list[tuple[str, str]]):
        result = await rh.combine_batch(session, batch, check_local=False)
        progress_addn(len(batch))
        return result

    tasks = []
    cur_requests = []
    results = []
    for i, item1 in enumerate(current):
        for item2 in current[i:]:
            local_result = rh.get_local(item1, item2)
            print(f"Local: {item1} + {item2} = {local_result}")
            if local_result and local_result != rh.local_nothing_indication and local_result not in current:
                results.append((item1, item2, local_result))
                progress_addn()
                continue

            cur_requests.append((item1, item2))
            if len(cur_requests) >= 50:
                tasks.append(batch_combine(session, cur_requests.copy()))
                cur_requests = []

    if cur_requests:
        tasks.append(batch_combine(session, cur_requests))

    batch_results = await asyncio.gather(*tasks)

    for batch_result in batch_results:
        for item1, item2, new_item in batch_result:
            results.append((item1, item2, new_item))

    return results


async def get_all_recipes(session: aiohttp.ClientSession, rh: recipe.RecipeHandler, current: list[str]):
    results = []
    batch_results = await _get_all_recipes(session, rh, current)
    for item1, item2, new_item in batch_results:
        if new_item and new_item != "Nothing" and new_item in current:
            results.append(new_item)

    print(f"Total recipes: {len(results)}")
    return results


async def request_extra_generation(session: aiohttp.ClientSession, rh: recipe.RecipeHandler, current: list[str]):
    batch_results = await _get_all_recipes(session, rh, current)
    new_items = set()

    for item1, item2, new_item in batch_results:
        if new_item and new_item != "Nothing" and new_item not in current:
            new_items.add(new_item)

    return new_items


def get_local_generation(rh: recipe.RecipeHandler, current: list[str]):
    new_items = set()
    for item1 in current:
        for item2 in current:
            new_item = rh.get_local(item1, item2)
            if new_item and new_item != "Nothing" and new_item not in current:
                new_items.add(new_item)
    return new_items


def get_all_local_recipes(rh: recipe.RecipeHandler, items: list[str]):
    total_recipe_count = len(items) * (len(items) + 1) // 2
    current_recipe = 0
    # Only store valid recipes
    recipes = []
    items_set = set([item.lower() for item in items])
    for u, item1 in enumerate(items):
        for item2 in items[u:]:
            new_item = rh.get_local(item1, item2)
            if new_item.lower() in items_set:
                recipes.append((item1, item2, new_item))
            current_recipe += 1

            cur_precentage = int(current_recipe / total_recipe_count * 100)
            last_precentage = int((current_recipe - 1) / total_recipe_count * 100)
            if cur_precentage != last_precentage:
                print(f"Recipe Progress: {cur_precentage}% ({current_recipe}/{total_recipe_count})")
    return recipes


async def initialize_optimizer(
        session: aiohttp.ClientSession,
        rh: recipe.RecipeHandler,
        items: list[str],
        extra_generations: int = 1,
        local_generations: int = 0) -> OptimizerRecipeList:
    # Get extra generations
    for i in range(extra_generations):
        new_items = await request_extra_generation(session, rh, items)
        items.extend(new_items)
        print(f"Generation {i+1} complete with {len(new_items)} new items.")

    # Get extra local generations
    for i in range(local_generations):
        new_items = get_local_generation(rh, items)
        items.extend(new_items)
        print(f"Local Generation {1 + i + extra_generations} complete with {len(new_items)} new items.")

    # Get all recipes
    recipes = await get_all_recipes(session, rh, items)
    recipe_list = OptimizerRecipeList(items)
    for recipe_data in recipes:
        recipe_list.add_recipe_name(recipe_data[2], recipe_data[0], recipe_data[1])
    return recipe_list


async def main(*,
               file: str = "speedrun.txt",
               extra_generations: int = 1,
               local_generations: int = 0,
               deviation: int = -1,
               target: list[str] = None,
               local_only: bool = False):
    # Start timer
    start_time = time.perf_counter()

    # Parse crafts file
    crafts = speedrun.parse_craft_file(file)
    craft_results = [craft[2] for craft in crafts]
    if target is None:
        target = crafts.targetList
    max_crafts = len(crafts)
    final_items_for_current_recipe = list(util.DEFAULT_STARTING_ITEMS) + craft_results

    # Request and build items cache
    config = util.load_json("config.json")

    with recipe.RecipeHandler(final_items_for_current_recipe, local_only=local_only, **config) as rh:
        async with aiohttp.ClientSession() as session:
            optimizer_recipes = await initialize_optimizer(
                session,
                rh,
                final_items_for_current_recipe,
                extra_generations,
                local_generations)

    # Generate generations
    optimizer_recipes.generate_generations()

    # Initial crafts for deviation checking
    initial_crafts = [optimizer_recipes.get_id(item) for item in list(util.DEFAULT_STARTING_ITEMS) + craft_results]

    # Artificial targets, when args just don't cut it because there's too many
    # alphabets = [chr(i) for i in range(ord('a'), ord('z') + 1)]
    # target = []
    # for c in alphabets:
    #     target.append(c)
    #     target.append(f".{c}")
    #     target.append(f"\"{c}\"")
    # print(target)

    # gen_1_pokemon = ['Lapras', 'Squirtle', 'Charizard', 'Magikarp', 'Magmar', 'Pikachu', 'Pidgey', 'Pidgeotto', 'Pidgeot', 'Gyarados', 'Raichu', 'Kingler', 'Blastoise', 'Charmander', 'Charmeleon', 'Bulbasaur', 'Ivysaur', 'Venusaur', 'Geodude', 'Graveler', 'Golem', 'Dragonite', 'Dragonair', 'Seadra', 'Omastar', 'Omanyte', 'Arcanine', 'Flareon', 'Vaporeon', 'Jolteon', 'Eevee', 'Aerodactyl', 'Moltres', 'Zapdos', 'Articuno', 'Cubone', 'Marowak', 'Oddish', 'Gloom', 'Vileplume', 'Jigglypuff', 'Wigglytuff', 'Grimer', 'Muk', 'Koffing', 'Weezing', 'Golduck', 'Psyduck', 'Weedle', 'Kakuna', 'Beedrill', 'Caterpie', 'Butterfree', 'Mewtwo', 'Mew', 'Hitmonlee', 'Hitmonchan', 'Meowth', 'Persian', 'Slowbro', 'Spearow', 'Fearow', 'Zubat', 'Golbat', 'Seaking', 'Goldeen', 'Sandshrew', 'Sandslash', 'Vulpix', 'Ninetales', 'Growlithe', 'Chansey', 'Snorlax', "Farfetch’d", 'Shellder', 'Cloyster', 'Mr. Mime', 'Arbok', 'Scyther', 'Onix', 'Ditto', 'Metapod', 'Dodrio', 'Doduo', 'Kangaskhan', 'Jynx', 'Ekans', 'Wartortle', 'Drowzee', 'Hypno', 'Poliwrath', 'Poliwhirl', 'Poliwag', 'Krabby', 'Nidoking', 'Weepinbell', 'Victreebel', 'Bellsprout', 'Raticate', 'Rattata', 'Porygon', 'Tauros', 'Slowpoke', 'Horsea', 'Nidoran', 'Nidorina', 'Nidoqueen', 'Nidorino', 'Magneton', 'Magnemite', 'Starmie', 'Staryu', 'Lickitung', 'Exeggcute', 'Exeggutor', 'Abra', 'Kadabra', 'Alakazam', 'Tentacruel', 'Tentacool', 'Pinsir', 'Clefairy', 'Clefable', 'Paras', 'Parasect', 'Gastly', 'Haunter', 'Gengar', 'Ponyta', 'Rapidash', 'Rhyhorn', 'Rhydon', 'Seel', 'Dewgong', 'Venomoth', 'Venonat', 'Diglett', 'Dugtrio', 'Electrode', 'Voltorb', 'Kabutops', 'Kabuto', 'Tangela', 'Dratini', 'Primeape', 'Machamp', 'Machoke', 'Machop', 'Mankey', 'Electabuzz', 'Missingno']
    # target = gen_1_pokemon

    # for i in target:
    #     print(f"{i}: {optimizer_recipes.get_generation_id(optimizer_recipes.get_id(i))}")

    # Run the optimizer
    print(f"Optimizing for {target}...")
    # optimizer_setup = {
    #     "targets": target,
    #     "recipe_list": optimizer_recipes_to_dict(optimizer_recipes),
    #     "upper_bound": max_crafts,
    #     "initial_crafts": initial_crafts,
    #     "max_deviations": deviation,
    # }
    # with open("optimizer_setup.json", "w", encoding="utf-8") as f:
    #     json.dump(optimizer_setup, f, indent=4, ensure_ascii=False)
    # result = addition_deletion.optimize(target, optimizer_recipes, max_crafts, initial_crafts, deviation)
    result = a_star.optimize(target, optimizer_recipes, max_crafts, initial_crafts, deviation)
    
    # End timer
    end_time = time.perf_counter()
    print(f"Time taken: {end_time - start_time:.3f}s")


def load_optimizer_setup(file: str):
    with open(file, "r", encoding="utf-8") as f:
        optimizer_setup = json.load(f)
    optimizer_recipes = optimizer_recipes_from_dict(optimizer_setup["recipe_list"])
    return optimizer_setup, optimizer_recipes


def benchmark_optimizer(file: str):
    optimizer_setup, optimizer_recipes = load_optimizer_setup(file)

    # Run the optimizer
    print(f"Benchmarking for {optimizer_setup['targets']}...")
    start_time = time.perf_counter()
    result = a_star.optimize(optimizer_setup["targets"],
                             optimizer_recipes,
                             optimizer_setup["upper_bound"],
                             optimizer_setup["initial_crafts"],
                             optimizer_setup["max_deviations"])
    end_time = time.perf_counter()
    print(f"Time taken: {end_time - start_time:.3f}s")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Speedrun Optimizer")
    parser.add_argument("filename",
                        type=str,
                        help="The file to read the crafts from")
    parser.add_argument("--ignore-case",
                        dest="ignore_case",
                        action="store_true",
                        default=False,
                        help="Ignore case when parsing the crafts file")
    parser.add_argument("-g", "--extra-generations",
                        dest="extra_generations",
                        type=int,
                        default=1,
                        help="The number of extra generations to generate")
    parser.add_argument("-lg", "--local-generations",
                        dest="local_generations",
                        type=int,
                        default=0,
                        help="The number of local generations to generate")
    parser.add_argument("-d", "--deviation",
                        dest="deviation",
                        type=int,
                        default=-1,
                        help="The maximum deviation from the original path, default off")
    parser.add_argument("-t", "--target",
                        dest="target",
                        type=str,
                        nargs="+",
                        help="The target item to craft")
    parser.add_argument("-l", "--local",
                        dest="local",
                        action="store_true",
                        default=False,
                        help="Use local cache instead of Neal's API")
    return parser.parse_args()


def benchmark_main():
    benchmark_optimizer("optimizer_benchmark_alphabet41_0.5_3.json")


if __name__ == '__main__':
    # benchmark_main()
    args = parse_arguments()

    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main(
        file=args.filename,
        extra_generations=args.extra_generations,
        local_generations=args.local_generations,
        deviation=args.deviation,
        target=args.target,
        local_only=args.local
    ))
