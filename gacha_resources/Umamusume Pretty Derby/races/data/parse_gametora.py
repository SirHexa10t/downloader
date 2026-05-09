#!/usr/bin/python3

# parses text copied from  https://gametora.com/umamusume/races

def parse_races(file_path):
    races = []

    # Open and read all lines, stripping whitespace
    with open(file_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    i = 0
    while i < len(lines):
        try:
            # Each race has 7 lines
            name = lines[i]
            year = lines[i + 1]  # Junior / Classic / Senior info
            year = year.replace('First Year', 'Junior')
            year = year.replace('Second Year', 'Classic')
            year = year.replace('Third Year', 'Senior')
            date_within_year = lines[i + 2]  # e.g., June 2
            date_within_year = date_within_year.replace('1', 'Early')
            date_within_year = date_within_year.replace('2', 'Late')
            season = {
                'Dec': 'Winter', 'Jan': 'Winter', 'Feb': 'Winter',
                'Mar': 'Spring', 'Apr': 'Spring', 'May': 'Spring', 'Jun': 'Spring',
                'Jul': 'Summer', 'Aug': 'Summer',
                'Sep': 'Fall', 'Oct': 'Fall', 'Nov': 'Fall' }.get(date_within_year[:3], '?')
            terrain = lines[i + 3] if lines[i + 3] != "Varies" else "?"

            # Direction and racetrack
            direction_racetrack = lines[i + 4]
            if direction_racetrack != "Varies":
                arrow, racetrack = direction_racetrack.split(maxsplit=1)
                direction = {"⇒": "right", "⇐": "left", "⇑": "straight"}.get(arrow, "?")
            else:
                direction = "?"
                racetrack = "?"

            racetype = lines[i + 5] if lines[i + 5] != "Varies" else "?"
            racetype = racetype.replace('Short', 'Sprint')

            # Distance parsing
            distance_line = lines[i + 6]
            if distance_line != "Varies":
                try:
                    distance = int(distance_line.split()[0])  # Take first number
                except ValueError:
                    distance = "?"
            else:
                distance = "?"

            # Append the race dictionary to the list
            races.append({
                "date": f"{year} {date_within_year}",
                "grade": file_path,
                "name": name,
                "racetrack": racetrack,
                "direction": direction,
                "terrain": terrain,
                "distance": distance,
                "race-type": racetype,
                "season": season,
                "daytime": "?",
                "fans": "?"
            })

            i += 7  # Move to the next race
        except IndexError:
            # End of file reached
            break

    return races

# Example usage
if __name__ == "__main__":
    import sys
    race_list = parse_races(sys.argv[1])
    for race in race_list:
        print(race)


