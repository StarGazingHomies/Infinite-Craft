def parse_craft_file_old(filename: str, forced_delimiter: Optional[str] = None, *, ignore_case: bool = True,
                         strict_order: bool = False) -> SpeedrunRecipe:
    with open(filename, 'r', encoding='utf-8') as file:
        crafts = file.readlines()

    # Automatic delimiter detection

    # Format: ... + ... [delimiter] ...
    craft_count = 0
    crafts_parsed: list[tuple[str, str, str, bool]] = []
    for i, craft in enumerate(crafts):
        # print(craft)
        if craft == '\n':
            continue
        is_target = craft[0] == '\t'
        craft = craft.split(" //")[0].strip()

        # Default delimiter
        delimiter = "  =  "
        if forced_delimiter:
            delimiter = forced_delimiter
        elif delimiter not in craft:
            # In case you're using a speedrun script not following the guidelines
            if " = " in craft:
                delimiter = ' = '
            elif " -> " in craft:
                delimiter = " -> "
            else:
                print(f"Delimiter not found in line {i + 1}")
                continue

        # TODO: Double spaced +
        try:
            ingredients, results = craft.split(delimiter)
            ing1, ing2 = ingredients.split(' + ')
        except ValueError:
            print(f"Delimiter not found in line {i + 1}: {craft}")
            continue
        if strict_order:
            if ing1 > ing2:
                ing1, ing2 = ing2, ing1
        ing1, ing2, results = ing1.strip(), ing2.strip(), results.strip()
        if ignore_case:
            ing1, ing2, results = ing1.lower(), ing2.lower(), results.lower()
        crafts_parsed.append((ing1, ing2, results, is_target))
        craft_count += 1

    return SpeedrunRecipe(crafts_parsed)