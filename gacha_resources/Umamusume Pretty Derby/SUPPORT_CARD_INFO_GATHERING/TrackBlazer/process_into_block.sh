#!/usr/bin/env bash

rb_15_folder='./race_bonus_15/'
rb_10_folder='./race_bonus_10/'

mkdir -p "$rb_15_folder"
mkdir -p "$rb_10_folder"

output=$(./PRINT_BY_RACE_BONUS.sh)  # list of all supports and their total race bonus

echo "$output" | while read -r file num rest; do
    file="${file%.txt}.png"  # the script gives us only .txt files
    if [[ "$file" == *.png && "$num" == "15" ]]; then
        cp "$file" "$rb_15_folder"
    elif [[ "$file" == *.png && "$num" == "10" ]]; then
        cp "$file" "$rb_10_folder"
    fi
done

python3 ./collage_builder.py "$rb_15_folder"
python3 ./collage_builder.py "$rb_10_folder"




