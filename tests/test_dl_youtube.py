import unittest
import dl_youtube

SHORT_VIDEO_LINK = "https://www.youtube.com/watch?v=MFT4OgFxfes"  # 11s ; "Ice Cream - Oney Cartoons"
LONG_VIDEO_LINK = "https://www.youtube.com/watch?v=HQYsFshbkYw"  # 20m ; Bisqwit's tutorial "Doom-style 3D engine in C"
VERY_LONG_VIDEO_LINK = "https://www.youtube.com/watch?v=HQYsFshbkYw"  # 3.5h ; Flowering Night 2009
SHARE_LINK = "https://youtu.be/pv21e6iEZUw?si=sl5UGl0DI00f-0_h"  # 2.5m ; "A Cruel Angel’s Thesis, but it's ULTRA EPIC"
TIMESTAMPED_LINK = "https://youtu.be/IYnsfV5N2n8?si=6xSF90BnXIJcdy04&t=39"  # middle of "asdfmovie"
PLAYLIST_LINK = "https://www.youtube.com/watch?v=7jrKjkrX3Gw&list=PLvR1Vs9Qj4fk-VnGR2xUtNLvLcwBwGB6V"  # 10 JoJo OPs
CHANNEL_LINK_VIDEOS = "https://www.youtube.com/@MontemayorChannel/videos"  # Historical naval warfare (~20 videos)
CHANNEL_LINK = "https://www.youtube.com/@MontemayorChannel"  # Historical naval warfare (~20 videos)

HTTP_LINK = "http://www.youtube.com/watch?v=MFT4OgFxfes"  # 11s ; "Ice Cream - Oney Cartoons"

SUBTITLED_LINK = "https://www.youtube.com/watch?v=cEN00wMFB2A"  # 3m ; "[Jangbbijju Shorts] PlayStation"

KOREAN_TITLE_LINK = "https://www.youtube.com/watch?v=TBQTntud1as"  # "A summary of the world in 22 seconds"

AUTOGENERATED_SUBBED_LINK = "https://www.youtube.com/watch?v=H6t8eeXlADY"  # 4m ; Linux User Problems

AUTOTRANSLATED_SUBBED_LINK = "https://www.youtube.com/watch?v=HHmCSPXY32k"  # 6m ; HARD CORNER - Mario Kart Home Circuit - Benzaie TV


# TODO - test the records file (using the "instant regret clicking this playlist" playlist)

# TODO - whole channel (in different channel notations)
# TODO - sound only
# TODO - different resolutions
# TODO - age-restricted videos
# TODO - geo-restricted videos
# TODO - problematic (unlisted?) videos; part of channel
# TODO - very long videos
# TODO - test listing
# TODO - test records file


# define testing download-area
ARCHIVE_LOCATION = './test_outputs'
test_opts = {
    'archive_location': f'{ARCHIVE_LOCATION}',  # overwrite function arg
}

print("FINISHED BASIC DEFINITIONS")



class DownloadCases(unittest.TestCase):
    def test_download_short_video(self):
        dl_youtube.download(dl_link=SHORT_VIDEO_LINK, **test_opts)

    def test_download_korean_title_video(self):
        dl_youtube.download(dl_link=KOREAN_TITLE_LINK, **test_opts)

    def test_download_subbed_video(self):
        dl_youtube.download(dl_link=SUBTITLED_LINK, topic='subs_check', **test_opts)

    def test_download_autosubbed_video(self):
        dl_youtube.download(dl_link=AUTOGENERATED_SUBBED_LINK, topic='subs_check', **test_opts)

    def test_download_autotranslated_video(self):
        dl_youtube.download(dl_link=AUTOTRANSLATED_SUBBED_LINK, topic='subs_check', **test_opts)

    def test_no_duplications(self):
        # TODO - download twice and check that eventually only one instance
        pass






