# Generating a list of locations for my positioning script
import json

locations = []

# Enquoted alphabets:
quoted_alphabets = [
    ['!', ''],
    ['"', '"'],
#    ['(', ')'],         # Not as useful
    ['.', ''],
    ['/', '/'],
    ['_', ''],
    ['~', ''],
    ['‘', '’'],
    ['“', '”'],
]
# ! < " < # < ' < ( < ) < - < . < / < \ < _ < ~ <<< ‘ < “

quoted_alphabet_x = 20
quoted_alphabet_y = 400
quoted_alphabet_width = 90
quoted_alphabet_height = 42
for i, quote_type in enumerate(quoted_alphabets):
    prefix = quote_type[0]
    suffix = quote_type[1]
    x = i * quoted_alphabet_width + quoted_alphabet_x
    for j, char in enumerate("abcdefghijklmnopqrstuvwxyz"):
        y = j * quoted_alphabet_height + quoted_alphabet_y
        locations.append([prefix + char + suffix, x, y])

tool_groups = [
    [
        (20, 30), (42, 100),
        [
            "Delete First Character",
            "Delete First Letter",
            "Delete First Word",
            "Delete First"
        ]
    ],
    [
        (20, 215), (42, 100),
        [
            "Delete Last Character",
            "Delete Last Letter",
            "Delete Last Word",
            "Delete Last"
        ]
    ],
    [
        (320, 30), (42, 100),
        [
            "Delete The Quotation Mark",
            "Delete The Quotation Marks"
        ]
    ],
    [
        (320, 145), (42, 100),
        [
            "Delete The Dot",
            "Delete The Dots",
            "Delete The Period"
        ]
    ],
    [
        (320, 260), (42, 100),
        [
            "Hyphen",
            "Hyphenated",
            "Delete The Hyphen"
        ]
    ],
    [
        (570, 135), (42, 100),
        [
            "The",
            "The ~",
            "The Plural",
            "The One",
            "The The",
            "Delete The The"
        ]
    ],
    [
        (625, 30), (42, 100),
        [
            "Period",
            ".com"
        ]
    ],
    [
        (770, 30), (42, 100),
        [
            "Possessive",
            ["S'", "S's"],
            "Apostrophe",
            "Apostrophe S",
            "Delete The Apostrophe"
        ]
    ],
    [
        (770, 250), (42, 100),
        [
            "Past Tense"
        ]
    ],
    [
        (770, 300), (42, 100),
        [
            "Not",
            "Antonym"
        ]
    ],
    [
        (770, 400), (42, 100),
        [
            "Plural",
            "The Plural",
            "Pluralize",
            "Plurals"
        ]
    ],
    [
        (920, 400), (42, 100),
        [
            "Unplural",
            "Singular"
        ]
    ],
    [
        (770, 575), (42, 100),
        [
            "Without Spaces",
            "Without Spacing",
            "Delete The Space",
            "Makeoneword"
        ]
    ],
    [
        (1000, 575), (42, 100),
        [
            "With Spaces",
            "With Spacing",
            "English Sentence",
            "Romanization"
        ]
    ],
    [
        (770, 750), (42, 200),
        [
            ["Backwards", "Opposite"],
            ["Inverse", "Inverted"],
            ["Flip", "Swap"],
            ["Reverse", "Anagram"],
            "Repeat",
            "Makeoneword"
        ]
    ],
    [
        (770, 1030), (42, 100),
        [
            ['"0"', '“0”'],
            ['"1"', '“1”'],
            ['"2"', '“2”'],
            ['"3"', '“3”'],
            ['"4"', '“4”'],
            ['"5"', '“5”'],
            ['"6"', '“6”'],
            ['"7"', '“7”'],
            ['"8"', '“8”'],
            ['"9"', '“9”']
        ]
    ],
    [
        (970, 1030), (42, 100),
        [
            ['"+"', '"."'],
            ['"?"', '"!"'],
            ['"&"', '"|"'],
            ['( )', "(", ")"],
            ['_', '-'],
            ['"', "'"],
            ['&', ','],
            ['~', '#'],
            "“”"
        ]
    ],
    [
        (1000, 30), (42, 100),
        [
            "Hashtag",
            "The Hashtag",
            "Hashtag The",
            "Hashtagify"
        ]
    ],
    [
        (1000, 250), (42, 100),
        [
            "Next",
            "Next Alphabet",
            "Next Episode"
        ]
    ]
]

for group in tool_groups:
    x, y = group[0]
    height, width = group[1]
    for i, tool in enumerate(group[2]):
        if type(tool) is str:
            locations.append([tool, x, y + i * height])
        elif type(tool) is tuple or type(tool) is list:
            for j, sub_tool in enumerate(tool):
                locations.append([sub_tool, x + j * width, y + i * height])

# print(locations)
# with open("locations.json", "w", encoding='utf-8') as fout:
#     json.dump({"locations": locations}, fout, ensure_ascii=False, indent=4)

# Pony locations
pony_locations = []
pony_ep_width = 400
pony_ep_height = 42
# column_count = 84
with open("pony_episodes.txt", "r") as fin:
    episodes = fin.readlines()
    for i, episode in enumerate(episodes):
        if episode.count("\t") != 5:
            continue
        season, ep_air, ep_production, overall_air, overall_production, name = episode.split("\t")

        s = int(season) - 1
        e = int(ep_air) - 1
        # x = (s // 2) * pony_ep_width
        # y = (e + (s % 2) * 26) * pony_ep_height
        x = s * pony_ep_width
        y = e * pony_ep_height
        pony_locations.append([name.strip().replace(', ', '').replace('- ', ''), x, y])

print(pony_locations)
with open("pony_locations.json", "w", encoding='utf-8') as fout:
    json.dump({"locations": pony_locations[::-1]}, fout, ensure_ascii=False, indent=4)


with open("in_a_results.txt", "r") as fin:
    lines = fin.readlines()
    cnt = 0
    for line in lines:
        if len(line.split("-> ")[1]) >= 20:
            cnt += 1
    print(len(lines), cnt, cnt / len(lines))