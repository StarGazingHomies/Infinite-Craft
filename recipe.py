import atexit
import json
import math
import os
import sys
import time
import traceback
from typing import Optional
from urllib.parse import quote_plus

import aiohttp
from bidict import bidict

# TODO: Implement a proper db, like Postgresql


WORD_TOKEN_LIMIT = 20
WORD_COMBINE_CHAR_LIMIT = 30


def pair_to_int(i: int, j: int) -> int:
    if j < i:
        i, j = j, i
    return i + (j * (j + 1)) // 2


def int_to_pair(n: int) -> tuple[int, int]:
    j = math.floor(((8 * n + 1) ** 0.5 - 1) / 2)
    i = n - (j * (j + 1)) // 2
    return i, j


def load_json(file_name):
    try:
        with open(file_name, 'r', encoding='utf-8') as fin:
            return json.load(fin)
    except FileNotFoundError:
        return {}


def save_json(dictionary, file_name):
    try:
        json.dump(dictionary, open(file_name, 'w', encoding='utf-8'), ensure_ascii=False)
    except FileNotFoundError:
        print(f"Could not write to {file_name}! Trying to create cache folder...", flush=True)
        try:
            os.mkdir("cache")  # TODO: generalize
            json.dump(dictionary, open(file_name, 'w', encoding='utf-8'), ensure_ascii=False)
        except Exception as e:
            print(f"Could not create folder or write to file: {e}", flush=True)
            print(dictionary)
    except Exception as e:
        print(f"Unrecognized Error: {e}", flush=True)
        print(dictionary)


def save_nothing(a: str, b: str, response: dict):
    file_name = f"cache/nothing/{a}+{b}.json"
    try:
        with open(file_name, 'w') as file:
            json.dump(response, file)
    except FileNotFoundError:
        try:
            os.mkdir("cache/nothing")
            with open(file_name, 'w') as file:
                json.dump(response, file)
        except Exception as e:
            print(f"Could not create folder or write to file: {e}", flush=True)
            print(response)


class RecipeHandler:
    recipes_cache: dict[str, int]
    items_cache: dict[str, tuple[str, int, bool]]
    items_id: bidict[str, int]
    recipes_changes: int = 0
    recipe_autosave_interval: int = 3000
    items_changes: int = 0
    items_autosave_interval: int = 100
    item_count: int = 0
    recipes_file: str = "cache/recipes.json"
    items_file: str = "cache/items.json"

    last_request: float = 0
    request_cooldown: float = 0.5  # 0.5s is safe for this API
    sleep_time: float = 1.0
    sleep_default: float = 1.0
    retry_exponent: float = 2.0
    local_only: bool = False
    trust_cache_nothing: bool = True  # Trust the local cache for "Nothing" results
    trust_first_run_nothing: bool = False  # Save as "Nothing" in the first run
    local_nothing_indication: str = "Nothing\t"  # Indication of untrusted "Nothing" in the local cache
    nothing_verification: int = 3  # Verify "Nothing" n times with the API
    nothing_cooldown: float = 5.0  # Cooldown between "Nothing" verifications
    connection_timeout: float = 5.0  # Connection timeout

    def __init__(self, init_state):
        self.recipes_cache = load_json(self.recipes_file)
        self.items_cache = load_json(self.items_file)
        self.items_id = bidict()

        max_id = max(self.items_cache.values(), key=lambda x: x[1])[1] if self.items_cache else 0
        self.item_count = max_id + 1

        for item, (emoji, elem_id, _) in self.items_cache.items():
            self.items_id[item] = elem_id

        for elem in init_state:
            self.add_item(elem, '', False)

        # Nothing is -1, local_nothing_indication is -2
        if "Nothing" not in self.items_cache:
            self.add_item("Nothing", '', False, -1)
        if self.local_nothing_indication not in self.items_cache:
            self.add_item(self.local_nothing_indication, '', False, -2)

        # Get rid of "nothing"s, if we don't trust "nothing"s.
        if not self.trust_cache_nothing:
            temp_set = frozenset(self.recipes_cache.items())
            for ingredients, result in temp_set:
                if result < 0:
                    self.recipes_cache[ingredients] = -2
            save_json(self.recipes_cache, self.recipes_file)

        # If we're not adding anything, we don't need to save
        if not self.local_only:
            atexit.register(lambda: save_json(self.recipes_cache, self.recipes_file))
            atexit.register(lambda: save_json(self.items_cache, self.items_file))

    def result_key(self, param1: str, param2: str) -> str:
        id1 = self.items_id[param1]
        id2 = self.items_id[param2]
        return str(pair_to_int(id1, id2))

    def add_item(self, item: str, emoji: str, first_discovery: bool = False, force_id: Optional[int] = None) -> int:
        if item not in self.items_cache:
            new_id = force_id if force_id is not None else self.item_count
            self.items_cache[item] = (emoji, new_id, first_discovery)
            self.items_id[item] = new_id
            self.items_changes += 1
            if not force_id:
                self.item_count += 1
        # Add missing emoji
        elif self.items_cache[item][0] == '' and emoji != '':
            print(f"Adding missing emoji {emoji} to {item}")
            self.items_cache[item] = (emoji, self.items_cache[item][1], self.items_cache[item][2])
            self.items_changes += 1

        if self.items_changes == self.items_autosave_interval:
            print("Autosaving items file...")
            save_json(self.items_cache, self.items_file)
            self.items_changes = 0
        return self.items_cache[item][1]

    def add_recipe(self, a: str, b: str, result: int):
        if self.result_key(a, b) not in self.recipes_cache or \
                (self.recipes_cache[
                     self.result_key(a, b)] != result and result != -2):  # -2 is local_nothing_indication
            self.recipes_cache[self.result_key(a, b)] = result
            self.recipes_changes += 1
            if self.recipes_changes >= self.recipe_autosave_interval:
                print("Autosaving recipes file...")
                save_json(self.recipes_cache, self.recipes_file)
                self.recipes_changes = 0

    def save_response(self, a: str, b: str, response: dict):
        result = response['result']
        try:
            emoji = response['emoji']
        except KeyError:
            emoji = ''
        try:
            new = response['isNew']
        except KeyError:
            new = False

        print(f"New Recipe: {a} + {b} -> {result}")
        if new:
            print(f"FIRST DISCOVERY: {a} + {b} -> {result}")

        # Items - emoji, new discovery
        result_id = self.add_item(result, emoji, new)

        # Save as the fake nothing if it's the first run
        if result == "Nothing" and self.result_key(a, b) not in self.recipes_cache and not self.trust_first_run_nothing:
            result = self.local_nothing_indication
            result_id = self.items_id[result]

        # Recipe: A + B --> C
        self.add_recipe(a, b, result_id)

    def get_local(self, a: str, b: str) -> Optional[str]:
        if self.result_key(a, b) not in self.recipes_cache:
            return None
        result = self.recipes_cache[self.result_key(a, b)]
        if result not in self.items_id.inverse:
            return None

        result_str = self.items_id.inverse[result]

        # Didn't get the emoji. Useful for upgrading from a previous version.
        if result >= 0 and self.items_cache[result_str][0] == '':
            # print(f"Missing {result} in cache!")
            # print(f"{result}!!")
            return None
        return result_str

    def get_local_results_for(self, r: str) -> list[tuple[str, str]]:
        if r not in self.items_cache:
            return []

        result_id = self.items_id[r]
        recipes = []
        for ingredients, result in self.recipes_cache.items():
            if result == result_id:
                a, b = int_to_pair(int(ingredients))
                recipes.append((self.items_id.inverse[a], self.items_id.inverse[b]))
        return recipes

    def get_local_results_using(self, a: str) -> list[tuple[str, str, str]]:
        if a not in self.items_cache:
            return []

        recipes = []
        for other in self.items_cache:
            result = self.recipes_cache.get(self.result_key(a, other))
            if not result:
                continue
            recipes.append((a, other, self.items_id.inverse[result]))
        return recipes

    # Adapted from analog_hors on Discord
    async def combine(self, session: aiohttp.ClientSession, a: str, b: str) -> str:
        # Query local cache
        local_result = self.get_local(a, b)
        # print(f"Local result: {a} + {b} -> {local_result}")
        if local_result and local_result != self.local_nothing_indication:

            # TODO: Censoring - temporary, to see how much of a change it has
            # print(local_result)
            if ("slave" in local_result.lower() or
                    "terroris" in local_result.lower() or
                    "hamas" in local_result.lower() or
                    local_result.lower() == 'jew' or
                    local_result.lower() == "rape" or
                    local_result.lower() == "rapist" or
                    local_result.lower() == "pedophile" or
                    local_result.lower() == "aids" or
                    "Bin Laden" in local_result):
                return "Nothing"

            return local_result

        if self.local_only:
            return "Nothing"

        # print(f"Requesting {a} + {b}", flush=True)
        r = await self.request_pair(session, a, b)

        nothing_count = 1
        while (local_result != self.local_nothing_indication and  # "Nothing" in local cache is long, long ago
               r['result'] == "Nothing" and  # Still getting "Nothing" from the API
               nothing_count < self.nothing_verification):  # We haven't verified "Nothing" enough times
            # Request again to verify, just in case...
            # Increases time taken on requests but should be worth it.
            # Also note that this can't be asynchronous due to all the optimizations I made assuming a search order
            time.sleep(self.nothing_cooldown)
            print("Re-requesting Nothing result...", flush=True)

            r = await self.request_pair(session, a, b)

            nothing_count += 1

        self.save_response(a, b, r)
        return r['result']

    async def request_pair(self, session: aiohttp.ClientSession, a: str, b: str) -> dict:
        # with requestLock:
        a_req = quote_plus(a)
        b_req = quote_plus(b)

        # Don't request too quickly. Have been 429'd way too many times
        t = time.perf_counter()
        if (t - self.last_request) < self.request_cooldown:
            time.sleep(self.request_cooldown - (t - self.last_request))
        self.last_request = time.perf_counter()

        url = f"https://neal.fun/api/infinite-craft/pair?first={a_req}&second={b_req}"

        while True:
            try:
                # print(url, type(url))
                async with session.get(url) as resp:
                    # print(resp.status)
                    if resp.status == 200:
                        self.sleep_time = self.sleep_default
                        return await resp.json()
                    else:
                        print(f"Request failed with status {resp.status}", file=sys.stderr)
                        time.sleep(self.sleep_time)
                        self.sleep_time *= self.retry_exponent
                        print("Retrying...", flush=True)
            except Exception as e:
                # Handling more than just that one error
                print("Unrecognized Error: ", e, file=sys.stderr)
                traceback.print_exc()
                time.sleep(self.sleep_time)
                self.sleep_time *= self.retry_exponent
                print("Retrying...", flush=True)
