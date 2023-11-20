# reference: https://github.com/ytdl-org/youtube-dl
# downloads the best quality by default
# NOTICE: you need to have yt-dlp installed on your OS (it just works better than the Python lib)

# import yt_dlp
import os

from misc_tools import print_blue

# records of file-IDs (youtube-dl skips those and adds new entries as it works)
DEFAULT_ARCHIVE_LOCATION = "/youtube_archive"  # you could override this, but I recommend just creating such a symlink
YOUTUBE_DOWNLOAD_ARCHIVE = "youtube_download_archive"
FILETYPE = "webm"
OUTPUT_FORMAT = "%(uploader)s[%(channel_id)s]/%(upload_date)s__%(title)s__%(id)s.%(ext)s"

# TODO - download metadata (video description)

# TODO - add listing function

# TODO - add download specifically for playlists
#     requires a different output-format:
#       use "playlist", "playlist_index", "playlist_id", "playlist_title", "playlist_uploader"

# TODO - add download for series/seasons of videos
#     use "series", "season", "season_number", "season_id", "episode", "episode_number", maybe "episode_id"

# TODO - maybe music albums
#     use "track", "track_number", "artist", "genre", "album", "album_type", "album_artist", "release_year"


# TODO - handle downloading from entire channel

# TODO - add an arg for audio-only

# TODO -   --concurrent-fragments N


def download(dl_link,
             archive_location: str = f"{DEFAULT_ARCHIVE_LOCATION}",
             topic: str = None,  # main tag to nest the download under
             records_file: str = f"{YOUTUBE_DOWNLOAD_ARCHIVE}",
             **extra_args):

    # Command line opts. The Python lib gave me problems for similar commands that shell commands were fine with
    yt_dlp_opts = ['yt-dlp']

    # make sure that there's a records file (if we're using one)
    yt_dlp_opts.extend(['--download-archive', f"'{archive_location}/{records_file}'"])  # download_archive  opt for python-lib call

    # metadata
    yt_dlp_opts.extend(['--write-sub',  # necessary to download uploader's subs when available
                        '--write-auto-sub',
                        '--sub-lang', 'en',
                        '--embed-subs',
                        '--compat-options', 'no-keep-subs',  # deletes the .vtt files after embed
                        ])

    # output
    yt_dlp_opts.extend(['--format', f"'bestvideo[ext={FILETYPE}]+bestaudio[ext={FILETYPE}]/best[ext={FILETYPE}]/best'"])
    yt_dlp_opts.extend(['--output', f"'{archive_location}/{'' if not topic else topic+'/'}{OUTPUT_FORMAT}'"])  # 'outtmpl' opt for python-lib call

    # ad-hoc extra arguments
    # remove function args if they're in the extras dict
    for key in list(locals().keys()):
        extra_args.pop(key, None)
    if extra_args:
        yt_dlp_opts.extend([item for pair in extra_args.items() for item in pair])

    # youtube links to handle (specified at the end)
    yt_dlp_opts.append(dl_link)

    # declare and download
    command = ' '.join(yt_dlp_opts)
    print_blue(f"running command: {command}")
    os.system(command)



