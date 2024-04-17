import json
import sys
import time
import traceback
import urllib
from typing import Optional
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import argparse

import recipe

elements = ["Hydrogen", "Helium", "Lithium", "Beryllium", "Boron", "Carbon", "Nitrogen", "Oxygen", "Fluorine", "Neon",
            "Sodium", "Magnesium", "Aluminium", "Silicon", "Phosphorus", "Sulfur", "Chlorine", "Argon", "Potassium",
            "Calcium", "Scandium", "Titanium", "Vanadium", "Chromium", "Manganese", "Iron", "Cobalt", "Nickel",
            "Copper", "Zinc", "Gallium", "Germanium", "Arsenic", "Selenium", "Bromine", "Krypton", "Rubidium",
            "Strontium", "Yttrium", "Zirconium", "Niobium", "Molybdenum", "Technetium", "Ruthenium", "Rhodium",
            "Palladium", "Silver", "Cadmium", "Indium", "Tin", "Antimony", "Tellurium", "Iodine", "Xenon", "Caesium",
            "Barium", "Lanthanum", "Cerium", "Praseodymium", "Neodymium", "Promethium", "Samarium", "Europium",
            "Gadolinium", "Terbium", "Dysprosium", "Holmium", "Erbium", "Thulium", "Ytterbium", "Lutetium",
            "Hafnium", "Tantalum", "Tungsten", "Rhenium", "Osmium", "Iridium", "Platinum", "Gold", "Mercury",
            "Thallium", "Lead", "Bismuth", "Polonium", "Astatine", "Radon", "Francium", "Radium", "Actinium",
            "Thorium", "Protactinium", "Uranium", "Neptunium", "Plutonium", "Americium", "Curium", "Berkelium",
            "Californium", "Einsteinium", "Fermium", "Mendelevium", "Nobelium", "Lawrencium", "Rutherfordium",
            "Dubnium", "Seaborgium", "Bohrium", "Hassium", "Meitnerium", "Darmstadtium", "Roentgenium", "Copernicium",
            "Nihonium", "Flerovium", "Moscovium", "Livermorium", "Tennessine", "Oganesson"]
recipe_handler = None


def parse_craft_file(filename: str, forced_delimiter: Optional[str] = None, *, ignore_case: bool = True, strict_order: bool = False) -> list[tuple[str, str, str]]:
    with open(filename, 'r', encoding='utf-8') as file:
        crafts = file.readlines()

    # Format: ... + ... [delimiter] ...
    craft_count = 0
    crafts_parsed: list[tuple[str, str, str]] = []
    for i, craft in enumerate(crafts):
        # print(craft)
        if craft == '\n':
            continue
        craft = craft.split(" //")[0].strip()

        # Automatic delimiter detection
        delimiter = " = "
        if forced_delimiter:
            delimiter = forced_delimiter
        else:
            if " = " in craft:
                pass
            elif " -> " in craft:
                delimiter = " -> "
            else:
                print(f"Delimiter not found in line {i + 1}")
                continue
        ingredients, results = craft.split(delimiter)
        ing1, ing2 = ingredients.split(' + ')
        if strict_order:
            if ing1 > ing2:
                ing1, ing2 = ing2, ing1
        ing1, ing2, results = ing1.strip(), ing2.strip(), results.strip()
        if ignore_case:
            ing1, ing2, results = ing1.lower(), ing2.lower(), results.lower()
        crafts_parsed.append((ing1, ing2, results))
        craft_count += 1
    return crafts_parsed


def compare(original: str, new: str):
    crafts = parse_craft_file(original, ignore_case=False, strict_order=True)
    crafts2 = parse_craft_file(new, ignore_case=False, strict_order=True)
    elements = set([craft[2] for craft in crafts])
    elements2 = set([craft[2] for craft in crafts2])

    # print(set([str(craft) for craft in crafts]))
    # print(set([str(craft) for craft in crafts2]))

    elem_additions = set(elements2).difference(elements)
    print(f"Added Elements: {', '.join(elem_additions)}")
    elem_removals = set(elements).difference(elements2)
    print(f"Removed Elements: {', '.join(elem_removals)}")

    additions = []
    removals = []
    changes = {}
    for craft in crafts:
        if craft[2] not in elements2:
            removals.append(craft)
        else:
            if craft not in crafts2:
                changes[craft[2]] = [craft, None]
    for craft in crafts2:
        if craft[2] not in elements:
            additions.append(craft)
        else:
            if craft not in crafts:
                changes[craft[2]][1] = craft

    print(f"Added Crafts: {len(additions)}")
    for craft in additions:
        print(f"            {craft[0]} + {craft[1]} -> {craft[2]}")
    print(f"Removed Crafts: {len(removals)}")
    for craft in removals:
        print(f"            {craft[0]} + {craft[1]} -> {craft[2]}")
    print(f"Changed Crafts: {len(changes)}")
    for key, value in changes.items():
        print(f"Original:   {value[0][0]} + {value[0][1]} -> {value[0][2]}")
        print(f"New:        {value[1][0]} + {value[1][1]} -> {value[1][2]}")
        print()
    return


def simple_check_script(filename: str, *args, **kwargs) -> tuple[bool, bool, bool]:
    crafts = parse_craft_file(filename, *args, **kwargs)
    has_duplicates = False
    has_misplaced = False
    has_missing = False

    # Format: ... + ... -> ...
    current = {"earth": 0,
               "fire": 0,
               "water": 0,
               "wind": 0}
    crafted = set()
    possible_misplaced = set()
    for i, craft in enumerate(crafts):
        ing1, ing2, result = craft
        ing1, ing2, result = ing1.lower(), ing2.lower(), result.lower()

        if ing1 not in current:
            possible_misplaced.add(ing1)
            current[ing1] = 1
        else:
            current[ing1] += 1

        if ing2.strip() not in current:
            possible_misplaced.add(ing2)
            current[ing2] = 1
        else:
            current[ing2] += 1

        if result in crafted:
            print(f"Result {result} already exists in line {i + 1}")
            has_duplicates = True
        crafted.add(result)
        if result not in current:
            current[result] = 0

    for ingredient, value in current.items():
        if value == 0 and ingredient:
            # If the ingredient is a result, then it is fine not being used.
            print(f"Ingredient {ingredient} is not used in any recipe")

    for element in possible_misplaced:
        if element in crafted:
            print(f"Element {element} is misplaced.")
            has_misplaced = True
        else:
            print(f"Element {element} is missing.")
            has_missing = True

    return has_duplicates, has_misplaced, has_missing


def loop_check_script(filename, *args, **kwargs) -> bool:
    crafts = parse_craft_file(filename, *args, **kwargs)
    cur_elements = {"earth", "fire", "water", "wind"}
    new_order = []

    while len(cur_elements) < len(crafts) + 4:
        has_changes = False
        for i, craft in enumerate(crafts):
            ing1, ing2, result = craft
            ing1, ing2, result = ing1.lower(), ing2.lower(), result.lower()
            if ing1 in cur_elements and ing2 in cur_elements and result not in cur_elements:
                cur_elements.add(result)
                new_order.append(craft)
                has_changes = True
        if not has_changes:
            print("There is a loop in the recipe!")
            print("Correct ordering, up to the loop:")
            for craft in new_order:
                print(f"    {craft[0]} + {craft[1]} -> {craft[2]}")
            return False

    print("Correct ordering:")
    for craft in new_order:
        print(f"    {craft[0]} + {craft[1]} -> {craft[2]}")
    return True


def static_check_script(filename: str, *args, **kwargs):
    result = simple_check_script(filename, *args, **kwargs)
    if not result[0] and result[1] and not result[2]:
        print("Trying to correct for misplaced elements...")
        loop_check_script(filename, *args, **kwargs)


def dynamic_check_script(filename: str):
    global recipe_handler
    if recipe_handler is None:
        recipe_handler = recipe.RecipeHandler(("Water", "Fire", "Wind", "Earth"))

    crafts = parse_craft_file(filename)

    # Format: ... + ... -> ...
    current = {"Earth": 0,
               "Fire": 0,
               "Water": 0,
               "Wind": 0}
    craft_count = 0
    has_issues = False
    for i, craft in enumerate(crafts):
        ing1, ing2, result = craft
        true_result = recipe_handler.get_local(ing1.strip(), ing2.strip())
        if true_result != result.strip():
            has_issues = True
            print(f"Craft {ing1} + {ing2} -> {result} is not correct. The correct response is {true_result}")

    if not has_issues:
        print("All recipes are correct!")


def count_uses(filename: str):
    # ONLY USE THIS FOR A CORRECT FILE
    with open(filename, 'r') as file:
        crafts = file.readlines()

    # Format: ... + ... -> ...
    current = {"Earth": 0,
               "Fire": 0,
               "Water": 0,
               "Wind": 0}
    for i, craft in enumerate(crafts):
        if craft == '\n':
            continue
        ingredients, results = craft.split(' -> ')
        ing1, ing2 = ingredients.split(' + ')
        current[ing1.strip()] += 1
        current[ing2.strip()] += 1
        current[results.strip()] = 0

    print(current)


def parse_args():
    parser = argparse.ArgumentParser(description='Speedrun Checker')
    parser.add_argument('action', type=str, help='Action to perform')
    parser.add_argument('--file', type=str, help='File to read from')
    return parser.parse_args()


if __name__ == '__main__':
    pass
    # combine_element_pairs()
    static_check_script('speedrun.txt', ignore_case=False)
    # compare("Speedruns/curly quote a/curly_quote_a_A53.txt", "Speedruns/curly quote a/curly_quote_a_A49.txt")
    # compare("Speedruns/neal.fun/speedrun_neal.fun_B29.txt", "Speedruns/neal.fun/speedrun_neal.fun_B25_g1_ldb_g2_d4.txt")
    # static_check_script('speedrun_hashtag_fromcharcode.txt')
    # best_recipes = load_best_recipes('expanded_recipes_depth_10.txt')
    # count = 0
    # for key in best_recipes:
    #     for c in key:
    #         if c.isalnum():
    #             continue
    #         if c == ' ':
    #             continue
    #         print(key)
    #         break
    # print(count)
    # dynamic_check_script('speedrun3.txt')
    # clean("speedrun.txt", "speedrun3.txt")
    # add_element('speedrun.txt',
    #                          "Bottle",
    #             load_best_recipes('expanded_recipes_depth_10.txt'))
