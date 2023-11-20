
ansi_colors = {
    "red": "\033[38;5;196m",
    "green": "\033[38;5;46m",
    "blue": "\033[38;5;21m",
    "cyan": "\033[38;5;51m",
    "yellow": "\033[38;5;226m",
    "reset": "\033[0m"  # Reset to the default color
}

def create_file_if_not_exists(file_path):
    from pathlib import Path
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    Path(file_path).touch(exist_ok=True)

def find_files_recursively(directory:str, ext:str):
    import os
    import glob
    return [file for file in glob.iglob(os.path.join(directory, f"**/*.*.{ext}"), recursive=True)]

def print_blue(string):
    """it's hard to read blue on black (and you probably use Darcula theme), so cyan instead"""
    print(f"{ansi_colors['cyan']}{string}{ansi_colors['reset']}")

def print_green(string):
    print(f"{ansi_colors['green']}{string}{ansi_colors['reset']}")

def print_red(string):
    print(f"{ansi_colors['red']}{string}{ansi_colors['reset']}")

def print_yellow(string):
    print(f"{ansi_colors['yellow']}{string}{ansi_colors['reset']}")


