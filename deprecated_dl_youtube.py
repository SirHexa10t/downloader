# Deprecated: This module relies on an outdated repository. It might become relevant in the future.
# reference: https://github.com/ytdl-org/youtube-dl
# downloads the best quality by default



import youtube_dl

# records of file-IDs (youtube-dl skips those and adds new entries as it works)
DEFAULT_ARCHIVE_LOCATION = "/youtube_archive"  # you could override this, but I recommend just creating such a symlink
YOUTUBE_DOWNLOAD_ARCHIVE = "youtube_download_archive"  # FIXME - doesn't get written into
FILETYPE = "webm"
OUTPUT_FORMAT = "%(uploader)s[%(channel_id)s]/%(upload_date)s__%(title)s__%(id)s.%(ext)s"

# TODO - download with subtitles

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

def download_video_metadata(video_url):
    with youtube_dl.YoutubeDL({}) as ydl:
        info_dict = ydl.extract_info(video_url, download=False)
        description = info_dict.get("description", "Description not available.")

        print(description)

def download_one(video_to_dl,
                 archive_location=DEFAULT_ARCHIVE_LOCATION,
                 records_file=f"{DEFAULT_ARCHIVE_LOCATION}/{YOUTUBE_DOWNLOAD_ARCHIVE}",
                 **extra_args):
    ydl_opts = {}

    # if given a string, convert to tuple with a single string in it
    # if isinstance(videos_to_dl, str):
    #     videos_to_dl = (videos_to_dl,)

    # make sure that there's a records file (if we're using one)
    if records_file:
        import misc_tools
        misc_tools.create_file_if_not_exists(records_file)
        # ydl_opts['download-archive'] = records_file

    # metadata
    description_flags = ('write-description', 'write-info-json', 'write-annotations', 'write-sub', 'write-thumbnail')
    ydl_opts.update({key: True for key in description_flags})

    # ydl_opts['subtitle'] = '--write-sub --sub-lang en'

    # ydl_opts['write-description'] = True
    # ydl_opts['write-info-json'] = True



    ydl_opts['writesubtitles'] = True
    ydl_opts['write-sub'] = 'en'
    ydl_opts['sub-lang'] = 'en'

    # output
    ydl_opts['format'] = f'bestvideo[ext={FILETYPE}]+bestaudio[ext={FILETYPE}]/best[ext={FILETYPE}]/best'
    ydl_opts['outtmpl'] = f"{archive_location}/{OUTPUT_FORMAT}"

    # ad-hoc extra arguments
    ydl_opts.update(extra_args)

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_to_dl])
        # info_dict = ydl.extract_info(video_to_dl, download=False)
        # print(info_dict)






# -o, --output TEMPLATE                Output filename template, see the "OUTPUT TEMPLATE" for all the info
# youtube-dl -o '%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s' https://www.youtube.com/playlist?list=PLwiyx1dc3P2JR9N8gQaQN_BCvlSlap7re

# youtube-dl -f 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

# TODO - test "--extractor-descriptions" (Output descriptions of all supported extractors)
# TODO - test "--list-thumbnails" (Simulate and list all available thumbnail formats)
# TODO - test "--write-thumbnail" (Write thumbnail image to disk)

# TODO - test "--dateafter DATE" (Download only videos uploaded on or after this date (i.e. inclusive) date example: 20180101)

# TODO - test "--yes-playlist" (Download the playlist, if the URL refers to a video and a playlist.)

# TODO - test "--no-playlist" (Download only the video, if the URL refers to a video and a playlist.)

# TODO - test "-r, --limit-rate RATE" (Maximum download rate in bytes per second (e.g. 50K or 4.2M))

# TODO - test "--buffer-size SIZE" (Size of download buffer (e.g. 1024 or 16K) (default is 1024))

# TODO - test "--hls-prefer-native" (Use the native HLS downloader instead of ffmpeg)
# TODO - test "--hls-prefer-ffmpeg" (Use ffmpeg instead of the native HLS downloader)



