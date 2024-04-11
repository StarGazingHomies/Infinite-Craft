import json
import sys
import time
import traceback
import urllib
from typing import Optional
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

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


def parse_craft_file(filename: str, forced_delimiter: Optional[str] = None) -> list[tuple[str, str, str]]:
    with open(filename, 'r') as file:
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
        ing1, ing2, results = ing1.strip().lower(), ing2.strip().lower(), results.strip().lower()
        crafts_parsed.append((ing1, ing2, results))
        craft_count += 1
    return crafts_parsed


def static_check_script(filename: str):
    crafts = parse_craft_file(filename)

    # Format: ... + ... -> ...
    current = {"earth": 0,
               "fire": 0,
               "water": 0,
               "wind": 0}
    for i, craft in enumerate(crafts):
        ing1, ing2, result = craft
        if ing1.strip() not in current:
            print(f"Ingredient {ing1.strip()} not found in line {i + 1}")
        else:
            current[ing1.strip()] += 1
        if ing2.strip() not in current:
            print(f"Ingredient {ing2.strip()} not found in line {i + 1}")
        else:
            current[ing2.strip()] += 1
        if result.strip() in current:
            print(f"Result {result.strip()} already exists in line {i + 1}")

        current[result.strip()] = 0
    element_count = 0
    elements_copy = elements.copy()
    for ingredient, value in current.items():
        if value == 0 and ingredient not in elements_copy:
            print(f"Ingredient {ingredient} is not used in any recipe")
        if ingredient in elements_copy:
            element_count += 1
            elements_copy.remove(ingredient)
    # print("\n".join([str(elements_copy[i * 10:i * 10 + 10]) for i in range(11)]))
    print(len(crafts))
    # print(current)
    # current_list = list(current.items())
    # current_list.sort(key=lambda x: x[1], reverse=True)
    # for k, v in current_list:
    #     if k in elements:
    #         continue
    #     print(f"{k}: {v}")
    # print(tuple(current.keys()))
    # print(element_count)
    return current


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


def load_best_recipes(filename: str) -> dict[str, list[list[tuple[str, str, str]]]]:
    # Loading the all best recipes file for easy element adding
    with open(filename, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    recipes: dict[str, list[list[tuple[str, str, str]]]] = {}

    current_element = ""
    rec_separator = "--"
    separator = "-----------------------------------------------"
    state = 0
    current_recipe = []
    for line in lines:
        try:
            line = line[:-1]  # Ignore last \n
            if state == 0:
                # Get current element
                current_element = line
                state = 1
                continue
            if state == 1:
                state = 2
                current_recipe = []
                continue
            if state == 2:
                if line == separator:
                    state = 0
                    if current_element in recipes:
                        recipes[current_element].append(current_recipe)
                    else:
                        recipes[current_element] = [current_recipe]
                    continue
                if line == rec_separator:
                    state = 1
                    if current_element in recipes:
                        recipes[current_element].append(current_recipe)
                    else:
                        recipes[current_element] = [current_recipe]
                    continue
                # Get recipe
                elem, w = line.split(" -> ")
                u, v = elem.split(" + ", 1)
                current_recipe.append((u, v, w))
        except Exception as e:
            print(line, state)

    return recipes


def add_element(filename: str, element: str, recipes: dict[str, list[list[tuple[str, str, str]]]]):
    if element not in recipes:
        print(f"Element {element} not found in recipes")
        return

    cur_elements = static_check_script(filename)

    best_recipe = []
    best_cost = 1e9
    speedy_recipe = []
    for r in recipes[element]:
        cost = len(r)
        for u, v, w in r:
            if w in cur_elements:
                cost -= 1
            else:
                speedy_recipe.append((u, v, w))
        # print(cost, r)
        if cost < best_cost:
            best_cost = cost
            best_recipe = speedy_recipe
        speedy_recipe = []
    print(f"Best recipe for {element} has cost {best_cost}:")
    for u, v, w in best_recipe:
        print(f"{u} + {v} -> {w}")


def combine_element_pairs():
    global recipe_handler
    if recipe_handler is None:
        recipe_handler = recipe.RecipeHandler()

    results = {}
    for i in range(len(elements)):
        for j in range(i, len(elements)):
            result = recipe_handler.combine(elements[i], elements[j])
            if result != elements[i] and result != elements[j]:
                if result in results:
                    results[result].append((elements[i], elements[j]))
                else:
                    results[result] = [(elements[i], elements[j])]

    # intermediates = list(results.items())
    # print(intermediates)

    unused_elements = elements.copy()

    for k, v in results.items():
        if k in unused_elements:
            unused_elements.remove(k)
        if k not in elements:
            continue
        print(f"{k} can be obtained from {len(v)} methods")
        for u, w in v:
            print(f"{u} + {w} -> {k}")
        print()

    for e in unused_elements:
        print(f"{e} can't be made in 1 step")


def clean(filename: str, out_filename: str):
    with open(filename, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    new_lines = []
    for line in lines:
        new_line = ""
        for char in line:
            if 32 <= ord(char) < 128:
                new_line += char
        new_line = new_line.strip()
        new_lines.append(new_line)

    with open(out_filename, 'w') as file:
        file.writelines("\n".join(new_lines))


if __name__ == '__main__':
    pass
    # combine_element_pairs()
    static_check_script('speedrun.txt')
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
