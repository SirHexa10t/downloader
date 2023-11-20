import argparse


# parser = argparse.ArgumentParser()
# parser.add_argument('--all', action='store_true', default=False, help='Use Toggle mode instead of Hold mode')
# parser.add_argument('--audio_only', action='store_true', default=False, help='Print actions in terminal')
# parser.add_argument('--cps', action='store', default=20, type=float,
#                     help='How many clicks per second, default is 20')
# parser.add_argument('--key_press', action='store', default='', type=str,
#                     help='Specify key repeat instead of click (example: \'f\')')
# args = parser.parse_args()


def main():

    # TODO - check the type of link

    # youtube link
    # TODO - match to domain "youtube.com" or "youtu.be"
    import dl_youtube
    dl_youtube.download()

    # TODO - throw error message if no match found



if __name__ == "__main__":
    main()
