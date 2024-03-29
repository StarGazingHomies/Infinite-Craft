"""
A* Optimizer for single destination speedrun, or within a savefile
Requires already having a valid route to the destination - TODO: choose how missing recipes are handled.
Based on BRH0208's A*
"""


class AStarOptimizerState:
    craft_count: int
    current: list[tuple[int, int]]  # Crafts to do, depth of each of the items

    def __init__(self, craft_count: int, current: list[tuple[int, int]]):
        self.craft_count = craft_count
        self.current = current

    @property
    def heuristic(self) -> int:
        # Simple admissible heuristic: generation for all elements. Does not take into account repeating generations.
        return self.craft_count + sum([x[1] for x in self.current])

    @property
    def heuristic2(self) -> int:
        # Better admissible heuristic: generation for all elements. Takes into account repeating generations.
        generations = [i[1] for i in self.current]
        for i in range(1, len(generations)):
            generations[i] = max(generations[i], generations[i - 1] + 1)
        return self.craft_count + sum(generations)
