import math

WORD_TOKEN_LIMIT = 20
WORD_COMBINE_CHAR_LIMIT = 30
DEFAULT_STARTING_ITEMS = ("Water", "Fire", "Wind", "Earth")


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


def to_start_case(s: str) -> str:
    new_str = ""
    for i in range(len(s)):
        if i == 0 or s[i - 1] == " ":
            new_str += s[i].upper()
        else:
            new_str += s[i].lower()
    return new_str
