import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import io
from collections import namedtuple
from types import SimpleNamespace

import gradio as gr
from tqdm import tqdm
from datetime import datetime
from multiprocessing import cpu_count, Pool
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pydub import AudioSegment

from lib.classes.tts_manager import TTSManager
from lib.models import TTS_SML
from lib.conf import default_audio_proc_format
from lib.util import util


required_session_fields = [
    'chapters',
    'tts_engine',
    'final_name',
    'output_split_minutes',
    'chapters_dir',
    'audiobooks_dir',
    'process_dir',
    'chapters_dir_sentences',
    'cover',
    'output_format',
    'metadata',
    'cancellation_requested',
]
Conf = namedtuple("Conf", required_session_fields)

class EbookAudio:

    def __init__(self, session):
        # pick only required field from session as read-only obj instance
        filtered_data = {k :session[k] for k in required_session_fields if k in session}
        self.conf = Conf(**filtered_data)

    def transfer_chapters_to_audio_file(self, session):
        """
        Converts text chapters into audio files using a TTS engine.

        This method orchestrates the text-to-speech conversion process. It manages
        the TTS engine, handles resuming from a previously interrupted session,
        iterates through chapters and sentences, generates audio for each sentence,
        and then combines the sentence audio files into a single file for each chapter.

        Args:
            session (dict): A dictionary containing all session-related data, including:
                - 'cancellation_requested' (bool): Flag to stop the process.
                - 'tts_engine' (str): The identifier for the TTS engine to use.
                - 'chapters_dir' (str): Path to the directory for storing chapter audio.
                - 'chapters_dir_sentences' (str): Path to the directory for storing sentence audio.
                - 'chapters' (list): A list of chapters, where each chapter is a list of sentences.

        Returns:
            bool: True if the conversion is successful, False otherwise.
        """
        try:
            # Immediately exit if a cancellation request has been detected.
            if session['cancellation_requested']:
                print('Cancel requested')
                return False

            # --- Process Initialization ---
            all_chapters_ = session['chapters']
            total_chapters_num = len(all_chapters_)
            if total_chapters_num == 0:
                print('No chapters found!')
                return False

            # --- Resume Logic ---
            # Determine the starting point if resuming a previous session.
            missing_chapters, resume_chapter = self.calculate_chapter_resume(session['chapters_dir'])
            missing_sentences, resume_sentence = self.calculate_sentence_resume(session['chapters_dir_sentences'])

            # Calculate total number of items (sentences + SML tokens) for the progress bar.
            total_iterations = sum(len(all_chapters_[x]) for x in range(total_chapters_num))
            # Calculate the total number of actual sentences to be converted.
            total_sentences = sum(sum(1 for row in chapter if row.strip() not in TTS_SML.values()) for chapter in
                                  all_chapters_)
            if total_sentences == 0:
                print('No sentences found!')
                return False

            # Initialize the TTS manager with the current session configuration.
            tts_manager = TTSManager(session)
            if not tts_manager:
                error = f"TTS engine {session['tts_engine']} could not be loaded!\nPossible reason can be not enough VRAM/RAM memory.\nTry to lower max_tts_in_memory in models.py"
                print(error)
                return False

            sentence_number = 0
            print(f"--------------------------------------------------\nA total of {total_chapters_num} {'chapter' if total_chapters_num <= 1 else 'chapters'} and {total_sentences} {'sentence' if total_sentences <= 1 else 'sentences'}.\n--------------------------------------------------")

            # --- Main Processing Loop ---
            progress_bar = gr.Progress(track_tqdm=False)
            # an iteration for one sentence including breaking
            with tqdm(total=total_iterations, desc='0.00%', bar_format='{desc}: {n_fmt}/{total_fmt} ', unit='step', initial=0) as tbar:
                # iterate each chapter
                for chapter_num_start_with_0 in range(total_chapters_num):
                    chapter_num = chapter_num_start_with_0 + 1
                    chapter_audio_file = f'chapter_{chapter_num}.{default_audio_proc_format}'
                    sentences_and_breaking_of_chapter = all_chapters_[chapter_num_start_with_0]
                    # breaking, such as {break} {pause}, won't generate speech file. no need to count
                    sentences_only_count = sum(1 for row in sentences_and_breaking_of_chapter if row.strip() not in TTS_SML.values())
                    chapter_stences_start = sentence_number  # Mark the starting sentence number for this chapter.
                    print(f'Chapter {chapter_num} containing {sentences_only_count} sentences...')

                    # Iterate through each sentence/SML token in the chapter.
                    for i, sentence in enumerate(sentences_and_breaking_of_chapter):
                        if session['cancellation_requested']:
                            print('Cancel requested')
                            return False

                        # Determine if the sentence needs to be processed.
                        # This is true if it's a missing sentence, or if it's beyond the last processed sentence.
                        if sentence_number in missing_sentences or sentence_number > resume_sentence or (sentence_number == 0 and resume_sentence == 0):
                            if sentence_number <= resume_sentence and sentence_number > 0:
                                print(f'**Recovering missing file sentence {sentence_number}')
                            
                            sentence = sentence.strip()
                            # Convert sentence to audio. SML tokens are skipped but still marked as success.
                            success = tts_manager.convert_sentence2audio(sentence_number, sentence) if sentence else True
                            if success:
                                # Update progress bar and console output.
                                total_progress = (tbar.n + 1) / total_iterations
                                progress_bar(total_progress)
                                is_sentence = sentence.strip() not in TTS_SML.values()
                                percentage = total_progress * 100
                                tbar.set_description(f'{percentage:.2f}%')
                                print(f" | {sentence}")
                            else:
                                # If TTS fails for any sentence, abort the entire process.
                                return False

                        # Increment sentence number only for actual sentences, not SML tokens.
                        if sentence.strip() not in TTS_SML.values():
                            sentence_number += 1
                        
                        tbar.update(1)  # Advance progress bar for every item (sentence or SML).

                    # --- Chapter Finalization ---
                    # Mark the ending sentence number for this chapter.
                    chapter_sentences_end = sentence_number - 1 if sentence_number > 1 else sentence_number
                    print(f"End of chapter {chapter_num}")

                    # Combine the generated sentence audio files into a single chapter file.
                    # This is done if the chapter was missing or is new.
                    if chapter_num in missing_chapters or sentence_number > resume_sentence:
                        if chapter_num <= resume_chapter:
                            print(f'**Recovering missing file chapter {chapter_num}')
                        
                        if self.combine_audio_sentences(chapter_audio_file, chapter_stences_start, chapter_sentences_end, session):
                            print(f'Combining chapter {chapter_num} to audio, sentence {chapter_stences_start} to {chapter_sentences_end}')
                        else:
                            print('combine_audio_sentences() failed!')
                            return False
            return True
        except Exception as e:
            util.print_error(e)
            return False

    def calculate_chapter_resume(self, chapters_dir_):
        resume_chapter = 0
        missing_chapters = []
        # Check for already processed chapter audio files to find the resume point.
        existing_chapters = sorted(
            [f for f in os.listdir(chapters_dir_) if f.endswith(f'.{default_audio_proc_format}')],
            key=lambda x: int(re.search(r'\d+', x).group())
        )
        if existing_chapters:
            # Find the last successfully created chapter.
            resume_chapter = max(int(re.search(r'\d+', f).group()) for f in existing_chapters)
            print(f'Resuming from chapter {resume_chapter}')
            # Identify any chapters that are missing before the resume point.
            existing_chapter_numbers = {int(re.search(r'\d+', f).group()) for f in existing_chapters}
            missing_chapters = [i for i in range(1, resume_chapter) if i not in existing_chapter_numbers]
            if resume_chapter not in missing_chapters:
                missing_chapters.append(resume_chapter)
        return missing_chapters, resume_chapter

    def calculate_sentence_resume(self, sentences_dir):
        # Check for already processed sentence audio files.
        resume_sentence = 0
        missing_sentences = []
        existing_sentences = sorted(
            [f for f in os.listdir(sentences_dir) if f.endswith(f'.{default_audio_proc_format}')],
            key=lambda x: int(re.search(r'\d+', x).group())
        )
        if existing_sentences:
            # Find the last successfully created sentence.
            resume_sentence = max(int(re.search(r'\d+', f).group()) for f in existing_sentences)
            print(f"Resuming from sentence {resume_sentence}")
            # Identify any sentences that are missing before the resume point.
            existing_sentence_numbers = {int(re.search(r'\d+', f).group()) for f in existing_sentences}
            missing_sentences = [i for i in range(1, resume_sentence) if i not in existing_sentence_numbers]
            if resume_sentence not in missing_sentences:
                missing_sentences.append(resume_sentence)
        return missing_sentences, resume_sentence

    def _get_audio_duration(self, filepath):
        try:
            ffprobe_cmd = [
                shutil.which('ffprobe'),
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'json',
                filepath
            ]
            result = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
            try:
                return float(json.loads(result.stdout)['format']['duration'])
            except Exception:
                return 0
        except subprocess.CalledProcessError as e:
            util.print_error(e)
            return 0
        except Exception as e:
            error = f"get_audio_duration() Error: Failed to process {filepath}: {e}"
            util.print_error(e, error)
            return 0

    def _generate_ffmpeg_metadata(self, part_chapters_audio_with_title, session, output_metadata_path, default_audio_proc_format):
        """
        Generates an ffmpeg metadata file with chapter markers.

        This method creates a metadata file that includes book details (title, author, etc.)
        and chapter information with start and end times. This file is then used by ffmpeg
        to embed chapters into the final audiobook file.

        Args:
            part_chapters (list): A list of tuples, where each tuple contains the
                                  filename and title of a chapter.
            session (dict): The session object containing metadata and output settings.
            output_metadata_path (str): The path to write the generated metadata file.
            default_audio_proc_format (str): The audio format of the chapter files.

        Returns:
            str or bool: The path to the metadata file if successful, False otherwise.
        """
        try:
            # Determine output format characteristics for correct tagging
            out_fmt = session['output_format']
            is_mp4_like = out_fmt in ['mp4', 'm4a', 'm4b', 'mov']
            is_vorbis = out_fmt in ['ogg', 'webm']  # Vorbis comments use uppercase tags
            is_mp3 = out_fmt == 'mp3'

            # Helper function to format tag keys based on container
            def tag(key):
                return key.upper() if is_vorbis else key

            # Start with the ffmpeg metadata file header
            ffmpeg_metadata = ';FFMETADATA1\n'

            # Add global metadata from the session
            if session['metadata'].get('title'):
                ffmpeg_metadata += f"{tag('title')}={session['metadata']['title']}\n"
            if session['metadata'].get('creator'):
                ffmpeg_metadata += f"{tag('artist')}={session['metadata']['creator']}\n"
            if session['metadata'].get('language'):
                ffmpeg_metadata += f"{tag('language')}={session['metadata']['language']}\n"
            if session['metadata'].get('description'):
                ffmpeg_metadata += f"{tag('description')}={session['metadata']['description']}\n"
            if session['metadata'].get('publisher') and (is_mp4_like or is_mp3):
                ffmpeg_metadata += f"{tag('publisher')}={session['metadata']['publisher']}\n"

            # Extract and format the publication year
            if session['metadata'].get('published'):
                try:
                    # Handle different timestamp formats
                    if '.' in session['metadata']['published']:
                        year = datetime.strptime(session['metadata']['published'], '%Y-%m-%dT%H:%M:%S.%f%z').year
                    else:
                        year = datetime.strptime(session['metadata']['published'], '%Y-%m-%dT%H:%M:%S%z').year
                except Exception:
                    year = datetime.now().year  # Fallback to current year
            else:
                year = datetime.now().year
            
            # Add year/date tag based on format
            if is_vorbis:
                ffmpeg_metadata += f"{tag('date')}={year}\n"
            else:
                ffmpeg_metadata += f"{tag('year')}={year}\n"

            # Add identifiers like ISBN and ASIN if available and supported
            if session['metadata'].get('identifiers') and isinstance(session['metadata']['identifiers'], dict):
                if is_mp3 or is_mp4_like:
                    isbn = session['metadata']['identifiers'].get('isbn')
                    if isbn:
                        ffmpeg_metadata += f"{tag('isbn')}={isbn}\n"
                    asin = session['metadata']['identifiers'].get('mobi-asin')
                    if asin:
                        ffmpeg_metadata += f"{tag('asin')}={asin}\n"

            # Initialize chapter start time
            start_time = 0
            # Iterate through chapters to add their metadata
            for filename, chapter_title in part_chapters_audio_with_title:
                filepath = os.path.join(session['chapters_dir'], filename)
                # Get chapter duration in milliseconds from the audio file
                duration_ms = len(AudioSegment.from_file(filepath, format=default_audio_proc_format))
                # Sanitize chapter title for metadata file (escape special characters)
                clean_title = re.sub(r'(^#)|[=\\]|(-$)', lambda m: '\\' + (m.group(1) or m.group(0)), chapter_title.replace(TTS_SML['pause'], ''))
                
                # Add chapter marker with timebase, start, and end times
                ffmpeg_metadata += '[CHAPTER]\nTIMEBASE=1/1000\n'
                ffmpeg_metadata += f'START={start_time}\nEND={start_time + duration_ms}\n'
                ffmpeg_metadata += f"{tag('title')}={clean_title}\n"
                
                # Update start time for the next chapter
                start_time += duration_ms

            # Write the complete metadata string to the output file
            with open(output_metadata_path, 'w', encoding='utf-8') as f:
                f.write(ffmpeg_metadata)
            return output_metadata_path
        except Exception as e:
            error = f"generate_ffmpeg_metadata() Error: Failed to generate metadata to {output_metadata_path}: {e}"
            util.print_error(e, error)
            return False

    def _export_audiobook(self, input_audio_file, ffmpeg_metadata_file, final_audiobook_output_file, session):
        """
        Exports the final audiobook file using ffmpeg.

        This method takes the combined audio file, applies metadata, cover art, and audio processing,
        and outputs the final audiobook in the desired format.

        Args:
            input_audio_file (str): Path to the combined chapter audio file.
            ffmpeg_metadata_file (str): Path to the ffmpeg metadata file.
            final_audiobook_output_file (str): Path for the final output audiobook file.
            session (dict): The session object containing output settings and metadata.

        Returns:
            bool: True if export is successful, False otherwise.
        """
        try:
            # Check for cancellation request before starting the process
            if session['cancellation_requested']:
                print('Cancel requested')
                return False

            # Initialize the base ffmpeg command
            ffmpeg_cmd = [shutil.which('ffmpeg'), '-hide_banner', '-nostats', '-i', input_audio_file]
            # if session['cover'] is not None:
            cover_path = session.get('cover', None)
            
            # Configure codecs and parameters based on the selected output format
            if session['output_format'] == 'wav':
                # Simple WAV output with specific audio format
                ffmpeg_cmd += ['-map', '0:a', '-ar', '44100', '-sample_fmt', 's16']
            elif session['output_format'] ==  'aac':
                # AAC audio codec with a bitrate of 192k and 44.1kHz sample rate
                ffmpeg_cmd += ['-c:a', 'aac', '-b:a', '192k', '-ar', '44100']
            elif session['output_format'] == 'flac':
                # FLAC lossless audio with compression level 5
                ffmpeg_cmd += ['-c:a', 'flac', '-compression_level', '5', '-ar', '44100', '-sample_fmt', 's16']
            else:
                # For formats that support metadata chapters, add the metadata file
                ffmpeg_cmd += ['-f', 'ffmetadata', '-i', ffmpeg_metadata_file]
                if session['output_format'] in ['m4a', 'm4b', 'mp4', 'mov']:
                    subtitle_file = Path(final_audiobook_output_file).with_suffix(".vtt")
                    if cover_path and os.path.exists(cover_path):
                        # Extract part number from ffmpeg_final_file (e.g., xxx_part01.mp4)
                        part_match = re.search(r'_part(\d+)', final_audiobook_output_file, re.IGNORECASE)
                        if part_match:
                            part_number = int(part_match.group(1))
                            cover_path = self.stamp_on_image_file(cover_path, Path(input_audio_file).with_suffix(".jpg"),str(part_number))
                        ffmpeg_cmd += ['-loop', '1', '-framerate', '1', '-i', cover_path]
                        ffmpeg_cmd += ['-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'stillimage', '-pix_fmt', 'yuv420p']
                        if os.path.exists(subtitle_file):
                            # Use absolute path for subtitle file to be safe
                            subtitle_path_for_filter = Path(subtitle_file).resolve().as_posix().replace(":", "\\:")
                            ffmpeg_cmd += ['-vf', f"subtitles='{subtitle_path_for_filter}':force_style='Fontsize=12,PrimaryColour=&H00FFFF00,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=0',scale=796:1200"]
                        ffmpeg_cmd += ['-shortest']
                        # map the video to the output file
                        ffmpeg_cmd += ['-map', '2:v']

                    # AAC codec for MP4-based containers
                    ffmpeg_cmd += ['-map', '0:a', '-c:a', 'aac', '-b:a', '192k', '-ar', '44100', '-movflags', '+faststart+use_metadata_tags']

                elif session['output_format'] == 'mp3':
                    # MP3 codec using libmp3lame
                    ffmpeg_cmd += ['-map', '0:a', '-c:a', 'libmp3lame', '-b:a', '192k', '-ar', '44100']
                elif session['output_format'] == 'webm':
                    # Opus codec for WebM container, 48kHz sample rate for better quality
                    ffmpeg_cmd += ['-map', '0:a', '-c:a', 'libopus', '-b:a', '192k', '-ar', '48000']
                elif session['output_format'] == 'ogg':
                    # Opus codec for Ogg container
                    ffmpeg_cmd += ['-map', '0:a', '-c:a', 'libopus', '-compression_level', '0', '-b:a', '192k', '-ar', '48000']
                # Map the metadata from the metadata file to the output file
                ffmpeg_cmd += ['-map_metadata', '1']

            # Apply audio filters for normalization and noise reduction
            # loudnorm: EBU R128 loudness normalization
            # afftdn: FFT-based noise reduction
            ffmpeg_cmd += ['-af', 'loudnorm=I=-16:LRA=11:TP=-1.5,afftdn=nf=-70', '-strict', 'experimental', '-threads', '1', '-y', final_audiobook_output_file]

            # Execute the ffmpeg command as a subprocess
            process = subprocess.Popen(
                ffmpeg_cmd,
                env={},
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding='utf-8',
                errors='ignore'
            )

            # Print ffmpeg output in real-time
            for line in process.stdout:
                print(line, end='')
            process.wait()

            # Check if ffmpeg command executed successfully
            if process.returncode == 0:
                # If the output format supports embedded covers, add the cover image
                if session['output_format'] in ['mp3', 'm4a', 'm4b', 'mp4']:
                    if cover_path is not None:
                        print(f'Adding cover {cover_path} into the final audiobook file...')

                        # Use mutagen to embed the cover image
                        if session['output_format'] == 'mp3':
                            from mutagen.mp3 import MP3
                            from mutagen.id3 import ID3, APIC, error
                            audio = MP3(final_audiobook_output_file, ID3=ID3)
                            try:
                                audio.add_tags()
                            except error:
                                pass  # Tags already exist
                            with open(cover_path, 'rb') as img:
                                audio.tags.add(
                                    APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=img.read())
                                )
                        elif session['output_format'] in ['mp4', 'm4a', 'm4b']:
                            from mutagen.mp4 import MP4, MP4Cover
                            audio = MP4(final_audiobook_output_file)

                            with open(cover_path, 'rb') as f:
                                cover_data = f.read()
                                audio["covr"] = [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
                        
                        # Save the file with the embedded cover
                        if audio:
                            audio.save()

                # Move generated subtitle files to the final audiobooks directory
                stem = Path(final_audiobook_output_file).stem
                for ext in ['.vtt', '.srt', '.lrc']:
                    subtitle_file = f"{stem}{ext}"
                    proc_subtitle_path = os.path.join(session['process_dir'], subtitle_file)
                    if os.path.exists(proc_subtitle_path):
                        final_subtitle_path = os.path.join(session['audiobooks_dir'], subtitle_file)
                        shutil.move(proc_subtitle_path, final_subtitle_path)
                return True
            else:
                # If ffmpeg fails, print the error code and the command for debugging
                error = process.returncode
                print(error, ffmpeg_cmd)
                return False
        except Exception as e:
            # Handle any other exceptions, possibly dependency-related
            util.print_error(e)
            return False


    def get_font(self, size=40):
        # Common fonts by OS
        font_paths = []
        system = platform.system()

        if system == "Windows":
            font_paths = [
                "C:\\Windows\\Fonts\\arial.ttf",
                "C:\\Windows\\Fonts\\segoeui.ttf"
            ]
        elif system == "Darwin":  # macOS
            font_paths = [
                "/System/Library/Fonts/Supplemental/Helvetica.ttf",
                "/System/Library/Fonts/Supplemental/Arial.ttf"
            ]
        else:  # Linux
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
            ]

        # Try each font path
        for path in font_paths:
            if os.path.exists(path):
                return ImageFont.truetype(path, size)

        # Fallback
        print("⚠ No system font found, using default font (fixed size).")
        return ImageFont.load_default()

    def stamp_on_image_data(self, image_data: bytes, text: str) -> bytes:
        try:
            img = Image.open(io.BytesIO(image_data))
            draw = ImageDraw.Draw(img)

            # Define font size relative to image width
            font_size = int(img.width / 2)
            font = self.get_font(font_size)


            # text = f"Part {text}"
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]

            # Position text in the top-right corner with a margin
            margin = int(img.width * 0.05)
            position = (img.width - text_width - margin, margin)
            draw.text(position, text, font=font, fill=(255, 0, 0), stroke_width=5, stroke_fill=(0, 0, 0))

            with io.BytesIO() as output:
                img.save(output, format='JPEG')
                image_data = output.getvalue()
        except Exception as e:
            print(f"Could not stamp part number on cover: {e}")
        return image_data

    def stamp_on_image_file(self, input_file: str, output_file: str, stamp_text: str) -> str:
        try:
            img = Image.open(input_file)
            draw = ImageDraw.Draw(img)

            # Define font size relative to image width
            font_size = int(img.width / 2)
            font = self.get_font(font_size)

            text_bbox = draw.textbbox((0, 0), stamp_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]

            # Position text in the top-right corner with a margin
            margin = int(img.width * 0.05)
            position = (img.width - text_width - margin, margin)
            draw.text(position, stamp_text, font=font, fill=(255, 0, 0), stroke_width=5, stroke_fill=(0, 0, 0))

            img.save(output_file, format='JPEG')
            return output_file
        except Exception as e:
            error = f"Could not stamp part number on cover: {e}"
            util.print_error(e, error)
            return None

    def combine_audio_chapters(self, session):
        """
        Combine individual chapter audio files into final audiobook file(s).
        
        This method handles both single-file output and multi-part output based on session settings.
        It performs the following operations:
        1. Gathers all chapter audio files
        2. Calculates total duration to determine if splitting is needed
        3. Splits chapters into parts if required by output_split setting
        4. Processes chapters in batches to avoid memory issues
        5. Merges audio files using ffmpeg
        6. Generates metadata with chapter markers
        7. Exports final file(s) with proper formatting and metadata
        
        Args:
            session (dict): Context object with session management methods
            
        Returns:
            list or None: List of exported file paths, or None if no files were exported
        """
        try:
            proc_chapter_dir = session['chapters_dir']
            
            # Get all chapter audio files and sort them numerically
            chapter_audio_files = [f for f in os.listdir(proc_chapter_dir) if f.endswith(f'.{default_audio_proc_format}')]
            chapter_audio_files = sorted(chapter_audio_files, key=lambda x: int(re.search(r'\d+', x).group()))
            
            # Extract chapter titles from session data
            chapter_titles = [c[0] for c in session['chapters']]
            
            # Check if any chapter files exist
            if len(chapter_audio_files) == 0:
                print('No chapter files exists!')
                return None
            
            # Initialize list to track exported files
            exported_files = []
            
            # Handle multi-part output if splitting is enabled
            if session.get('output_split'):
                split_mins_ = int(session['output_split_minutes'])
                max_part_duration = split_mins_ * 60  # Max duration per part in seconds
                
                # Calculate total duration of all chapters
                chapter_durations = []
                for file in chapter_audio_files:
                    filepath = os.path.join(proc_chapter_dir, file)
                    chapter_durations.append(self._get_audio_duration(filepath))
                total_duration = sum(chapter_durations)
                
                # Determine if splitting is actually needed based on total duration
                total_duration = sum(chapter_durations)
                needs_split = total_duration > (split_mins_ * 2) * 60
                
                if needs_split:
                    if self.combine_to_multiple_audiobook_parts(
                        chapter_audio_files,
                        chapter_titles,
                        chapter_durations,
                        max_part_duration,
                        session,
                        exported_files,
                    ) is None:
                        return None
                    else:
                        return exported_files if exported_files else None

            # Handle single file output (no splitting)
            if self.combine_to_single_audiobook(chapter_audio_files, chapter_titles, session, exported_files) is None:
                return None
            # Return list of exported files or None if no files were exported
            return exported_files if exported_files else None
        except Exception as e:
            util.print_error(e)
            return False

    def combine_to_multiple_audiobook_parts(
        self,
        chapter_audio_files,
        chapter_titles,
        chapter_durations,
        max_part_duration,
        session,
        exported_files,
    ):

        # Initialize variables for splitting chapters into parts
        part_files = []           # List to hold file lists for each part
        part_chapter_indices = [] # List to hold chapter indices for each part
        # part_time_info = []         # item: [start, end, duration]
        cur_part = []             # Current part's file list
        cur_indices = []          # Current part's chapter indices
        cur_duration = 0          # Current part's total duration

        # subtitle_file_base = os.path.join(session['process_dir'], Path(session['final_name']).stem)
        # Distribute chapters into parts based on duration limits
        for idx, (file, dur) in enumerate(zip(chapter_audio_files, chapter_durations)):
            # Start a new part if adding this chapter would exceed the max duration
            if cur_part and (cur_duration + dur > max_part_duration):
                part_files.append(cur_part)
                part_chapter_indices.append(cur_indices)
                cur_part = []
                cur_indices = []
                cur_duration = 0
            # Add current chapter to the current part
            cur_part.append(file)
            cur_indices.append(idx)
            cur_duration += dur
        
        # Add the final part if it contains any chapters
        if cur_part:
            part_files.append(cur_part)
            part_chapter_indices.append(cur_indices)

        # Process each part separately
        for part_idx, (part_file_list, indices) in enumerate(zip(part_files, part_chapter_indices)):
            # Create a temporary directory for processing this part
            with tempfile.TemporaryDirectory() as tmpdir:
                # Process files in batches to avoid command line length limits
                batch_size = 1024
                chunk_list = []
                
                # Split part files into batches and create ffmpeg concat files for each
                for i in range(0, len(part_file_list), batch_size):
                    batch = part_file_list[i:i + batch_size]
                    input_list_file = os.path.join(tmpdir, f'chunk_{i:04d}.txt')
                    out = os.path.join(tmpdir, f'chunk_{i:04d}.{default_audio_proc_format}')
                    
                    # Create ffmpeg concat file for this batch
                    with open(input_list_file, 'w') as f:
                        for file in batch:
                            path = os.path.join(session['chapters_dir'], file).replace("\\", "/")
                            f.write(f"file '{path}'\n")
                    chunk_list.append((input_list_file, out))
                
                # Process all batches in parallel using multiprocessing
                with Pool(cpu_count()) as pool:
                    results = pool.starmap(self.assemble_audio_chunks_with_ffmpeg, chunk_list)
                
                # Check if all batch processing was successful
                if not all(results):
                    print(f"assemble_segments() One or more chunks failed for part {part_idx+1}.")
                    return None
                
                # Create final combined file path for this part
                combined_chapters_file = os.path.join(
                    session['process_dir'],
                    f"{util.sanitize_filename(session['metadata']['title'])}_part{part_idx + 1}.{default_audio_proc_format}"
                )
                
                # Create final concat file listing all processed chunks
                final_list = os.path.join(tmpdir, f'part_{part_idx+1:03d}_final.txt')
                with open(final_list, 'w') as f:
                    for _, chunk_path in chunk_list:
                        f.write(f"file '{chunk_path.replace(os.sep, '/')}'\n")
                
                # Merge all chunks into a single file for this part
                if not self.assemble_audio_chunks_with_ffmpeg(final_list, combined_chapters_file):
                    print(f"assemble_segments() Final merge failed for part {part_idx+1}.")
                    return None

                # Generate metadata file with chapter information for this part
                metadata_file = os.path.join(session['process_dir'], f'metadata_part{part_idx+1}.txt')
                part_chapters = [(chapter_audio_files[i], chapter_titles[i]) for i in indices]
                self._generate_ffmpeg_metadata(part_chapters, session, metadata_file, default_audio_proc_format)

                # Determine final output file path
                audiobook_partl_file_base_name = os.path.join(
                    session['audiobooks_dir'],
                    f"{session['final_name'].rsplit('.', 1)[0]}_part{part_idx+1:03d}"
                )

                self.create_audiobook_part_subtitle(chapter_durations, audiobook_partl_file_base_name, indices, session)

                # Export the final file with metadata and add to exported files list
                final_file = os.path.join(
                    session['audiobooks_dir'],
                    f"{audiobook_partl_file_base_name}.{session['output_format']}"
                )
                if self._export_audiobook(combined_chapters_file, metadata_file, final_file, session):
                    exported_files.append(final_file)
        return True

    def create_audiobook_part_subtitle(self, chapter_durations, final_file_base, indices, session):
        # Split subtitle file for this part
        for ext in ['.vtt', '.srt', '.lrc']:
            original_subtitle_file = os.path.join(session['process_dir'], f"{Path(session['final_name']).stem}{ext}")
            if os.path.exists(original_subtitle_file):
                # Calculate start and end times for this part
                start_time_sec = int(sum(chapter_durations[:indices[0]]) * 100) / 100
                end_time_sec = int(sum(chapter_durations[:indices[-1] + 1]) * 100) / 100

                # Output filename for the split subtitle, aligned with the audio part
                part_subtitle_file = f"{final_file_base}{ext}"

                # ffmpeg command to split subtitle file
                ffmpeg_split_cmd = [
                    shutil.which('ffmpeg'), '-y', '-i', original_subtitle_file,
                    '-ss', str(start_time_sec), '-to', str(end_time_sec),
                    '-c', 'copy', part_subtitle_file
                ]
                try:
                    subprocess.run(ffmpeg_split_cmd, check=True, capture_output=True, text=True)
                    print(f"Successfully created subtitle part: {part_subtitle_file}")
                except subprocess.CalledProcessError as e:
                    print(f"Error splitting subtitle file {original_subtitle_file}: {e.stderr}")

    def combine_to_single_audiobook(self, chapter_audio_files, chapter_titles, session, exported_files):
        # Handle single file output (no splitting)
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1) Create ffmpeg concat file listing all chapter files
            input_list_file = os.path.join(tmpdir, 'all_chapters.txt')
            merged_audio_output_file = os.path.join(tmpdir, f'all.{default_audio_proc_format}')
            with open(input_list_file, 'w') as f:
                for file in chapter_audio_files:
                    path = os.path.join(session['chapters_dir'], file).replace("\\", "/")
                    f.write(f"file '{path}'\n")

            # 2) Merge all chapters into a single temporary file
            if not self.assemble_audio_chunks_with_ffmpeg(input_list_file, merged_audio_output_file):
                print("assemble_segments() Final merge failed.")
                return None

            # 3) Generate metadata file with chapter information for the entire book
            metadata_file = os.path.join(session['process_dir'], 'metadata.txt')
            all_chapters_with_title = list(zip(chapter_audio_files, chapter_titles))
            self._generate_ffmpeg_metadata(all_chapters_with_title, session, metadata_file, default_audio_proc_format)

            # 4) Export the final audiobook file with metadata
            final_audiobook_file = os.path.join(
                session['audiobooks_dir'],
                session['final_name']
            )
            if self._export_audiobook(merged_audio_output_file, metadata_file, final_audiobook_file, session):
                exported_files.append(final_audiobook_file)
        return True

    def assemble_audio_chunks_with_ffmpeg(self, input_audio_chunks_list_file, audio_out_file):
        """
        Assembles audio chunks to format default_audio_proc_format(flac by default) using ffmpeg's concat protocol.

        This method takes a text file containing a list of audio files to be concatenated
        and uses ffmpeg to merge them into a single output file. It's a low-level
        utility function used for combining smaller audio segments, such as sentences
        or chapter batches, into larger audio files.

        Args:
            input_audio_chunks_list_file (str): The path to a text file where each line is `file '/path/to/audio.flac'`.
            audio_out_file (str): The path to the output audio file.

        Returns:
            bool: True if the assembly was successful, False otherwise.
        """
        try:
            # Construct the ffmpeg command for concatenation.
            # -hide_banner, -nostats: Suppress unnecessary console output.
            # -y: Overwrite output file if it exists.
            # -safe 0: Required for using file paths in the concat file that are not in the same directory.
            # -f concat: Use the concat demuxer to read the list of files.
            # -i txt_file: The input text file listing the audio chunks.
            # -c:a default_audio_proc_format: Use the default audio processing format for the output codec.
            # -map_metadata -1: Do not copy metadata from the source files.
            # -threads 1: Use a single thread to avoid potential issues with multithreaded concatenation.
            ffmpeg_cmd = [
                shutil.which('ffmpeg'), '-hide_banner', '-nostats', '-y',
                '-safe', '0', '-f', 'concat', '-i', input_audio_chunks_list_file,
                '-c:a', default_audio_proc_format, '-map_metadata', '-1', '-threads', '1', audio_out_file
            ]
            # Execute the ffmpeg command as a subprocess.
            process = subprocess.Popen(
                ffmpeg_cmd,
                env={},
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding='utf-8',
                errors='ignore'
            )
            # Print ffmpeg's output in real-time.
            for line in process.stdout:
                print(line, end='')  # Print each line of stdout
            # Wait for the process to complete.
            process.wait()
            # Check if ffmpeg executed successfully.
            if process.returncode == 0:
                return True
            else:
                # If ffmpeg fails, print the return code and the command for debugging.
                error = process.returncode
                print(error, ffmpeg_cmd)
                return False
        except subprocess.CalledProcessError as e:
            # Handle errors specific to subprocess execution.
            util.print_error(e)
            return False
        except Exception as e:
            # Handle any other exceptions that may occur.
            error = f"assemble_chunks() Error: Failed to process {input_audio_chunks_list_file} → {audio_out_file}: {e}"
            util.print_error(e, error)
            return False

    def combine_audio_sentences(self, chapter_audio_file: str, audio_file_start: int, audio_file_end: int, session: dict) -> bool:
        """
        Combine per-sentence audio files into one chapter audio file.

        The method slices the sentence-audio directory by numeric filename range, concatenates
        them in order, and writes a single chapter file using ffmpeg's concat demuxer.

        Args:
            chapter_audio_file (str): Output filename for the combined chapter audio.
            start (int): First sentence index (inclusive) to include.
            end (int): Last sentence index (inclusive) to include.
            session (dict): Session configuration with chapter paths and settings.

        Returns:
            bool: True if all chunks and the final merge succeed, otherwise False.
        """
        try:
            chapter_audio_file = os.path.join(session['chapters_dir'], chapter_audio_file)
            chapters_dir_sentences = session['chapters_dir_sentences']
            batch_size = 1024
            sentence_files = [
                f for f in os.listdir(chapters_dir_sentences)
                if f.endswith(f'.{default_audio_proc_format}')
            ]
            sentences_ordered = sorted(
                sentence_files, key=lambda x: int(os.path.splitext(x)[0])
            )
            selected_files = [
                os.path.join(chapters_dir_sentences, f)
                for f in sentences_ordered
                if audio_file_start <= int(os.path.splitext(f)[0]) <= audio_file_end
            ]
            if not selected_files:
                print('No audio files found in the specified range.')
                return False
            # Use a temporary directory to store intermediate concat lists and chunk outputs.
            # This keeps the workspace clean and ensures automatic cleanup even on exceptions.
            with tempfile.TemporaryDirectory() as tmpdir:
                chunk_list = []
                # Split into fixed-size batches to avoid very long concat lists and huge ffmpeg
                # command inputs. Each batch becomes a small merged chunk file.
                for i in range(0, len(selected_files), batch_size):
                    batch = selected_files[i:i + batch_size]
                    input_auiod_files_list_per_batch = os.path.join(tmpdir, f'chunk_{i:04d}.txt')
                    output_audio_file_per_batch = os.path.join(tmpdir, f'chunk_{i:04d}.{default_audio_proc_format}')
                    with open(input_auiod_files_list_per_batch, 'w') as f:
                        for file in batch:
                            f.write(f"file '{file.replace(os.sep, '/')}'\n")
                    chunk_list.append((input_auiod_files_list_per_batch, output_audio_file_per_batch))
                    
                try:
                    # Create a worker process pool sized to the CPU count. Each worker runs
                    # assemble_audio_chunks_with_ffmpeg(txt, out) for one tuple in chunk_list.
                    # starmap expands each tuple to positional args, so the function receives
                    # the correct (input_list_file, output_file) pair per chunk.
                    #
                    # This is multiprocessing (separate processes), not multithreading, so
                    # ffmpeg runs in parallel without GIL contention. The pool is closed and
                    # joined when leaving the context manager.
                    with Pool(cpu_count()) as pool:
                        parallel_proc_results = pool.starmap(self.assemble_audio_chunks_with_ffmpeg, chunk_list)
                        
                    # pool.starmap 是阻塞调用，执行到这里表示所有worker都已完成
                    if not all(parallel_proc_results):
                        error = "combine_audio_sentences() One or more chunks failed."
                        print(error)
                        return False
                    
                    # todo: 删除所有已经合并过的源音频文件
                    # for file_path in selected_files:
                    #             try:
                    #                 if os.path.exists(file_path):
                    #                     os.remove(file_path)
                    #             except Exception as e:
                    #                 util.print_error(f"Failed to delete {file_path}: {e}")
                    
                except Exception as e:
                    error = f"combine_audio_sentences() multiprocessing error: {e}"
                    util.print_error(e, error)
                    return False
                
                # Final merge
                final_list = os.path.join(tmpdir, 'sentences_final.txt')
                with open(final_list, 'w') as f:
                    for _, chunk_path in chunk_list:
                        f.write(f"file '{chunk_path.replace(os.sep, '/')}'\n")
                if self.assemble_audio_chunks_with_ffmpeg(final_list, chapter_audio_file):
                    msg = f'********* Combined chapter audio file saved in {chapter_audio_file}'
                    print(msg)
                    return True
                else:
                    error = "combine_audio_sentences() Final merge failed."
                    print(error)
                    return False
        except Exception as e:
            util.print_error(e)
            return False                    

