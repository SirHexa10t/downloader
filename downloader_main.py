#!/usr/bin/python3


def get_domain(url):
    import re
    pattern = r'(?:https?://)?(?:www\.)?([^\s/.]+\.[^\s/]+)'
    match = re.match(pattern, url)
    return None if not match else match.group(1)
    # return match.group(1) if match else None


if __name__ == "__main__":
    import sys
    from misc.colored_prints import print_red, print_green


    def print_error_and_exit(error_str):
        print_red(error_str)
        exit(1)


    print_match = (lambda site: print(f"matched {site} for URL: {sys.argv[1]}"))

    if len(sys.argv) <= 1:
        print_error_and_exit("This program requires args to work!")

    domain_found = get_domain(sys.argv[1])
    if not domain_found:
        print_error_and_exit("First arg must be a URL!")

    if domain_found in ('youtube.com', 'youtube.be'):
        print_match('Youtube')
        import dl_youtube
        dl_youtube.download(sys.argv[1])
    elif domain_found == 'consoleroms.com':
        print_match('consoleroms.com')
    else:
        print_error_and_exit(f"I don't know how to handle {domain_found} (url: '{sys.argv[1]}')")


