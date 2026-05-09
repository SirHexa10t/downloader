#!/usr/bin/python3

races = {
    "Junior Apr Early": {
        "grade": "G3",
        "name": "Sapporo Junior Stakes",
        "racetrack": "Sapporo",
        "direction": "right",
        "terrain": "turf",
        "distance": 1200,
        "season": "Spring",
        "time": "day",
    },
    "Junior Apr Late": {
        "grade": "G2",
        "name": "Hanshin Junior Cup",
        "racetrack": "Hanshin",
        "direction": "right",
        "terrain": "turf",
        "distance": 1400,
        "season": "Spring",
        "time": "day",
    },
    "Classic May Early": {
        "grade": "G1",
        "name": "Tokyo Derby",
        "racetrack": "Tokyo",
        "direction": "left",
        "terrain": "dirt",
        "distance": 2000,
        "season": "Spring",
        "time": "day",
    },
    # … add more …
    "Senior Dec Late": { "grade": "G1", "name": "Arima Kinen", "racetrack": "Nakayama", "direction": "right", "terrain": "turf", "distance": 2500, "season": "Winter", "time": "day" },
}












# -----------------------------------------------------------------------
# ------------------------------ DATE SORTER ----------------------------
# -----------------------------------------------------------------------

from functools import cmp_to_key

# Define the orderings
year_order = {"Junior": 0, "Classic": 1, "Senior": 2}
month_order = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12
}
earlylate_order = {"Early": 0, "Late": 1}

def race_key_cmp(a: str, b: str) -> int:
    ya, ma, ea = a.split()
    yb, mb, eb = b.split()
    # Compare year
    if year_order[ya] != year_order[yb]:
        return year_order[ya] - year_order[yb]
    # Compare month
    if month_order[ma] != month_order[mb]:
        return month_order[ma] - month_order[mb]
    # Compare early/late
    return earlylate_order[ea] - earlylate_order[eb]

def sort_race_keys(keys: list[str]) -> list[str]:
    return sorted(keys, key=cmp_to_key(race_key_cmp))

# Example usage:
all_keys = list(races.keys())
sorted_keys = sort_race_keys(all_keys)
print(sorted_keys)




def distance_type(distance: int) -> str:
    """
    Categorize distance into one of:
    - sprint: <= 1200 m
    - mile: >1200 and <= 1600 m
    - medium: >1600 and <= 2400 m
    - long: >2400 m
    """
    if distance <= 1200:
        return "sprint"
    elif distance <= 1600:
        return "mile"
    elif distance <= 2400:
        return "medium"
    else:
        return "long"

# Example usage:
print(distance_type(1000))  # sprint
print(distance_type(1500))  # mile
print(distance_type(2000))  # medium
print(distance_type(3000))  # long







