#!/usr/bin/env bash

# 1a - manually save the gametora page into a local html file. Make sure the page loaded all relevant supports.
# 2a - run 'find_support_urls.py' on the html file. It will output 'support_links.txt'

# 1b - find in the gametora website the stat-naming mapping, and save it into 'stat_table.json' (inspect -> sources , then look for its fields, like "name_en_eon" )
# 2b - run 'generate_lookup.py' on the json file you saved ('stat_table.json'), and put that table within 'scrape_single_support.py'

# 3  - Run this file


# File containing URLs (one per line)
URL_FILE="support_links.txt"
PY_FILE="scrape_single_support.py"

mkdir -p './outputs/'  # required by some other script

# Check if the file exists
if [[ ! -f "$URL_FILE" ]]; then
    echo "File $URL_FILE not found!"
    exit 1
fi

# Loop through each line in the file
while IFS= read -r line || [[ -n "$line" ]]; do
    # Skip empty lines
    [[ -z "$line" ]] && continue

    # Split line into page_url and img_url (space-separated)
    page_url=$(echo "$line" | awk '{print $1}')
    img_url=$(echo "$line" | awk '{print $2}')

    echo -e "------------------\nProcessing: $page_url"
    python3 "$PY_FILE" "$page_url" "$img_url"
done < "$URL_FILE"
