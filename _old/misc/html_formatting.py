
import re
import shlex

COLUMN_SPACING = '  '  # 2 spaces
NUMERICALLY_NEUTRAL = '-'


# allows spacing without consideration of special invisible characters (like coloring), so it'll align WITH colors
def strip_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def is_num_or_unit(input):
    pattern = r'^[+-]?[0-9]+(\.[0-9]+)?\s?[pKkMmGgTt]?((i?[bB]?(/s)?)|(%?)|((@[0-9]+)?(Hz)?))$'
    return bool(re.match(pattern, input))


def format_table(table: str, align_left=True) -> str:
    """meant for html tables retrieved via BeautifulSoup4"""

    matrix = []
    for row in table.find_all('tr'):
        row_data = []
        for cell in row.find_all('td'):  # Check if the cell contains an anchor (linked) tag
            anchor = cell.find('a')
            if anchor:  # if indeed contains link
                row_data.append(anchor['href'])
            else:
                row_data.append(cell.text.strip())
        matrix.append(row_data)

    col_word_lengths = {}  # column_index: max_word_length
    col_numerical_majority = {}  # column_index: int (positive means more numbers, negative means more strings)

    # get max length of words in each column
    for row in matrix:
        for j, word in enumerate(row):
            col_word_lengths[j] = max(col_word_lengths.get(j, 0), len(strip_ansi(word)))
            if word != NUMERICALLY_NEUTRAL:  # ignore word if it could be either a number or not
                col_numerical_majority[j] = col_numerical_majority.get(j, 0) + (1 if is_num_or_unit(word) else -1)

    def pad_word(a_word, index):
        removed_chars_count = len(a_word) - len(strip_ansi(a_word))  # char-count ignores colors and other unseen chars
        padding_total = col_word_lengths.get(index, 0) + removed_chars_count
        # numbers need to be RTL, because it makes the MSB (most significant bit) stand out rather than the LSB.
        # the config doesn't matter; if a number/neutral-char is in a majority-numerical column, align it right
        is_align_right_anyway = col_numerical_majority.get(index, 0) > 0 and (is_num_or_unit(a_word) or a_word == NUMERICALLY_NEUTRAL)
        return a_word.rjust(padding_total) if not align_left or is_align_right_anyway else a_word.ljust(padding_total)

    # pad all words to make columns uniform
    for i, row in enumerate(matrix):
        matrix[i] = [pad_word(word, i) for i, word in enumerate(row)]

    # Print the padded matrix without commas or brackets
    return "\n".join([COLUMN_SPACING.join(inner_list) for inner_list in matrix])
