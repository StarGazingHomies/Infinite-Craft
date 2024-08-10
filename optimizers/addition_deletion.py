from optimizer_interface import OptimizerRecipeList
from util import DEFAULT_STARTING_ITEMS

# TODO
# Alternate to A*, instead of using a queue and looking at possibly unlimited numbers of additions / deletions,
# iterate on the elements list being modified and quickly check (checking is
# O(V^2) at most, possible to optimize further by storing portions of the graph) if the current results are achievable.
# Guaranteed to find optimal within constraints.
# Should be faster if you don't need to search for infinite additions/deletions, otherwise equal.

def check(recipes: OptimizerRecipeList, target: int, allowed_elements: set[int]) -> bool:
    init_elements = [recipes.get_id(i) for i in DEFAULT_STARTING_ITEMS]

    # Live modifying list thing because *why not*!
    # Please don't do this in actual production code, this is just a test
    elements = init_elements
    p1 = 0
    while p1 < len(elements):
        p2 = 0
        while p2 < len(elements):
            result = recipes.get_result_id(elements[p1], elements[p2])
            if result == target:
                return True
            if result in allowed_elements:
                elements.append(result)

            p2 += 1
        p1 += 1

    return False


def main():
    pass


if __name__ == "__main__":
    main()
