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
import sqlite3

from util import int_to_pair, pair_to_int, WORD_COMBINE_CHAR_LIMIT


# Insert a recipe into the database
insert_recipe = ("""
    INSERT INTO recipes (ingredient1_id, ingredient2_id, result_id)
    SELECT ing1.id, ing2.id, result.id
    FROM items   AS result
    JOIN items   AS ing1   ON ing1.name = ?
    JOIN items   AS ing2   ON ing2.name = ?
    WHERE result.name = ?
    ON CONFLICT (ingredient1_id, ingredient2_id) DO UPDATE SET
    result_id = EXCLUDED.result_id
    """)

# Query for a recipe
query_recipe = ("""
    SELECT result.name, result.emoji
    FROM recipes
    JOIN items   AS ing1   ON ing1.id = recipes.ingredient1_id
    JOIN items   AS ing2   ON ing2.id = recipes.ingredient2_id
    JOIN items   AS result ON result.id = recipes.result_id
    WHERE ing1.name = ? AND ing2.name = ?
    """)


def load_json(file: str) -> dict:
    try:
        with open(file, "r", encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


class RecipeHandler:
    db: sqlite3.Connection
    db_location: str = "cache/recipes.db"
    closed: bool = False

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

    headers: dict[str, str] = {}

    def __init__(self, init_state):
        # Load headers
        self.headers = load_json("headers.json")["api"]

        self.db = sqlite3.connect(self.db_location)
        atexit.register(lambda: (self.close()))
        # Items table
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY,
                emoji text,
                name text UNIQUE,
                first_discovery boolean)
            """)
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS items_name_index ON items (name);
        """)

        # Recipes table
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                ingredient1_id integer REFERENCES items(id),
                ingredient2_id integer REFERENCES items(id),
                result_id integer REFERENCES items(id),
                PRIMARY KEY (ingredient1_id, ingredient2_id) )
            """)
        # For reverse searches only, so not useful for me. May be useful for other people though.
        # cur.execute("""
        #     CREATE INDEX IF NOT EXISTS recipes_result_index ON recipes (result_id)
        # """)

        # Add starting items
        for item in init_state:
            self.add_starting_item(item, "", False)

        # # Nothing is -1, local_nothing_indication is -2
        self.add_item_force_id("Nothing", '', False, -1)
        self.add_item_force_id(self.local_nothing_indication, '', False, -2)
        #
        # # Get rid of "nothing"s, if we don't trust "nothing"s.
        # if not self.trust_cache_nothing:
        #     temp_set = frozenset(self.recipes_cache.items())
        #     for ingredients, result in temp_set:
        #         if result < 0:
        #             self.recipes_cache[ingredients] = -2
        #     save_json(self.recipes_cache, self.recipes_file)

    def close(self):
        if self.closed:
            return
        self.db.commit()
        self.db.close()
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def add_item(self, item: str, emoji: str, first_discovery: bool = False):
        # print(f"Adding: {item} ({emoji})")
        cur = self.db.cursor()
        cur.execute("INSERT INTO items (emoji, name, first_discovery) VALUES (?, ?, ?) "
                    "ON CONFLICT (name) DO UPDATE SET "
                    "emoji = EXCLUDED.emoji, "
                    "first_discovery = items.first_discovery OR EXCLUDED.first_discovery",
                    (emoji, item, first_discovery))

    def add_starting_item(self, item: str, emoji: str, first_discovery: bool = False):
        # print(f"Adding: {item} ({emoji})")
        cur = self.db.cursor()
        cur.execute("INSERT INTO items (emoji, name, first_discovery) VALUES (?, ?, ?) "
                    "ON CONFLICT (name) DO NOTHING",
                    (emoji, item, first_discovery))

    def add_item_force_id(self, item: str, emoji: str, first_discovery: bool = False, overwrite_id: int = None):
        cur = self.db.cursor()
        try:
            cur.execute("INSERT INTO items (id, emoji, name, first_discovery) VALUES (?, ?, ?, ?)"
                        "ON CONFLICT (id) DO NOTHING",
                        (overwrite_id, emoji, item, first_discovery))
            self.db.commit()
        except Exception as e:
            print(e)

    def add_recipe(self, a: str, b: str, result: str):
        if a > b:
            a, b = b, a

        # print(f"Adding: {a} + {b} -> {result}")
        cur = self.db.cursor()
        cur.execute(insert_recipe, (a, b, result))

    def delete_recipe(self, a: str, b: str):
        if a > b:
            a, b = b, a
        cur = self.db.cursor()
        cur.execute("DELETE FROM recipes"
                    "JOIN items   AS ing1   ON ing1.id = recipes.ingredient1_id"
                    "JOIN items   AS ing2   ON ing2.id = recipes.ingredient2_id"
                    "WHERE ing1.name = ? AND ing2.name = ?", (a, b))

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
        self.add_item(result, emoji, new)

        # Save as the fake nothing if it's the first run
        # if result == "Nothing" and self.result_key(a, b) not in self.recipes_cache and not self.trust_first_run_nothing:
        #     result = self.local_nothing_indication
        #     result_id = self.items_id[result]

        # Recipe: A + B --> C
        self.add_recipe(a, b, result)

    def get_local(self, a: str, b: str) -> Optional[str]:
        if a > b:
            a, b = b, a
        cur = self.db.cursor()
        cur.execute(query_recipe, (a, b))
        result = cur.fetchone()
        if result:
            return result[0]
        else:
            return None

    def get_uses(self, a: str) -> list[tuple[str, str]]:
        cur = self.db.cursor()
        cur.execute("""
            SELECT ing2.name, result.name
            FROM recipes
            JOIN items   AS ing1   ON ing1.id = recipes.ingredient1_id
            JOIN items   AS ing2   ON ing2.id = recipes.ingredient2_id
            JOIN items   AS result ON result.id = recipes.result_id
            WHERE ing1.name = ?
            """, (a,))
        part1 = cur.fetchall()
        cur.execute("""
            SELECT ing1.name, result.name
            FROM recipes
            JOIN items   AS ing1   ON ing1.id = recipes.ingredient1_id
            JOIN items   AS ing2   ON ing2.id = recipes.ingredient2_id
            JOIN items   AS result ON result.id = recipes.result_id
            WHERE ing2.name = ?
            """, (a,))
        part2 = cur.fetchall()
        return part1 + part2

    def get_crafts(self, result: str) -> list[tuple[str, str]]:
        cur = self.db.cursor()
        cur.execute("""
            SELECT ing1.name, ing2.name
            FROM recipes
            JOIN items   AS ing1   ON ing1.id = recipes.ingredient1_id
            JOIN items   AS ing2   ON ing2.id = recipes.ingredient2_id
            JOIN items   AS result ON result.id = recipes.result_id
            WHERE result.name = ?
            """, (result,))
        return cur.fetchall()

    # def get_local_results_for(self, r: str) -> list[tuple[str, str]]:
    #     if r not in self.items_cache:
    #         return []
    #
    #     result_id = self.items_id[r]
    #     recipes = []
    #     for ingredients, result in self.recipes_cache.items():
    #         if result == result_id:
    #             a, b = int_to_pair(int(ingredients))
    #             recipes.append((self.items_id.inverse[a], self.items_id.inverse[b]))
    #     return recipes

    # def get_local_results_using(self, a: str) -> list[tuple[str, str, str]]:
    #     if a not in self.items_cache:
    #         return []
    #
    #     recipes = []
    #     for other in self.items_cache:
    #         result = self.recipes_cache.get(self.result_key(a, other))
    #         if not result:
    #             continue
    #         recipes.append((a, other, self.items_id.inverse[result]))
    #     return recipes

    # Adapted from analog_hors on Discord
    async def combine(self, session: aiohttp.ClientSession, a: str, b: str) -> str:
        # Query local cache
        local_result = self.get_local(a, b)
        # print(f"Local result: {a} + {b} -> {local_result}")
        if local_result and local_result != self.local_nothing_indication:
            # TODO: Censoring - temporary, to see how much of a change it has
            # print(local_result)
            # if ("slave" in local_result.lower() or
            #         "terroris" in local_result.lower() or
            #         "hamas" in local_result.lower() or
            #         local_result.lower() == 'jew' or
            #         local_result.lower() == "rape" or
            #         local_result.lower() == "rapist" or
            #         local_result.lower() == "pedophile" or
            #         local_result.lower() == "aids" or
            #         "Bin Laden" in local_result):
            #     return "Nothing"

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
        if len(a) > WORD_COMBINE_CHAR_LIMIT or len(b) > WORD_COMBINE_CHAR_LIMIT:
            return {"result": "Nothing", "emoji": "", "isNew": False}
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
                async with session.get(url, headers=self.headers) as resp:
                    # print(resp.status)
                    if resp.status == 200:
                        self.sleep_time = self.sleep_default
                        return await resp.json()
                    else:
                        print(f"Request failed with status {resp.status}", file=sys.stderr)
                        if resp.status == 500:
                            print(f"Internal Server Error when combining {a} + {b}", file=sys.stderr)

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


# Testing code / temporary code
async def main():
    pass
    # letters = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
    #            "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T",
    #            "U", "V", "W", "X", "Y", "Z"]
    #
    # letters2 = []
    # for l1 in letters:
    #     for l2 in letters:
    #         letters2.append(l1 + l2)
    #
    # rh = RecipeHandler([])
    # print(rh.get_crafts("Periodic"))
    # letter_recipes = {}
    # for two_letter_combo in letters2:
    #     uses = r.get_uses(two_letter_combo)
    #     print(two_letter_combo, uses)
    #     letter_recipes[two_letter_combo] = uses
    #
    # with open("letter_recipes.json", "w", encoding='utf-8') as f:
    #     json.dump(letter_recipes, f, ensure_ascii=False, indent=4)
    # target_words = ['Negative', 'Positive', '1']
    # with open("letter_recipes.json", "r", encoding='utf-8') as f:
    #     letter_recipes = json.load(f)
    #
    # new_letter_recipes = {}
    # for l, recipes in letter_recipes.items():
    #     r_set = set()
    #     for a, b in recipes:
    #         r_set.add((a, b))
    #     new_letter_recipes[l] = r_set
    #
    # new_2_letters = []
    # for l, recipes in new_letter_recipes.items():
    #     if len(recipes) == 0:
    #         print(l)
    #         break
    #     nothing_count = 0
    #     nothing_recipes = []
    #     valid_recipes = set()
    #     for second, result in recipes:
    #         if result == "Nothing" or result == "Nothing\t":
    #             nothing_count += 1
    #             nothing_recipes.append(second)
    #             # print(f"{l} + {second} -> {result}")
    #         else:
    #             u, v = l, second
    #             if u > v:
    #                 u, v = v, u
    #             valid_recipes.add((u, v, result))
    #     nothing_recipes.sort()
    #     nothing_ratio = nothing_count / len(recipes)
    #     new_2_letters.append((nothing_ratio, nothing_count, len(recipes), l, valid_recipes, nothing_recipes))
    #     if l == "HX":
    #         earliest_recipe = ""
    #         for u, v, r in valid_recipes:
    #             other = u if u != "HX" else v
    #             print(other)
    #             if earliest_recipe == "" or earliest_recipe > other:
    #                 print(f"New earliest: {other}")
    #                 earliest_recipe = other
    #         print(earliest_recipe)
    # new_2_letters.sort(reverse=True)
    # print("\n".join([f"{l}: {n}/{t} ({r:.2f}) - Valid: {vs if len(vs) > 0 else "None"}" for r, n, t, l, vs, ns in new_2_letters[:30]]))


if __name__ == "__main__":
    import asyncio

    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
