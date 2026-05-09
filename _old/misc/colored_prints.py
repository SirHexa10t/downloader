
ansi_colors = {
    'HEADER':       '\033[95m',
    'OKBLUE':       '\033[94m',
    'OKCYAN':       '\033[96m',
    'OKGREEN':      '\033[92m',
    'WARNING':      '\033[93m',
    'FAIL':         '\033[91m',
    'BOLD':         '\033[1m',
    'UNDERLINE':    '\033[4m',
    "red": "\033[38;5;196m",
    "green": "\033[38;5;46m",
    "blue": "\033[38;5;21m",
    "cyan": "\033[38;5;51m",
    "yellow": "\033[38;5;226m",
    "reset": "\033[0m"  # Reset to the default color
}


def print_blue(string):
    """it's hard to read blue on black (and you probably use Darcula theme), so cyan instead"""
    print(f"{ansi_colors['cyan']}{string}{ansi_colors['reset']}")

def print_green(string):
    print(f"{ansi_colors['green']}{string}{ansi_colors['reset']}")

def print_red(string):
    print(f"{ansi_colors['red']}{string}{ansi_colors['reset']}")

def print_yellow(string):
    print(f"{ansi_colors['yellow']}{string}{ansi_colors['reset']}")

