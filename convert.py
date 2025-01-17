import asyncio
import json
import math
import os
import sqlite3
from functools import cache
from typing import Optional

import aiohttp
import bidict

import optimals
import recipe
import util


def remove_first_discoveries(savefile: str, new_savefile: str):
    with open(savefile, "r", encoding='utf-8') as f:
        data = json.load(f)

    elements = data['elements']
    for val in elements:
        if val['discovered']:
            val['discovered'] = False
    data["elements"] = elements

    with open(new_savefile, "w", encoding='utf-8') as f:
        json.dump(data, f)


def load_save_file(file: str):
    with open(file, "r", encoding='utf-8') as f:
        data = json.load(f)
    return data


def modify_save_file(file: str, items_file: str, new_file: str):
    with open(file, "r", encoding='utf-8') as f:
        data = json.load(f)
    with open(items_file, "r", encoding='utf-8') as f:
        items = json.load(f)

    elements = data['elements']
    new_data = {}
    for i in elements:
        print(i, i['text'])
        new_data[i['text']] = i
    for key, val in items.items():
        if key in new_data:
            new_data[key]['discovered'] = val[1] or new_data[key]['discovered']
        else:
            new_data[key] = {
                "text": key,
                "emoji": val[0],
                "discovered": val[1]
            }

    new_data_2 = data.copy()
    new_data_2['elements'] = []
    new_cnt = 0
    for val in new_data.values():
        new_data_2['elements'].append(val)
        if val['discovered']:
            new_cnt += 1
    print(new_cnt)
    # print(new_data_2)

    print(len(new_data_2['elements']))

    with open(new_file, "w", encoding='utf-8') as f:
        json.dump(new_data_2, f)


# def count_recipes(file: str):
#     with open(file, "r") as f:
#         recipes = json.load(f)
#     print(len(recipes))


def convert_to_result_first(file_name):
    with open(file_name, "r") as f:
        recipes = json.load(f)
    new_recipes = {}
    for key, value in recipes.items():
        if value not in new_recipes:
            new_recipes[value] = [key]
        else:
            new_recipes[value].append(key)
    return new_recipes


def check_crafts(file: str, db: dict[str, str]):
    with open(file) as f:
        recipes = json.load(f)

    for key, value in recipes.items():
        if key not in db:
            continue
        if db[key] != value:
            key_str = key.replace('\t', ' + ')
            if "Nothing" == value or "Nothing" == db[key]:
                print(f"Conflict: {key_str} -> (stargazing) {value} vs (analog_hors) {db[key]}")


def load_best_recipe_book(file: str) -> list[set]:
    with open(file, "r", encoding='utf-8') as fin:
        lines = fin.readlines()

    recipes = [set() for _ in range(11)]
    cur_recipe = ""
    cur_recipe_depth = -1
    for line in lines:
        if line.strip() == "":
            output = cur_recipe.split(":")[1].strip()
            recipes[cur_recipe_depth].add(output)

            cur_recipe = ""
            cur_recipe_depth = -1
        else:
            cur_recipe += line
            cur_recipe_depth += 1
    sizes = [len(x) for x in recipes]
    print([sum(sizes[:i + 1]) for i in range(1, len(sizes))])
    return recipes


def check_recipes(file1, file2):
    recipe_book1 = load_best_recipe_book(file1)
    recipe_book2 = load_best_recipe_book(file2)
    for i in range(10):
        for v in recipe_book1[i]:
            if v not in recipe_book2[i]:
                print(f"Missing {v} at depth {i} in 2nd book")
        for v in recipe_book2[i]:
            if v not in recipe_book1[i]:
                print(f"Missing {v} at depth {i} in 1st book")


def pair_to_int(i: int, j: int) -> int:
    if j < i:
        i, j = j, i
    return i + (j * (j + 1)) // 2


def convert_to_id(recipes_file: str, items_file: str, output_recipes: str, output_items: str):
    with open(recipes_file, "r") as f:
        recipes = json.load(f)
    with open(items_file, "r") as f:
        items = json.load(f)

    new_items = {"Water": ["", 0, False],
                 "Fire": ["", 1, False],
                 "Wind": ["", 2, False],
                 "Earth": ["", 3, False]}
    item_ids: bidict.bidict[str, int] = bidict.bidict()
    item_ids["Nothing\t"] = -2
    item_ids["Nothing"] = -1
    item_ids["Water"] = 0
    item_ids["Fire"] = 1
    item_ids["Wind"] = 2
    item_ids["Earth"] = 3
    new_recipes = {}
    items_count = 4
    for item in items:
        if item in ("Nothing", "Nothing\t"):
            continue
        if item in new_items:
            original_id = new_items[item][1]
            new_items[item] = [items[item][0], original_id, items[item][1]]
            continue

        new_items[item] = [items[item][0], items_count, items[item][1]]
        item_ids[item] = items_count
        items_count += 1

    def new_result_key(a: str, b: str) -> str:
        id1 = item_ids[a]
        id2 = item_ids[b]
        return str(pair_to_int(id1, id2))

    for key, value in recipes.items():
        u, v = key.split("\t")
        if u in ("Nothing", "Nothing\t") or v in ("Nothing", "Nothing\t"):
            continue
        if u not in item_ids:
            new_items[u] = ["", items_count, False]
            item_ids[u] = items_count
            items_count += 1
        if v not in item_ids:
            new_items[v] = ["", items_count, False]
            item_ids[v] = items_count
            items_count += 1
        if value not in item_ids:
            new_items[value] = ["", items_count, False]
            item_ids[value] = items_count
            items_count += 1
        # print(u, v, value, u in new_items, v in new_items, value in new_items)
        # if value == "Nothing" or value == "Nothing\t":
        #     print(item_ids[value])

        new_recipes[new_result_key(u, v)] = item_ids[value]

    with open(output_items, "w", encoding='utf-8') as f:
        json.dump(new_items, f, ensure_ascii=False)

    with open(output_recipes, "w", encoding='utf-8') as f:
        json.dump(new_recipes, f, ensure_ascii=False)


def merge_lapis(file2: str):
    recipe_handler = recipe.RecipeHandler(("Water", "Fire", "Wind", "Earth"))

    with open(file2, "r", encoding="utf-8") as file:
        data = json.loads(file.read())
        elements = data["elements"]
        recipes = data["recipes"]
        for i, v in enumerate(recipes):
            if (i + 1) % 100000 == 0:
                print(f"Processed {i + 1} of {len(recipes)} recipes")
            if v is None:
                continue
            i1_index = math.floor(0.5 * (math.sqrt(8 * i + 1) - 1))
            i2_index = math.floor(i - (0.5 * i1_index * (i1_index + 1)))
            i1 = elements[i1_index]
            i2 = elements[i2_index]
            res = elements[v] if v != -1 else {"t": "Nothing\t", "e": ''}

            res_str = res["t"]
            if "e" in res:
                res_emote = res["e"]
            else:
                res_emote = None

            # print(f"Adding {i1['t']} + {i2['t']} -> {res_str} with emote {res_emote}")
            # input()
            result_id = recipe_handler.add_item(res_str, res_emote, False)
            recipe_handler.add_recipe(i1["t"], i2["t"], result_id)


def merge_old(file_r: str, file_i: str):
    recipe_handler = recipe.RecipeHandler(("Water", "Fire", "Wind", "Earth"))

    with open(file_r, "r") as f:
        recipes = json.load(f)
    with open(file_i, "r") as f:
        items = json.load(f)

    for key, value in items.items():
        recipe_handler.add_item(key, value[0], value[1])

    for key, value in recipes.items():
        u, v = key.split("\t")
        r = recipe_handler.add_item(value, "", False)
        recipe_handler.add_recipe(u, v, r)


def merge_sql(file_new: str):
    rh = recipe.RecipeHandler(("Water", "Fire", "Wind", "Earth"))

    new_db = sqlite3.connect(file_new)
    new_cursor = new_db.cursor()

    # Get everything from the items table
    new_cursor.execute("SELECT * FROM items")
    for i in new_cursor:
        rh.add_item(i[1], i[2], i[3])

    print("Finished adding all items")

    # Get everything from the recipes table, and convert them to items
    new_cursor.execute("""
            SELECT ing1.name, ing2.name, result.name
            FROM recipes
            JOIN items   AS ing1   ON ing1.id = recipes.ingredient1_id
            JOIN items   AS ing2   ON ing2.id = recipes.ingredient2_id
            JOIN items   AS result ON result.id = recipes.result_id
            """)
    num_recipes = 0
    for r in new_cursor:
        rh.add_recipe(r[0], r[1], r[2])
        num_recipes += 1
        if num_recipes % 100000 == 0:
            print(f"Processed {num_recipes} recipes")


@cache
def limit(n: int) -> int:
    return n * (n + 1) // 2


@cache
def ordered_total(cur_limit, cur_step, max_steps, init_list_size=4):
    if cur_step == max_steps:
        return 1
    if cur_limit >= limit(cur_step + init_list_size):
        return 0
    # if cur_step == max_steps - 1 and cur_step != 0:
    #     return limit(cur_step + init_list_size + 1) - limit(cur_step + init_list_size)

    # print(f"Step {cur_step} with limit {cur_limit} has {s} recipes")
    return \
            ordered_total(cur_limit + 1, cur_step + 1, max_steps, init_list_size) + \
            ordered_total(cur_limit + 1, cur_step, max_steps, init_list_size)


def ordered_total_from_current(current_state: list[int]):
    init_list_size = 0
    count = 0
    for i, val in enumerate(current_state):
        if val == -1:
            init_list_size = i + 1
            continue

        print(f"{val} + 1, {i - init_list_size}, {len(current_state) - init_list_size}, {init_list_size}")
        count += ordered_total(val + 1, i - init_list_size, len(current_state) - init_list_size, init_list_size)
    return count


def get_items(file: str):
    with open(file, "r", encoding="utf-8") as f:
        items = json.load(f)
    return items


def alpha_3_tmp(file: str, new_file: str):
    exists = set()
    for i in range(26):
        first_letter = chr(ord('A') + i)
        with open("3 letter spreadsheet/" + first_letter + ".csv", "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            values = line.split(",")
            for i in range(0, len(values), 2):
                if values[i + 1].strip() != "Yes":
                    continue

                exists.add(values[i].strip().lower())

    with open(file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    new_result = []
    include_next_line = False
    count = 0

    current_result = []
    for line in lines:
        if line.strip() == "" and include_next_line:
            include_next_line = False
            new_result.append(current_result)
            print(current_result)

        if include_next_line:
            current_result[1] += line

        word = line.split(":")[0].strip().lower()
        if line.count(":") == 1 and len(word) == 3 and all([ord('a') <= ord(x) <= ord('z') for x in word.lower()]):
            # and word not in exists:
            result = line.split(":")[0].strip()
            current_result = [result, ""]
            current_result[1] += f"{result}: "
            include_next_line = True
            count += 1

    new_result.sort()

    with open(new_file, "w", encoding="utf-8") as f:
        f.write("\n".join([x[1] for x in new_result]))


def convert_to_savefile(savefile: str, items_file: str, recipes_file: Optional[str] = None):
    with open(items_file, "r", encoding="utf-8") as f:
        items = json.load(f)

    items_reverse: dict[int, list] = {v[1]: [v[0], k, v[2]] for k, v in items.items()}

    item_count = 0
    first_discoveries_count = 0
    # ITEM_LIMIT = int(1e6)
    new_data = {"elements": [], "recipes": {}, "darkMode": True}
    for key, value in items.items():
        new_data["elements"].append({
            "text": key,
            "emoji": value[0],
            "discovered": value[2]
        })
        item_count += 1
        if value[2]:
            first_discoveries_count += 1
        # if item_count > ITEM_LIMIT:
        #     break
    print(f"Processed {item_count} items")

    recipes_limit = 12000000
    if recipes_file:
        with open(recipes_file, "r", encoding="utf-8") as f:
            recipes = json.load(f)
        i = 0
        for key, value in recipes.items():
            i += 1
            if i % 100000 == 0:
                print(f"Processed {i} of {len(recipes)} recipes")
            if i > recipes_limit:
                break
            if value < 0:
                continue
            key = int(key)
            value = int(value)
            u, v = recipe.int_to_pair(key)
            u_item = items_reverse[u]
            v_item = items_reverse[v]
            result = items_reverse[value][1]

            if u_item[1] == result or v_item[1] == result:
                continue

            u_formatted = {
                "text": u_item[1],
                "emoji": u_item[0]
            }
            v_formatted = {
                "text": v_item[1],
                "emoji": v_item[0]
            }

            craft_formatted = [u_formatted, v_formatted]

            if result in new_data["recipes"]:
                new_data["recipes"][result].append(craft_formatted)
            else:
                new_data["recipes"][result] = [craft_formatted]

    with open(savefile, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False)


def add_to_recipe_handler(items_file: str, recipes_file: str):
    with open(items_file, "r", encoding="utf-8") as f:
        items = json.load(f)
    with open(recipes_file, "r", encoding="utf-8") as f:
        recipes = json.load(f)

    rh = recipe.RecipeHandler(("Water", "Fire", "Wind", "Earth"))

    items_reverse = {v[1]: [v[0], k, v[2]] for k, v in items.items()}
    items_reverse[-1] = ["", "Nothing", False]
    items_reverse[-2] = ["", "Nothing\t", False]

    for key, value in items.items():
        rh.add_item(key, value[0], value[2])

    i = 0
    for key, value in recipes.items():
        i += 1
        if i % 100000 == 0:
            print(f"Processed {i} of {len(recipes)} recipes")
        # if value < 0:
        #     continue
        key = int(key)
        value = int(value)
        u, v = recipe.int_to_pair(key)
        u_item = items_reverse[u][1]
        v_item = items_reverse[v][1]
        result = items_reverse[value][1]
        if u_item > v_item:
            u_item, v_item = v_item, u_item  # Swap to ensure u < v
        rh.add_recipe(u_item, v_item, result)


def filter_results(result: str) -> bool:
    # 3 letter search
    if len(result) != 1:
        return False
    # for char in result.lower():
    #     if not (ord("a") <= ord(char) <= ord("z") or ord("0") <= ord(char) <= ord("9") or char in (" ", "\t", "-", ".", "_", ",", ":", "’", "'", "/")):
    #         return True
    return True
    # return not " " in result


def generate_single_best_recipe(input_file: str, output_file: str):
    print("Loading file...")
    try:
        with open(input_file, "r", encoding="utf-8") as file:
            last_state_json = json.load(file)
        best_recipes = last_state_json["BestRecipes"]
    except FileNotFoundError:
        print("File not found")
        return
    except KeyError:
        print("Invalid file")
        return
    print("File loading complete!")

    MAX_DEPTH = 16
    recipe_list = [[] for _ in range(MAX_DEPTH + 1)]
    for key, value in best_recipes.items():
        if len(value[0]) > MAX_DEPTH:
            break
        if filter_results(key):
            recipe_list[len(value[0])].append((key, value[0]))

    print("Recipes at each depth: ", [len(x) for x in recipe_list])
    print("Total recipes at each depth: ",
          [sum([len(x) for x in recipe_list[:i + 1]]) for i in range(1, len(recipe_list))])

    visited = set()
    count: int = 0
    with open(output_file, "w", encoding="utf-8") as f:
        for i in range(MAX_DEPTH + 1):
            for key, value in recipe_list[i]:
                # if len(key) != 3 or not all([ord('a') <= ord(x) <= ord('z') for x in key.lower()]):
                #     continue
                # if len(key) != 1 or not key[0].isalpha():
                #     continue
                # if key.lower() in visited:
                #     continue
                # visited.add(key.lower())
                value_str = "\n".join([f"{x[0]} + {x[1]} = {x[2]}" for x in value])
                f.write(f"{count + 1}: {key}:\n{value_str}\n\n")
                count += 1
    # with open(output_file, "w", encoding="utf-8") as f:
    #     for i in range(10):
    #         for key, value in recipe_list[i]:
    #             # if len(key) != 3 or not all([ord('a') <= ord(x) <= ord('z') for x in key.lower()]):
    #             #     continue
    #             # if key.lower() in visited:
    #             #     continue
    #             # visited.add(key.lower())
    #             f.write(f"{key}\n")


def generate_single_best_json(input_file: str, output_file: str):
    print("Loading file...")
    try:
        with open(input_file, "r", encoding="utf-8") as file:
            last_state_json = json.load(file)
        best_recipes = last_state_json["BestRecipes"]
    except FileNotFoundError:
        print("File not found")
        return
    except KeyError:
        print("Invalid file")
        return
    print("File loading complete!")

    recipe_list = {}
    for key, value in best_recipes.items():
        recipe_list[key] = value[0]

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(recipe_list, f, ensure_ascii=False)


def export_items(input_file: str, output_file: str):
    print("Loading file...")
    try:
        with open(input_file, "r", encoding="utf-8") as file:
            last_state_json = json.load(file)
        best_recipes = last_state_json["BestRecipes"]
    except FileNotFoundError:
        print("File not found")
        return
    except KeyError:
        print("Invalid file")
        return

    MAX_DEPTH = 12
    items_list = [[] for _ in range(MAX_DEPTH + 1)]
    for key, value in best_recipes.items():
        if len(value[0]) > MAX_DEPTH:
            break
        if filter_results(key):
            items_list[len(value[0])].append(key)

    print("Items at each depth: ", [len(x) for x in items_list])

    with open(output_file, "w", encoding="utf-8") as f:
        for i in range(MAX_DEPTH + 1):
            for key in items_list[i]:
                f.write(f"{i}={key}=\n")


def compare_persistent_files(file1: str, file2: str):
    with open(file1, "r", encoding="utf-8") as f:
        data1 = json.load(f)
    with open(file2, "r", encoding="utf-8") as f:
        data2 = json.load(f)

    recipes1 = data1["BestRecipes"]
    recipes2 = data2["BestRecipes"]

    missing = []

    for key, value in recipes1.items():
        if key not in recipes2:
            missing.append(key)
            continue
        depth = len(value[0])
        if depth != len(recipes2[key][0]):
            print(f"{key}: {depth} / {len(recipes2[key][0])}")

    print("\n".join(missing))
    return


def find_specific_items(file: str, items: list[str]):
    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)
    for item in items:
        if item in data["BestRecipes"]:
            print(f"{item}:\n")
            result = data["BestRecipes"][item]
            for r in result:
                print("```asciidoc")
                for a, b, c in r[:-1]:
                    print(f"{a} + {b} -> {c}")
                print(f"{r[-1][0]} + {r[-1][1]} -> {r[-1][2]}  // :: \n```\n")
            print("--------------------------")


def generate_json(input_file: str, output_file: str):
    try:
        with open(input_file, "r", encoding="utf-8") as file:
            last_state_json = json.load(file)
        best_recipes = last_state_json["BestRecipes"]
    except FileNotFoundError:
        best_recipes = {}

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(best_recipes, f, ensure_ascii=False)


def get_decent_recipe(file: str, item_names: list[str]):
    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)
    for item_name in item_names:
        if item_name in data['BestRecipes']:
            for recipe in data['BestRecipes'][item_name]:
                for a, b, c in recipe:
                    print(f"{a} + {b} -> {c}")
                print("--------------------------")
        else:
            print(f"{item_name} not found.")


def parse_pbpbpb_cancer_list(file: str) -> list[str]:
    with open(file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    cancer_list = []
    for line in lines:
        starting_bit = line.split('[')[0]
        print(starting_bit)
        print(starting_bit.split(' ')[:-4])
        cancer_list.append(" ".join(starting_bit.split(' ')[:-4]))
        print(cancer_list[-1])

    return cancer_list


cancers = ['Swamp Thing', 'Werewolf', 'Venus Flytrap', 'Flying Fish', 'Giant Venus Flytrap', 'Sharknado', 'Dust Bunny',
           'Muddy Wine', 'Steam Engine', 'Dandelion Wine', 'Dust Bowl', 'Steampunk Pirate', 'Dandelion Patch',
           'Zombie King', 'Were-tree', 'Rocky Mountains', 'Monster Truck', 'Tornado', 'Dusty Springfield', 'Flat Earth',
           'Fire Trap', 'Loch Ness Monster', 'Piranha Plant', 'Giant Dandelion', 'Flying Car', 'Funnel Cake',
           'Steam Punk', 'Paper Boat', 'Mountain Dew', 'Pickle Rick', 'Hangover', 'Flying Sushi', 'Muddy Teapot',
           'Balsamic Vinegar', 'Steamboat', 'Drunken Dragon', 'Fire Breathing Dragon', 'Flying Cow', 'Swamp Venus',
           'Netherite Sword', 'Steam Robot', 'Muddy Sushi', 'Godzilla', 'Dust Storm', 'Poison Ivy', 'Darth Vader',
           'Smoky Mountains', 'Chocolate Milk', 'Tsunami', 'Glasser', 'Flying Shark', 'Burning Man', 'Flying Frog',
           'Soggy Toast', 'Hot Air Balloon', 'Niagara Falls', 'Wish Upon A Star', 'Mr. Potato Head', 'Swampasaurus',
           'Zephyr Train', 'SpongeBob', 'Surf and Turf', 'Surfboard', 'Tea Party', 'Boiling Frog', 'Duck Sauce',
           'Dandelion', 'Mecha Dragon', 'Flying Spaghetti Monster', 'Muddy Wind Farm', 'Piggyback', 'Pterodactyl',
           'Surfing', 'Birthday Cake', 'Flying Plant', 'Flying Starfish', 'Beef Bourguignon', 'Dandelion Tea',
           'Mars Rover', 'Venus Fly Trap', 'Gone With The Wind', 'Thunderbird', 'Flying Pig',
           'Big Trouble in Little China', 'Amphibious Car', 'Cheese Wheel', 'Great Wall of China', 'Mudslide',
           'Flying Soup', 'Dandelion Soup', 'Kite Surfing', 'Unicorn', 'Sperm Whale', 'Jellyfish', 'Amphicar',
           'Chicken Noodle Soup', 'Mermaid', 'Water Rocket', 'Rainbow Trout', 'Lawnmower']


# PBPBPB: I'm just checking if first and last 2 tokens of an A or B are the same as the resulting element C.


async def try_cancer_combinations(rh: recipe.RecipeHandler, session: aiohttp.ClientSession, word1: str) -> list[
    tuple[str, str, str]]:
    results = []
    for word2 in cancers:
        result = await rh.combine(session, word1, word2)
        # print(f"Found {word1} + {word2} -> {result}")
        if word1.lower() in result.lower():
            # print(f"Found {word1} + {word2} -> {result}")
            results.append((word1, word2, result))
    return results


async def try_in_a_combinations(rh: recipe.RecipeHandler, session: aiohttp.ClientSession, wordlist: list[str]) -> list[
    tuple[str, str]]:
    results = []
    for word in wordlist:
        # print(word)
        result = await rh.combine(session, "In A", word)
        results.append((word, result))
        print(f"In A + {word} -> {result}")
        with open("in_a_results.txt", "a") as f:
            f.write(f"In A + {word} -> {result}\n")
    return results


async def main():
    async with aiohttp.ClientSession() as session:
        rh = recipe.RecipeHandler(("Water", "Fire", "Wind", "Earth"))
        # await rh.combine(session, "\"littleshy\"", "Delete the Quotation Marks")
        # await rh.combine(session, "\"littleshy\"", "Delete the Quotation Mark")
        # await rh.combine(session, "#littleshy", "Delete the Hyphen")
        with open("depth_9_items.txt", "r") as f:
            lines = f.readlines()
        items = [x.strip() for x in lines]
        await try_in_a_combinations(rh, session, items)
        # await rh.combine(session, "#TotallyNotFakeElement2", "With Spaces")
        # await rh.combine(session, "#IAmNotCreative", "With Spaces")
        # word1 = "Baby"
        # word2 = "Cake"
        # combined = f"{word1} {word2}"
        # show_combos = await try_cancer_combinations(rh, session, word1)
        # # print(show_combos)
        # stopper_combos = await try_cancer_combinations(rh, session, word2)
        # # print(stopper_combos)
        # for u1, u2, u in show_combos:
        #     for v1, v2, v in stopper_combos:
        #         result = await rh.combine(session, u, v)
        #         # print(f"Found {u} + {v} -> {result}")
        #         if combined in result:
        #             print(f"Found {combined} with {u} ({u2}) + {v} ({v2}) -> {result}")


def merge_savefile(file1: str, file2: str, output_file: str):
    with open(file1, "r", encoding="utf-8") as f:
        data1 = json.load(f)
    with open(file2, "r", encoding="utf-8") as f:
        data2 = json.load(f)

    new_data = {"elements": [], "recipes": {}, "darkMode": True}
    new_elements: dict[str, dict] = {}
    for i in data1["elements"]:
        if i["text"] not in new_elements:
            new_elements[i["text"]] = i
        else:
            new_elements[i["text"]]["discovered"] = new_elements[i["text"]]["discovered"] or i["discovered"]
    for i in data2["elements"]:
        if i["text"] not in new_elements:
            new_elements[i["text"]] = i
        else:
            new_elements[i["text"]]["discovered"] = new_elements[i["text"]]["discovered"] or i["discovered"]

    new_data["elements"] = list(new_elements.values())

    new_recipes = {}
    for key, value in data1["recipes"].items():
        if key not in new_recipes:
            new_recipes[key] = value
        else:
            new_recipes[key].extend(value)
    for key, value in data2["recipes"].items():
        if key not in new_recipes:
            new_recipes[key] = value
        else:
            new_recipes[key].extend(value)

    new_data["recipes"] = new_recipes

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False)


def find_softlocks():
    rh = recipe.RecipeHandler([])
    items_cur = rh.db.cursor()
    items_cur.execute("SELECT * FROM items")
    softlock_data = {}
    for i in items_cur:
        softlock_data[i[2]] = [0, 0]

    recipes_cur = rh.db.cursor()
    recipes_cur.execute("""
    SELECT ing1.name, ing2.name, result.name
    FROM recipes
    JOIN items   AS ing1   ON ing1.id = recipes.ingredient1_id
    JOIN items   AS ing2   ON ing2.id = recipes.ingredient2_id
    JOIN items   AS result ON result.id = recipes.result_id
    """)
    # recipes = {}
    recipes_count = 0
    for r in recipes_cur:
        recipes_count += 1
        if recipes_count % 100000 == 0:
            print(f"Processed {recipes_count} recipes")
        if r[0] in softlock_data:
            softlock_data[r[0]][1] += 1
        else:
            softlock_data[r[0]] = [0, 1]
        if r[2].lower() == r[0].lower():
            softlock_data[r[0]][0] += 1

        if r[1] in softlock_data:
            softlock_data[r[1]][1] += 1
        else:
            softlock_data[r[1]] = [0, 1]
        if r[2].lower() == r[1].lower():
            softlock_data[r[1]][0] += 1

    # print(nothing_data)
    with open("softlock_data.json", "w", encoding="utf-8") as f:
        json.dump(softlock_data, f, ensure_ascii=False)


def analyze_softlocks(file: str, persistent_file: str, *, softlock_limit=0.95):
    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)

    with open(persistent_file, "r", encoding="utf-8") as f:
        persistent_data = json.load(f)
    items_in_depth_11 = persistent_data["Visited"]
    print(len(items_in_depth_11))

    items: list[tuple[str, int, int]] = []
    for key, value in data.items():
        if value[1] <= 50:
            continue
        if len(key) > util.WORD_COMBINE_CHAR_LIMIT:
            continue
        items.append((key, value[0], value[1]))
    items.sort(key=lambda x: x[1] / x[2], reverse=True)
    for item in items:
        if item[1] <= item[2] * softlock_limit:
            break

        if item[0] in items_in_depth_11:
            # if item[0] in items_in_depth_11:
            print(f"{item[0]}: {item[1]} / {item[2]} ( {round(item[1] / item[2] * 100):.1f}% )")


def poseidons(result: str):
    rh = recipe.RecipeHandler([])
    crafts = rh.get_crafts(result)
    with open(f"{result.replace(" ", "_")}_crafts.txt", "w", encoding="utf-8") as f:
        for craft in crafts:
            f.write(f"{craft[0]}  +  {craft[1]}\n")


def count_poseidons(result: str):
    rh = recipe.RecipeHandler([])
    crafts = rh.get_crafts(result)
    ingredients = {}
    for craft in crafts:
        if craft[0] in ingredients:
            ingredients[craft[0]] += 1
        else:
            ingredients[craft[0]] = 1
        if craft[1] in ingredients:
            ingredients[craft[1]] += 1
        else:
            ingredients[craft[1]] = 1

    with open(f"{result.replace(" ", "_")}_poseidons.json", "w", encoding="utf-8") as f:
        json.dump(ingredients, f, ensure_ascii=False)


def process_poseidons(result: str, file: str):
    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = []
    for key, value in data.items():
        items.append((key, value))
    items.sort(key=lambda x: x[1], reverse=True)

    with open(f"{result.replace(" ", "_")}_poseidon_ingredients.txt", "w", encoding="utf-8") as f:
        for item in items:
            f.write(f"{item[0]}: {item[1]}\n")


def count_ingredients():
    rh = recipe.RecipeHandler([])
    recipes_cur = rh.db.cursor()
    recipes_cur.execute("""SELECT ing1.name, ing2.name, result.name FROM recipes
    JOIN items AS ing1 ON ing1.id = recipes.ingredient1_id
    JOIN items AS ing2 ON ing2.id = recipes.ingredient2_id
    JOIN items AS result ON result.id = recipes.result_id""")
    ingredients = {}
    recipe_count = 0
    for r in recipes_cur:
        recipe_count += 1
        if recipe_count % 100000 == 0:
            print(f"Processed {recipe_count} recipes")
        if r[0] in ingredients:
            ingredients[r[0]] += 1
        else:
            ingredients[r[0]] = 1
        if r[1] in ingredients:
            ingredients[r[1]] += 1
        else:
            ingredients[r[1]] = 1

    with open("occurrences.json", "w", encoding="utf-8") as f:
        json.dump(ingredients, f, ensure_ascii=False)


def process_poseidons_percentage(result: str, poseidon_file: str, occurrences_file: str):
    with open(poseidon_file, "r", encoding="utf-8") as f:
        poseidons = json.load(f)

    with open(occurrences_file, "r", encoding="utf-8") as f:
        occurrences = json.load(f)

    items = []
    for key, value in poseidons.items():
        if key in occurrences:
            items.append((key, value, occurrences[key]))
    items.sort(key=lambda x: x[1] / x[2], reverse=True)

    with open(f"{result.replace(" ", "_")}_poseidon_ingredients_percentage.txt", "w", encoding="utf-8") as f:
        for item in items:
            f.write(f"{item[0]:<30}: {item[1]:>5} / {item[2]:>5} ( {item[1] / item[2] * 100:.2f}% )\n")


def count_recipes():
    rh = recipe.RecipeHandler([])
    recipes_cur = rh.db.cursor()
    recipes_cur.execute("""SELECT ing1.name, ing2.name, result.name FROM recipes
    JOIN items AS ing1 ON ing1.id = recipes.ingredient1_id
    JOIN items AS ing2 ON ing2.id = recipes.ingredient2_id
    JOIN items AS result ON result.id = recipes.result_id""")

    result_count = {}
    recipe_count = 0
    for r in recipes_cur:
        recipe_count += 1
        if recipe_count % 100000 == 0:
            print(f"Processed {recipe_count} recipes")
        if r[2] in result_count:
            result_count[r[2]] += 1
        else:
            result_count[r[2]] = 1

    with open("result_count.json", "w", encoding="utf-8") as f:
        json.dump(result_count, f, ensure_ascii=False)


def analyze_recipes(file: str):
    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = []
    for key, value in data.items():
        if key == "Nothing" or key == "Nothing\t":
            continue
        items.append((key, value))
    items.sort(key=lambda x: x[1], reverse=True)
    for item in items[:51]:
        print(f"{item[0]}: {item[1]}")


def find_minus_claus():
    rh = recipe.RecipeHandler([])
    items_cur = rh.db.cursor()
    items_cur.execute("SELECT * FROM items")
    nothing_data = {}
    for i in items_cur:
        nothing_data[i[2]] = [0, 0]

    recipes_cur = rh.db.cursor()
    recipes_cur.execute("""
    SELECT ing1.name, ing2.name, result.name
    FROM recipes
    JOIN items   AS ing1   ON ing1.id = recipes.ingredient1_id
    JOIN items   AS ing2   ON ing2.id = recipes.ingredient2_id
    JOIN items   AS result ON result.id = recipes.result_id
    """)
    recipes = {}
    recipes_count = 0
    for r in recipes_cur:
        recipes_count += 1
        if recipes_count % 100000 == 0:
            print(f"Processed {recipes_count} recipes")
        is_nothing = False
        if r[2] == "Nothing" or r[2] == "Nothing\t":
            is_nothing = True
        if r[0] in nothing_data:
            nothing_data[r[0]][1] += 1
            if is_nothing:
                nothing_data[r[0]][0] += 1
        else:
            nothing_data[r[0]] = [0, 1]
            if is_nothing:
                nothing_data[r[0]][0] += 1
        if r[1] in nothing_data:
            nothing_data[r[1]][1] += 1
            if is_nothing:
                nothing_data[r[1]][0] += 1
        else:
            nothing_data[r[1]] = [0, 1]
            if is_nothing:
                nothing_data[r[1]][0] += 1

    # print(nothing_data)
    with open("minus_claus_data2.json", "w", encoding="utf-8") as f:
        json.dump(nothing_data, f, ensure_ascii=False)


def analyze_minus_claus(file: str, persistent_file: str):
    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)

    with open(persistent_file, "r", encoding="utf-8") as f:
        persistent_data = json.load(f)
    items_in_depth_11 = persistent_data["Visited"]
    print(len(items_in_depth_11))

    items: list[tuple[str, int, int]] = []
    for key, value in data.items():
        if value[1] <= 50:
            continue
        if len(key) > util.WORD_COMBINE_CHAR_LIMIT:
            continue
        items.append((key, value[0], value[1]))
    items.sort(key=lambda x: x[1] / x[2], reverse=True)
    for item in items:
        if item[1] <= item[2] * 0.99:
            break
        # Check if item is start case
        parts = item[0].split(" ")
        is_valid = True
        for part in parts:
            if not part[0].isalpha():
                continue
            if not part[0].isupper():
                is_valid = False
                break
            for char in part[1:]:
                if not char.isalpha():
                    continue
                if char.isupper():
                    is_valid = False
                    break
        if not is_valid and item[0] in items_in_depth_11:
            # if item[0] in items_in_depth_11:
            print(f"{item[0]}: {item[1]} / {item[2]} ( {item[1] / item[2]} )")


def analyze_tmp(file: str):
    with open(file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    items = [line.split('=')[:2] for line in lines]
    item: str
    for depth, item in items:
        if item.isnumeric():
            print(f"{depth} = {item}")


def count_FDs(file: str):
    with open(file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    rh = recipe.RecipeHandler([], db_location="Depth 12/recipes_depth12_h.db")

    depth_count = [0 for _ in range(13)]
    fd_count = [0 for _ in range(13)]
    for line in lines:
        depth = line.split('=')[0]
        word = line.split('=')[1].strip()
        result = rh.get_item(word)
        if not result:
            print(f"Could not find {word}")
            continue
        depth_count[int(depth)] += 1
        if result[1] == 1:
            fd_count[int(depth)] += 1
            print(f"{depth} = {word} = {result}")

    print(depth_count)
    print(fd_count)


def analyze_tokens(file: str):
    with open(file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    tokenizer = util.Tokenizer()
    items = [line.split('=')[:2] for line in lines]
    tokens_at_depth = [[0 for _ in range(21)] for _ in range(13)]
    for depth, item in items:
        tokens = tokenizer.tokenize(item)
        tokens_at_depth[int(depth)][len(tokens) - 1] += 1
        # print(f"{depth} -> {len(tokens)} {item}")

    for i in range(13):
        print(f"Depth {i}: {sum(tokens_at_depth[i])}")
        print(tokens_at_depth[i])


def analyze_tokens2():
    tokens_at_depth = [
        [0, 3, 6, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 9, 5, 4, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 19, 24, 4, 3, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 15, 61, 45, 6, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 35, 114, 85, 36, 4, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 70, 261, 168, 88, 31, 6, 3, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 132, 488, 506, 277, 103, 40, 14, 3, 1, 2, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 178, 944, 1256, 861, 392, 159, 64, 16, 10, 4, 1, 0, 1, 0, 0, 0, 1, 0, 0, 0],
        [0, 257, 1883, 3011, 2740, 1534, 620, 285, 101, 44, 17, 12, 6, 2, 2, 1, 0, 0, 0, 0, 2],
        [0, 301, 3484, 8350, 8899, 5808, 2783, 1228, 498, 239, 107, 51, 36, 8, 5, 3, 0, 0, 1, 2, 16],
        [0, 350, 7259, 23013, 29791, 22216, 12591, 5963, 2762, 1283, 575, 314, 167, 90, 49, 40, 16, 13, 19, 8, 59],
        [0, 200, 8298, 32391, 49590, 41253, 25765, 13632, 6687, 3208, 1711, 863, 481, 242, 153, 68, 45, 30, 24, 10,
         139], ]

    for i in range(12):
        average_tokens = sum([j * tokens_at_depth[i][j] for j in range(21)]) / sum(tokens_at_depth[i])
        print(f"Depth {i + 1}: {sum(tokens_at_depth[i])} {average_tokens}")


def analyze_folder_save(persistent_file: str, results_folder: str = "Results",
                        output_file: str = "4_letter_sequences.txt"):
    with open(persistent_file, "r", encoding="utf-8") as f:
        persistent_data = json.load(f)
    items: dict[str, int] = persistent_data["BestDepths"]
    path = os.path.join(os.getcwd(), results_folder)
    # print(path)
    count = 0
    final_result = ""
    for item, depth in items.items():
        item_recipe_file = os.path.join(path, f"{depth}", f"{util.file_sanitize(item)}.txt")
        # print(item_recipe_file)
        if len(item) != 4 or not all([ord('a') <= ord(x) <= ord('z') for x in item.lower()]):
            continue
        count += 1
        with open(item_recipe_file, "r", encoding='utf-8') as f:
            final_result += f"{count}: " + f.read()

    with open(output_file, "w") as fout:
        fout.write(final_result)


def analyze_optimal_save(output_file: str = "4_letter_sequences.txt"):
    optimal_handler: Optional[optimals.OptimalRecipeStorage] = optimals.OptimalRecipeStorage()
    count = 0
    with open(output_file, "w") as fout:
        pass
    items: list[tuple[str, str]] = []
    for item_id, item, best_recipes in optimal_handler.get_all_optimals():
        best_recipes = best_recipes.split("==")[:-1]
        first_recipe = best_recipes[0].split("=")
        if len(item) != 4 or not all([ord('a') <= ord(x) <= ord('z') for x in item.lower()]):
            continue
        count += 1
        # print(f"{item_id}: {item}:")
        item_str = f"{item}:\n"
        for i in range(0, len(first_recipe), 3):
            item_str += f"{first_recipe[i]} + {first_recipe[i + 1]} = {first_recipe[i + 2]}\n"
        items.append((item.lower(), item_str))
    items.sort()
    with open(output_file, "a") as fout:
        for _, item_str in items:
            fout.write(item_str)

    print(count)


async def new_api_test():
    addr = util.load_json("headers.json")["addr"]
    rh = recipe.RecipeHandler(util.DEFAULT_STARTING_ITEMS, request_addr=addr)
    async with aiohttp.ClientSession() as s:
        print(await rh.request_batch(s, [("Water", "Fire"), ("Water", "Water"), ("Fire", "Fire")]))


if __name__ == '__main__':
    pass
    asyncio.run(new_api_test())

    # count_recipes()
    # analyze_recipes("result_count.json")
    # poseidons()
    # count_ingredients()
    # s = "Poseidon"
    # count_poseidons(s)
    # process_poseidons(s, f"{s.replace(" ", "_")}_poseidons.json")
    # process_poseidons_percentage(s, f"{s.replace(" ", "_")}_poseidons.json", "occurrences.json")
    # analyze_folder_save("persistent.json")
    # analyze_optimal_save()
    # merge_sql("Depth 12/recipes_depth12_k.db")
    # analyze_tokens("depth12_h_results.txt")
    # analyze_tokens2()
    # analyze_minus_claus("Searches/Minus Claus/minus_claus_data2.json",
    #                     "Depth 11/persistent_depth11_pass3.json")
    # merge_sql("Depth 11/recipes_depth11_pass3.db")
    # input()
    # make_ingredients_case_insensitive()
    # if os.name == 'nt':
    #     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # asyncio.run(main())
    # export_items("Depth 12/persistent_depth12_complete.json", "Depth 12/depth12_complete_results_1char.txt")
    # generate_single_best_json("Depth 12/persistent_depth12_complete.json", "Depth 12/depth12_complete_single_best.json")

    # targets = "Clefable, Dewgong, Doduo, Exeggutor, Hypno, Machoke, Onix, Victreebel, Weezing, Arbok, Dratini, Electrode, Horsea, Jynx, Machop, Magnemite, Paras, Hitmonchan, Krabby, Pinsir, Poliwhirl, Hitmonlee, Spearow, Fearow, Tangela, Electabuzz, Kabuto, Psyduck, Bellsprout, Chansey, Poliwag, Missingno"
    # find_specific_items("Depth 12/persistent_depth12_complete.json", targets.split(", "))

    # generate_single_best_recipe("Depth 12/persistent_depth12_complete.json", "Depth 12/depth12_complete_single_best.txt")
    # compare_persistent_files("Depth 11/persistent_depth11_pass3.json", "Depth 11/persistent_depth11_pass2.json")
    # l = [10, 29, 113, 414, 1642, 7823, 39295, 209682]
    # print("\n".join([f"{l[i-1]}, {ordered_total(0, 0, i)}" for i in range(1, 9)]))
