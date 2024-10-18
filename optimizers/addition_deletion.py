from optimizers.optimizer_interface import OptimizerRecipeList
from util import DEFAULT_STARTING_ITEMS


# TODO
# Alternate to A*, instead of using a queue and looking at possibly unlimited numbers of additions / deletions,
# iterate on the elements list being modified and quickly check (checking is
# O(V^2) at most, possible to optimize further by storing portions of the graph) if the current results are achievable.
# Guaranteed to find optimal within constraints.
# Should be faster if you don't need to search for infinite additions/deletions, otherwise equal.


def check(recipes: OptimizerRecipeList, target: set[int], allowed_elements: set[int]) -> bool:
    init_elements = [recipes.get_id(i) for i in DEFAULT_STARTING_ITEMS]

    # Live modifying list in a loop because *why not*!
    # TODO: Don't do this in actual production code, this is just a shortcut while I write the algorithm

    # Also TODO: Use past checks to inform future checks, e.g. all lower generation than removed elements
    # are still reachable. Or even modified dijkstra with edge adding or smth

    elements = init_elements
    elements_set = set(elements)  # Using an element set to check for repeats quickly, and the list for ordering

    target_copy = target.copy()
    p1 = 0
    while p1 < len(elements):
        p2 = 0
        while p2 < len(elements):
            result = recipes.get_result_id(elements[p1], elements[p2])
            # print(result, target_copy, elements, p1, p2)
            p2 += 1

            if result not in allowed_elements:
                continue
            if result in target_copy:
                target_copy.remove(result)
                if len(target_copy) == 0:
                    return True

            if result not in elements_set:
                elements.append(result)
                elements_set.add(result)

        p1 += 1

    return False


def optimize(
        targets: list[str],
        recipe_list: OptimizerRecipeList,
        upper_bound: int,
        initial_crafts: list[int] = None,
        max_deviations: int = 2) -> list[int]:
    # TODO
    target_set = set([recipe_list.get_id(i) for i in targets])
    print(target_set, set(initial_crafts))
    print(check(recipe_list, target_set, set(initial_crafts)))
    starting_items = {0, 1, 2, 3}
    other_items = set(initial_crafts).difference(starting_items)
    print(other_items)
    # Check removing each item
    for i in other_items:
        if check(recipe_list, target_set, set(initial_crafts).difference({i})):
            print("Removed", i)
            # return [i]


    return []


def main():
    pass


if __name__ == "__main__":
    main()
