import math

WORD_TOKEN_LIMIT = 20
WORD_COMBINE_CHAR_LIMIT = 30
DEFAULT_STARTING_ITEMS = ("Wind", "Fire", "Water", "Earth")


def pair_to_int(i: int, j: int) -> int:
    if j < i:
        i, j = j, i
    return i + (j * (j + 1)) // 2


def int_to_pair(n: int) -> tuple[int, int]:
    if n < 0:
        return -1, -1
    j = math.floor(((8 * n + 1) ** 0.5 - 1) / 2)
    i = n - (j * (j + 1)) // 2
    return i, j
