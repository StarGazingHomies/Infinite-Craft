import json
import os, sys
import asyncio
import argparse
import time

import aiohttp

import recipe
import speedrun
import util


async def _get_all_recipes(session: aiohttp.ClientSession, rh: recipe.RecipeHandler, current: list[str]):
    total_recipe_count = len(current) * (len(current) + 1) // 2
    completed_count = 0
    local_count = 0
    t0 = time.time()

    def progress_addn(n: int = 1):
        nonlocal completed_count, t0, local_count
        completed_count += n
        cur_precentage = int(completed_count / total_recipe_count * 100)
        last_precentage = int((completed_count - n) / total_recipe_count * 100)

        try:
            cur_time = time.time()
            elapsed_time = cur_time - t0
            total_request_count = total_recipe_count - local_count
            request_count = completed_count - local_count
            estimated_time = elapsed_time / request_count * total_request_count - elapsed_time
        except ZeroDivisionError:
            estimated_time = 0

        if cur_precentage != last_precentage:
            print(f"Recipe Progress: {cur_precentage}% ({completed_count}/{total_recipe_count}) | ETA: {estimated_time:.2f}s")

    async def batch_combine(session: aiohttp.ClientSession, batch: list[tuple[str, str]]):
        result = await rh.combine_batch(session, batch, check_local=False)
        progress_addn(len(batch))
        return result

    tasks = []
    results = []

    def generate_requests():
        nonlocal local_count
        cur_requests = []
        for i, item1 in enumerate(current):
            for item2 in current[i:]:
                local_result = rh._get_local(item1, item2)
                # print(f"Local: {item1} + {item2} = {local_result}")

                if local_result and local_result != rh.local_nothing_indication:
                    results.append((item1, item2, local_result))
                    local_count += 1
                    progress_addn()
                    continue

                cur_requests.append((item1, item2))
                if len(cur_requests) >= 50:
                    yield cur_requests
                    cur_requests = []

        if cur_requests:
            yield cur_requests

    batch_results = []
    for r in generate_requests():
        batch_result = await batch_combine(session, r)
        batch_results.append(batch_result)
        print(batch_result)

    for batch_result in batch_results:
        for item1, item2, new_item in batch_result:
            results.append((item1, item2, new_item))

    return results


async def request_extra_generation(session: aiohttp.ClientSession, rh: recipe.RecipeHandler, current: list[str]):
    batch_results = await _get_all_recipes(session, rh, current)
    new_items = set()

    for item1, item2, new_item in batch_results:
        if new_item and new_item != "Nothing" and new_item not in current:
            new_items.add(new_item)

    return new_items

init_state: tuple[str, ...] = util.DEFAULT_STARTING_ITEMS

letters = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
           "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T",
           "U", "V", "W", "X", "Y", "Z"]

letters2 = []
for l1 in letters:
    for l2 in letters:
        letters2.append(l1 + l2)

letters3 = []
for l1 in letters:
    for l2 in letters:
        for l3 in letters:
            letters3.append(l1 + l2 + l3)

init_state = tuple(list(init_state) + letters + letters2 + letters3)


async def main():
    config = util.load_json("config.json")

    with recipe.RecipeHandler(util.DEFAULT_STARTING_ITEMS) as rh:
        async with aiohttp.ClientSession() as session:
            await request_extra_generation(session, rh, init_state)

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
