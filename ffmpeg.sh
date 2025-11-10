# Case 1: Enhanced Command for M4B (Audiobook)
# This command creates a fully-featured M4B audiobook file with audio, chapters, subtitles, and a cover image. 
# The .m4b format is ideal for audiobooks as it is specifically designed to support these features in players like Apple Books, VLC, and others.

ffmpeg -i UnravelMe-c12.flac \
-i metadata_part1.txt \
-i UnravelMe-c12.vtt \
-i UnravelMe-c12.jpg \
-map 0:a \
-map 3:v \
-map_metadata 1 \
-map 2:s \
-c:a aac -b:a 192k \
-c:v copy \
-c:s mov_text \
-disposition:v:0 attached_pic \
-metadata:s:s:0 language=eng \
-af 'loudnorm=I=-16:LRA=11:TP=-1.5,afftdn=nf=-70' \
-y UnravelMe-c12.m4b

# Command Breakdown:
# -i UnravelMe-c12.flac ... -i cover.jpg: Specifies the four input files: audio, chapters, subtitles, and cover image.
# -map 0:a: Selects the audio stream from the first input (the FLAC file).
# -map 3:v: Selects the video stream from the fourth input (the cover image).
# -map_metadata 1: Applies the chapter metadata from the second input (the text file).
# -map 2:s: Selects the subtitle stream from the third input (the VTT file).
# -c:a aac -b:a 192k: Sets the audio codec to aac with a bitrate of 192k, a good balance of quality and size for audiobooks.
# -c:v copy: Copies the video stream (the cover image) without re-encoding it.
# -c:s mov_text: Sets the subtitle codec to mov_text, making it compatible with the M4B/MP4 container.
# -disposition:v:0 attached_pic: Marks the video stream as an attached picture (i.e., the cover art).
# -metadata:s:s:0 language=eng: Sets the language metadata for the subtitle track to English.
# -af '...': Applies the same audio filters for loudness normalization and denoising from your original command.
# -y: Overwrites the output file if it already exists.



# Case 2: Enhanced Command for MP4
# The command for creating an MP4 file is nearly identical. 
# The MP4 container is versatile and widely supported, though .m4b is more specific for audiobooks. 
# The resulting file will be an audio-only MP4 with embedded subtitles and cover art.

ffmpeg -i UnravelMe-c12.flac \
-i metadata_part1.txt \
-i UnravelMe-c12.vtt \
-i UnravelMe-c12.jpg \
-map 0:a \
-map 3:v \
-map_metadata 1 \
-map 2:s \
-c:a aac -b:a 192k \
-c:v copy \
-c:s mov_text \
-disposition:v:0 attached_pic \
-metadata:s:s:0 language=eng \
-af 'loudnorm=I=-16:LRA=11:TP=-1.5,afftdn=nf=-70' \
-y UnravelMe-c12.mp4
