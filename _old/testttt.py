# import youtube_dl
#
# # Set the URL of the video you want to download
# video_url = "https://www.youtube.com/watch?v=MFT4OgFxfes"
#
# description = None  # Initialize the description variable
#
# with youtube_dl.YoutubeDL({}) as ydl:
#     info_dict = ydl.extract_info(video_url, download=False)
#     description = info_dict.get("description", "Description not available")
#
# # Specify the file path where you want to save the description
# output_file = "video_description.txt"
#
# if description:
#     # Write the description to a text file
#     with open(output_file, "w", encoding="utf-8") as file:
#         file.write(description)
#
# with youtube_dl.YoutubeDL({}) as ydl:
#     info_dict = ydl.extract_info(video_url, download=False)
#
#     title = info_dict.get("title", "Title not available")
#     uploader = info_dict.get("uploader", "Uploader not available")
#     upload_date = info_dict.get("upload_date", "Upload date not available")
#
#     print("Video Title:", title)
#     print("Uploader:", uploader)
#     print("Upload Date:", upload_date)









import youtube_dl
import json

# Set the URL of the video you want to download
video_url = "https://www.youtube.com/watch?v=MFT4OgFxfes"

# Define the output video file name (you can change this)
video_output_file = "downloaded_video.mp4"

# Define the output metadata file name (you can change this)
metadata_output_file = "video_metadata.json"

# Define the YouTube-DL options
ydl_opts = {
    'writeinfojson': True,  # Write metadata as JSON
    'outtmpl': '%(upload_date)s__%(title)s__%(id)s.%(ext)s',
}

with youtube_dl.YoutubeDL(ydl_opts) as ydl:
    ydl.download([video_url])
