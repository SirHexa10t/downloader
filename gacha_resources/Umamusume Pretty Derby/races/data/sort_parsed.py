#!/usr/bin/python3

# assuming you ran:
# ./parse_gametora.py Pre-OP > aggregate.txt
# ./parse_gametora.py OP >> aggregate.txt
# ./parse_gametora.py G3 >> aggregate.txt
# ./parse_gametora.py G2 >> aggregate.txt
# ./parse_gametora.py G1 >> aggregate.txt
FILE_PATH = 'aggregate.txt'


def sort_dicts_list(dlist):
    from functools import cmp_to_key
    # Define the orderings
    year_order = {"Junior": 0, "Classic": 1, "Senior": 2}
    month_order = {
        "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
        "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12
    }
    earlylate_order = {"Early": 0, "Late": 1}
    racetype_order = {"Pre-OP": 4, "OP": 3, "G3": 2, "G2": 1, "G1": 0, }

    def race_key_cmp(a, b) -> int:
        ya, ma, ea = a['date'].split()
        yb, mb, eb = b['date'].split()

        ydiff = year_order[ya] - year_order[yb]  # compare year
        mdiff = month_order[ma] - month_order[mb]  # compare month
        ediff = earlylate_order[ea] - earlylate_order[eb]  # compare early/late in month
        racediff = racetype_order[a['grade']] - racetype_order[b['grade']]  # compare race grade
        namediff = len(a['name']) - len(b['name']) #  compare name length (the lengthier, the more significant)

        return ydiff if ydiff != 0 \
          else mdiff if mdiff != 0 \
          else ediff if ediff != 0 \
          else racediff if racediff != 0 \
          else namediff

    def sort_races(ds: list[dict]) -> list[dict]:
        return sorted(ds, key=cmp_to_key(race_key_cmp))

    return sort_races(dlist)


def sort_races_in_file():
    import ast

    # Open and read all lines, stripping whitespace
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        lines = [ast.literal_eval(line.strip()) for line in f if line.strip()]

    return sort_dicts_list(lines)


def format_csvlike(list_of_dicts: list[dict]):
    lines=['  '.join(list_of_dicts[0].keys()),]
    lines += ['  '.join(map(str, d.values())) for d in list_of_dicts]
    return lines


# Example usage
if __name__ == "__main__":
    race_list = sort_races_in_file()
    # for r in race_list:
    #     print(r)
    race_table = format_csvlike(race_list)  # need to format the result as a neat table with an external tool
    for r in race_table:
        print(r)

