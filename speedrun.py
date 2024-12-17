import argparse
import asyncio
import os
import re
import sys
from typing import Optional

import aiohttp

import recipe
import util

# elements = ["Hydrogen", "Helium", "Lithium", "Beryllium", "Boron", "Carbon", "Nitrogen", "Oxygen", "Fluorine", "Neon",
#             "Sodium", "Magnesium", "Aluminium", "Silicon", "Phosphorus", "Sulfur", "Chlorine", "Argon", "Potassium",
#             "Calcium", "Scandium", "Titanium", "Vanadium", "Chromium", "Manganese", "Iron", "Cobalt", "Nickel",
#             "Copper", "Zinc", "Gallium", "Germanium", "Arsenic", "Selenium", "Bromine", "Krypton", "Rubidium",
#             "Strontium", "Yttrium", "Zirconium", "Niobium", "Molybdenum", "Technetium", "Ruthenium", "Rhodium",
#             "Palladium", "Silver", "Cadmium", "Indium", "Tin", "Antimony", "Tellurium", "Iodine", "Xenon", "Caesium",
#             "Barium", "Lanthanum", "Cerium", "Praseodymium", "Neodymium", "Promethium", "Samarium", "Europium",
#             "Gadolinium", "Terbium", "Dysprosium", "Holmium", "Erbium", "Thulium", "Ytterbium", "Lutetium",
#             "Hafnium", "Tantalum", "Tungsten", "Rhenium", "Osmium", "Iridium", "Platinum", "Gold", "Mercury",
#             "Thallium", "Lead", "Bismuth", "Polonium", "Astatine", "Radon", "Francium", "Radium", "Actinium",
#             "Thorium", "Protactinium", "Uranium", "Neptunium", "Plutonium", "Americium", "Curium", "Berkelium",
#             "Californium", "Einsteinium", "Fermium", "Mendelevium", "Nobelium", "Lawrencium", "Rutherfordium",
#             "Dubnium", "Seaborgium", "Bohrium", "Hassium", "Meitnerium", "Darmstadtium", "Roentgenium", "Copernicium",
#             "Nihonium", "Flerovium", "Moscovium", "Livermorium", "Tennessine", "Oganesson"]
recipe_handler = None


# Follows speedrun script guidelines
# TODO: Use this class in all relevant functions
class SpeedrunRecipe:
    crafts: list[tuple[str, str, str, bool]] = []  # Format: [0] + [1] -> [2], [3] indicates if the result is a target
    # TODO: Some way to represent line number comments
    emotes: dict[str, str]  # Optional emotes storage. Unused for now.
    craft_counts: dict[str, int] = {}  # Unused for now

    def __init__(self, crafts: list[tuple[str, str, str, bool]]):
        self.crafts = crafts

    def __str__(self):
        return '\n'.join(
            [f"{craft[0]}  +  {craft[1]}  =  {craft[2]}{'  // @result' if craft[3] else ''}" for craft in self.crafts])

    __repr__ = __str__

    def __getitem__(self, item):
        return self.crafts[item]

    def __iter__(self):
        return iter(self.crafts)

    def __len__(self):
        return len(self.crafts)

    @property
    def results(self) -> list[str]:
        return [craft[2] for craft in self.crafts]

    @property
    def targetList(self) -> list[str]:
        return [craft[2] for craft in self.crafts if craft[3]]

    def to_discord_message(self, default_language="prolog", highlight_language=None) -> str:
        # Note on languages:
        # Typescript - purple
        # Prolog - orange
        # Scala - funny
        if not highlight_language:
            if len(self.targetList) == 1:
                highlight_language = "fix"
            else:
                highlight_language = default_language
        current_str = ""
        last_lang = None
        for craft in self.crafts:
            cur_lang = highlight_language if craft[3] else default_language
            if last_lang != cur_lang or last_lang == "fix":
                if last_lang:
                    current_str += "```"
                current_str += f"```{cur_lang}\n"
                last_lang = cur_lang
            current_str += f"{craft[0]}  +  {craft[1]}  =  {craft[2]}{'  // @result' if craft[3] else ''}\n"

        current_str += "```"
        return current_str

    def to_discord_asciidoc(self) -> str:
        current_str = "```asciidoc\n"
        for i, craft in enumerate(self.crafts):
            current_str += f"{craft[0]}  +  {craft[1]}  =  {craft[2]}{'  // ' + str(i+1) + ' :: ' if craft[3] else ''}\n"
        current_str += "```"
        return current_str


def parse_craft_file(filename: str) -> SpeedrunRecipe:
    with open(filename, 'r', encoding='utf-8') as file:
        text = file.read()

    # Remove multiline comments
    # Multi-line - ignored
    # Note that comments have to start with either a newline or 2 spaces.
    text = re.sub('(\\s{2}|\n)/\\*.*?\\*/', '', text, flags=re.DOTALL)

    crafts: list[tuple[str, str, str, bool]] = []
    target_count = 0
    comment_warning = False

    for i, line in enumerate(text.split('\n')):
        try:
            # Line comment
            comment = re.search("(\\s{2}|^)//.*", line)
            if comment:
                line = line[:comment.start()]
                comment = comment.group(0)
            if not line.strip():
                continue
            # Target element indicated by two colons (::) within a comment
            target = "::" in comment if comment else False
            target_count += target

            # Warning if you're using single spaced comments
            if not comment_warning and "//" in line:
                comment_warning = True
                print(f"Warning: Double slashes found in line {i+1}: {line}. "
                      f"If this is a comment, use double spaces instead.")

            line = line.strip()
            ingredients, result = line.split('  =  ')
            ing1, ing2 = ingredients.split('  +  ')

            if "  " in ing1:
                ing1_emote, ing1 = ing1.split("  ")
            else:
                ing1_emote = ""

            if "  " in ing2:
                ing2_emote, ing2 = ing2.split("  ")
            else:
                ing2_emote = ""

            if "  " in result:
                result_emote, result = result.split("  ")
            else:
                result_emote = ""

            crafts.append((ing1.strip(), ing2.strip(), result.strip(), target))
        except ValueError:
            print(f"Delimiter not found in line {i+1}: {line}")
            print(f"Note that you need to use DOUBLE spaces around + and =, since elements may contain single spaces.")
            continue

    if target_count == 0:
        print("No target elements found in the recipe. Defaulting to last element as target.")
        crafts[-1] = (crafts[-1][0], crafts[-1][1], crafts[-1][2], True)

    return SpeedrunRecipe(crafts)


def compare(original: SpeedrunRecipe, new: SpeedrunRecipe):
    crafts = original.crafts
    crafts2 = new.crafts
    elements = set(original.results)
    elements2 = set(new.results)

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


def simple_check_script(speedrun_recipe: SpeedrunRecipe) -> tuple[bool, bool, bool]:
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
    for i, craft in enumerate(speedrun_recipe.crafts):
        ing1, ing2, result, is_target = craft
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


def loop_check_script(speedrun_recipe: SpeedrunRecipe) -> bool:
    crafts = speedrun_recipe.crafts
    cur_elements = {"earth", "fire", "water", "wind"}
    new_order = []

    while len(cur_elements) < len(crafts) + 4:
        has_changes = False
        for i, craft in enumerate(crafts):
            ing1, ing2, result, is_result = craft
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


def static_check_script(speedrun_recipe: SpeedrunRecipe):
    result = simple_check_script(speedrun_recipe)
    if not result[0] and result[1] and not result[2]:
        print("Trying to correct for misplaced elements...")
        loop_check_script(speedrun_recipe)


async def dynamic_check_script(speedrun_recipe: SpeedrunRecipe) -> bool:
    global recipe_handler
    if recipe_handler is None:
        config = util.load_json("config.json")
        recipe_handler = recipe.RecipeHandler(("Water", "Fire", "Wind", "Earth"), **config)

    crafts = speedrun_recipe.crafts

    # Format: ... + ... -> ...
    has_issues = False
    async with aiohttp.ClientSession() as session:
        for i, craft in enumerate(crafts):
            ing1, ing2, result, is_target = craft
            true_result = await recipe_handler.combine(session, ing1.strip(), ing2.strip())

            if true_result == "Nothing" or true_result == "Nothing\t" or true_result is None:
                true_result = await recipe_handler.combine(session, ing2.strip(), ing1.strip(), ignore_local=True)

            if true_result != result.strip():
                has_issues = True
                print(f"Craft {ing1} + {ing2} -> {result} is not correct. The correct response is {true_result}")

    if not has_issues:
        print("All recipes are correct!")
    return has_issues


def to_discord_message(speedrun_recipe: SpeedrunRecipe):
    print(speedrun_recipe.to_discord_message())


def parse_args():
    parser = argparse.ArgumentParser(description='Speedrun Checker')
    parser.add_argument('action', type=str, help='Action to perform',
                        choices=['static_check', 'dynamic_check', 'compare', 'to_discord'])
    parser.add_argument('file', type=str, help='File to read from')
    parser.add_argument('file2', type=str, help='File to compare to. Ignored unless using the compare action.',
                        nargs='?', default=None)
    return parser.parse_args()


if __name__ == '__main__':
    pass
    args = parse_args()
    if args.action == 'static_check':
        file = parse_craft_file(args.file)
        static_check_script(file)
    elif args.action == 'dynamic_check':
        if os.name == 'nt':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        file = parse_craft_file(args.file)
        asyncio.run(dynamic_check_script(file))
    elif args.action == 'compare':
        if args.file2 is None:
            print("No file to compare to!")
            sys.exit(1)
        file1 = parse_craft_file(args.file)
        file2 = parse_craft_file(args.file2)
        compare(file1, file2)
    elif args.action == 'to_discord':
        file = parse_craft_file(args.file)
        # to_discord_message(file)
        print(file.to_discord_asciidoc())
