import json
import bidict

# Load sample testing data from Yui's optimizer
with open("../yui_optimizer_savefile.json", "r", encoding='utf-8') as file:
    data = json.load(file)

# Raw recipes and elements data
recipes_raw: dict[str, list[dict]] = data["recipes"]
elements_raw = data["elements"]

# bidirectional mapping from text to id
id_map: bidict.bidict[str, int] = bidict.bidict()
for i, element in enumerate(elements_raw):
    id_map[element['text']] = i

# Convert raw recipes to integer ids
recipes: dict[int, list[list[int, int, int]]] = {}
for result, recipe_list in recipes_raw.items():
    new_recipe_list: list[list[int, int, int]] = []
    for recipe in recipe_list:
        new_recipe_list.append([id_map[recipe[0]['text']], id_map[recipe[1]['text']], 0])
    recipes[id_map[result]] = new_recipe_list


# Code from Yui's site, converted from javascript to python
def calculate_recipe_depth():
    queue = {}
    depth = {0: 1, 1: 1, 2: 1, 3: 1}

    def enqueue(item, recipe, result):
        if item not in queue:
            queue[item] = {}
        q = queue[item]
        if result not in q:
            q[result] = []
        q[result].append(recipe)

    def check_recipe(recipe, result):
        if recipe[0] not in depth:
            enqueue(recipe[0], recipe, result)
        elif recipe[1] not in depth:
            enqueue(recipe[1], recipe, result)
        else:
            recipe[2] = depth[recipe[0]] + depth[recipe[1]]
            return recipe[2]

    def find_min_depth(list, result):
        min_depth = float('inf')
        for recipe in list:
            recipe_depth = check_recipe(recipe, result)
            if recipe_depth and recipe_depth < min_depth:
                min_depth = recipe_depth

        if min_depth == float('inf') or result in depth:
            return

        depth[result] = min_depth

        if result in queue:
            for k, x in queue[result].items():
                find_min_depth(x, k)
            del queue[result]

    for result, recipe_list in recipes.items():
        find_min_depth(recipe_list, result)

    for result, recipe_list in queue.items():  # just in case
        find_min_depth(recipe_list, result)

    return depth


# Recipe format: [a: number, b: number, depth: number]
def find_smallest_recipe(recipe_list: list[tuple[int, int, int]]):
    return min(recipe_list, key=lambda x: x[2]) if recipe_list else None


def generateRecipeTree(item_id: int, recipes: dict[int, list[list[int, int, int]]]):
    crafted: set[int] = {0, 1, 2, 3}
    unknown: set[int] = set()
    queue: list[int] = [item_id]
    steps: list[tuple[int, int, int]] = []

    while len(queue) > 0:
        cur_id = queue.pop(0)
        if cur_id in crafted:
            continue
        if cur_id not in recipes:
            unknown.add(cur_id)
            continue

        recipe = find_smallest_recipe([x for x in recipes.get(cur_id) if x[0] not in queue and x[1] not in queue])

        if not recipe:
            unknown.add(cur_id)
            continue

        if recipe[0] not in crafted or recipe[1] not in crafted:
            if cur_id not in queue:
                queue.append(cur_id)
            if recipe[1] not in crafted and recipe[1] not in queue:
                queue.append(recipe[1])
            if recipe[0] not in crafted and recipe[0] not in queue:
                queue.append(recipe[0])
        else:
            steps.append((recipe[0], recipe[1], cur_id))
            crafted.add(cur_id)

    return [steps, unknown]


calculate_recipe_depth()

steps, unknown = generateRecipeTree(id_map["1444980"], recipes)
for step in steps:
    print(f"{id_map.inverse[step[0]]} + {id_map.inverse[step[1]]} -> {id_map.inverse[step[2]]}")
print(unknown)
