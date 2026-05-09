import requests
from bs4 import BeautifulSoup

from misc.html_formatting import format_table


def fetch_program_info(url):
    page_segments=[]

    page_segments.append(('source:', url))

    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # emulator name
    page_segments.append(('', soup.find('h1', attrs={'itemprop': 'name', 'title': True}).text.strip() ))

    # Description
    page_segments.append(( 'Description', soup.find(attrs={'itemprop': 'description'}).text.strip() ))

    # Quick Facts
    details = soup.find('table', class_=['table', 'table-striped'])
    page_segments.append(( 'Details', format_table(details) ))

    # Downloads
    downloads = soup.find('div', attrs={'class': 'sharingDiv'}).find('table', class_=['table', 'table-striped'])
    page_segments.append(( 'Downloads', format_table(downloads) ))

    page_stringified = "\n\n".join(['\n'.join(segment) for segment in page_segments])

    print(page_stringified)

