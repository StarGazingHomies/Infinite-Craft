import atexit
import os
import random
import sys
import time
import traceback
from typing import Optional
from urllib.parse import quote_plus

import aiohttp
import asyncio
import sqlite3

import util
from util import WORD_COMBINE_CHAR_LIMIT, load_json

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


class RecipeHandler:
    db: sqlite3.Connection
    db_location: str = "cache/recipes.db"
    closed: bool = False

    last_request: float = 0
    request_cooldown: float = 0.5                # 0.5s is safe for this API
    request_lock: asyncio.Lock = asyncio.Lock()
    sleep_time: float = 1.0
    sleep_default: float = 1.0
    retry_exponent: float = 2.0
    local_only: bool = True
    trust_cache_nothing: bool = True             # Trust the local cache for "Nothing" results
    trust_first_run_nothing: bool = False        # Save as "Nothing" in the first run
    local_nothing_indication: str = "Nothing\t"  # Indication of untrusted "Nothing" in the local cache
    nothing_verification: int = 3                # Verify "Nothing" n times with the API
    nothing_cooldown: float = 5.0                # Cooldown between "Nothing" verifications
    connection_timeout: float = 10.0             # Connection timeout

    print_new_recipes: bool = True

    headers: dict[str, str] = {}

    def __init__(self, init_state, **kwargs):
        # Key word arguments
        for key, value in kwargs.items():
            setattr(self, key, value)

        # Load headers
        self.headers = load_json("headers.json")["api"]

        self.db = sqlite3.connect(self.db_location, isolation_level=None)
        self.db.execute('pragma journal_mode=wal')
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

        # # Get rid of "nothing"s, if we don't trust "nothing"s.
        if not self.trust_cache_nothing:
            cur = self.db.cursor()
            cur.execute("UPDATE recipes SET result_id = -2 WHERE result_id = -1")
            self.db.commit()

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

    def get_item(self, item: str) -> Optional[tuple[str, str]]:
        cur = self.db.cursor()
        cur.execute("SELECT emoji, first_discovery FROM items WHERE name = ?", (item,))
        return cur.fetchone()

    def add_recipe(self, a: str, b: str, result: str):
        a = util.to_start_case(a)
        b = util.to_start_case(b)
        if a > b:
            a, b = b, a

        # Note that only the *INGREDIENT* will be converted to start case element.
        # because ingredient case does not matter.
        # The results will not, since the case of the resultant item may be significant.
        self.add_starting_item(a, "", False)
        self.add_starting_item(b, "", False)

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

        if self.print_new_recipes:
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
        a = util.to_start_case(a)
        b = util.to_start_case(b)
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
    async def combine(self, session: aiohttp.ClientSession, a: str, b: str, *, ignore_local: bool = False) -> str:
        # Query local cache
        local_result = None
        if not ignore_local:
            local_result = self.get_local(a, b)

        # TODO: Re-request Nothing SETTING instead of db command
        # if local_result == "Nothing":
        #     local_result = "Nothing\t"

        # print(f"Local result: {a} + {b} -> {local_result}")
        if local_result and local_result != self.local_nothing_indication:
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
            await asyncio.sleep(self.nothing_cooldown)
            if self.print_new_recipes:
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
        async with self.request_lock:
            return await self._request_pair(session, a, b, a_req, b_req)

    async def _request_pair(self, session: aiohttp.ClientSession, a: str, b: str, a_req: str, b_req: str) -> dict:
        t = time.perf_counter()
        if (t - self.last_request) < self.request_cooldown:
            time.sleep(self.request_cooldown - (t - self.last_request))
        self.last_request = time.perf_counter()

        url = f"https://neal.fun/api/infinite-craft/pair?first={a_req}&second={b_req}"

        while True:
            try:
                # print(url, type(url))
                # cookies = session.cookie_jar.filter_cookies('https://neal.fun/infinite-craft/')
                # for key, cookie in cookies.items():
                #     print('Key: "%s", Value: "%s"' % (cookie.key, cookie.value))
                async with session.get(url, headers=self.headers) as resp:
                    # print(resp.status)
                    if resp.status == 200:
                        self.sleep_time = self.sleep_default
                        return await resp.json(content_type=None)
                    else:
                        print(f"Request failed with status {resp.status}", file=sys.stderr)
                        if resp.status == 500:
                            print(f"Internal Server Error when combining {a} + {b}", file=sys.stderr)
                            with open("500s.txt", "a", encoding="utf-8") as fout:
                                fout.write(f"{a} + {b} -> 500\n")
                            return {"result": "Nothing\t", "emoji": "", "isNew": False}

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
async def random_walk(rh: RecipeHandler, session: aiohttp.ClientSession, steps: int):
    current_items = set(util.DEFAULT_STARTING_ITEMS)
    for i in range(steps):
        a = list(current_items)[random.randint(0, len(current_items) - 1)]
        b = list(current_items)[random.randint(0, len(current_items) - 1)]
        result = await rh.combine(session, a, b)
        if result != "Nothing":
            current_items.add(result)
        print(f"Step {i+1}: {a} + {b} -> {result}")
    print(f"{len(current_items)} items: {current_items}")


async def main():
    pass


if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
