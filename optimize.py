# Speedrun Optimizer

import recipe
import speedrun

# TODO: 2 types of optimization
# 1. In-place: No new elements, only look at subsets of original that can be crafted
# 2. Limited-depth: Allow new elements up to a certain deviation from the original path
# 2a) iddfs (top-down)
# 2b) A* (bottom-up, single destination)

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


