import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime
from multiprocessing import cpu_count, Pool
from pathlib import Path

from pydub import AudioSegment

from lib import TTS_SML, default_audio_proc_format
from lib.functions import DependencyError

class EbookAudio:
    is_gui_process = False

    def get_sanitized(self, str, replacement="_"):
        str = str.replace('&', 'And')
        forbidden_chars = r'[<>:"/\\|?*\x00-\x1F ()]'
        sanitized = re.sub(r'\s+', replacement, str)
        sanitized = re.sub(forbidden_chars, replacement, sanitized)
        sanitized = sanitized.strip("_")
        return sanitized

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
            DependencyError(e)
            return 0
        except Exception as e:
            error = f"get_audio_duration() Error: Failed to process {filepath}: {e}"
            print(error)
            return 0

    def _generate_ffmpeg_metadata(self, part_chapters, session, output_metadata_path, default_audio_proc_format):
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
            for filename, chapter_title in part_chapters:
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
            print(error)
            return False

    def _export_audio(self, ffmpeg_combined_audio, ffmpeg_metadata_file, ffmpeg_final_file, session):
        """
        Exports the final audiobook file using ffmpeg.

        This method takes the combined audio file, applies metadata, cover art, and audio processing,
        and outputs the final audiobook in the desired format.

        Args:
            ffmpeg_combined_audio (str): Path to the combined chapter audio file.
            ffmpeg_metadata_file (str): Path to the ffmpeg metadata file.
            ffmpeg_final_file (str): Path for the final output audiobook file.
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
            ffmpeg_cmd = [shutil.which('ffmpeg'), '-hide_banner', '-nostats', '-i', ffmpeg_combined_audio]

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
                ffmpeg_cmd += ['-f', 'ffmetadata', '-i', ffmpeg_metadata_file, '-map', '0:a']
                if session['output_format'] in ['m4a', 'm4b', 'mp4', 'mov']:
                    # AAC codec for MP4-based containers
                    ffmpeg_cmd += ['-c:a', 'aac', '-b:a', '192k', '-ar', '44100', '-movflags', '+faststart+use_metadata_tags']
                elif session['output_format'] == 'mp3':
                    # MP3 codec using libmp3lame
                    ffmpeg_cmd += ['-c:a', 'libmp3lame', '-b:a', '192k', '-ar', '44100']
                elif session['output_format'] == 'webm':
                    # Opus codec for WebM container, 48kHz sample rate for better quality
                    ffmpeg_cmd += ['-c:a', 'libopus', '-b:a', '192k', '-ar', '48000']
                elif session['output_format'] == 'ogg':
                    # Opus codec for Ogg container
                    ffmpeg_cmd += ['-c:a', 'libopus', '-compression_level', '0', '-b:a', '192k', '-ar', '48000']
                # Map the metadata from the metadata file to the output file
                ffmpeg_cmd += ['-map_metadata', '1']

            # Apply audio filters for normalization and noise reduction
            # loudnorm: EBU R128 loudness normalization
            # afftdn: FFT-based noise reduction
            ffmpeg_cmd += ['-af', 'loudnorm=I=-16:LRA=11:TP=-1.5,afftdn=nf=-70', '-strict', 'experimental', '-threads', '1', '-y', ffmpeg_final_file]

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
                    if session['cover'] is not None:
                        cover_path = session['cover']
                        print(f'Adding cover {cover_path} into the final audiobook file...')

                        # Use mutagen to embed the cover image
                        if session['output_format'] == 'mp3':
                            from mutagen.mp3 import MP3
                            from mutagen.id3 import ID3, APIC, error
                            audio = MP3(ffmpeg_final_file, ID3=ID3)
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
                            audio = MP4(ffmpeg_final_file)
                            with open(cover_path, 'rb') as f:
                                cover_data = f.read()
                            audio["covr"] = [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
                        
                        # Save the file with the embedded cover
                        if audio:
                            audio.save()

                # Move the generated VTT subtitle file to the final audiobooks directory
                final_vtt = f"{Path(ffmpeg_final_file).stem}.vtt"
                proc_vtt_path = os.path.join(session['process_dir'], final_vtt)
                final_vtt_path = os.path.join(session['audiobooks_dir'], final_vtt)
                shutil.move(proc_vtt_path, final_vtt_path)
                return True
            else:
                # If ffmpeg fails, print the error code and the command for debugging
                error = process.returncode
                print(error, ffmpeg_cmd)
                return False
        except Exception as e:
            # Handle any other exceptions, possibly dependency-related
            DependencyError(e)
            return False

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
            # Retrieve session data using the provided ID
            # session = context.get_session(id)
            _cdir = session['chapters_dir']
            
            # Get all chapter audio files and sort them numerically
            chapter_files = [f for f in os.listdir(_cdir) if f.endswith(f'.{default_audio_proc_format}')]
            chapter_files = sorted(chapter_files, key=lambda x: int(re.search(r'\d+', x).group()))
            
            # Extract chapter titles from session data
            chapter_titles = [c[0] for c in session['chapters']]
            
            # Check if any chapter files exist
            if len(chapter_files) == 0:
                print('No chapter files exists!')
                return None
            
            # Calculate total duration of all chapters
            durations = []
            for file in chapter_files:
                filepath = os.path.join(session['chapters_dir'], file)
                durations.append(self._get_audio_duration(filepath))
            total_duration = sum(durations)
            
            # Initialize list to track exported files
            exported_files = []
            
            # Handle multi-part output if splitting is enabled
            if session.get('output_split'):
                # Initialize variables for splitting chapters into parts
                part_files = []           # List to hold file lists for each part
                part_chapter_indices = [] # List to hold chapter indices for each part
                cur_part = []             # Current part's file list
                cur_indices = []          # Current part's chapter indices
                cur_duration = 0          # Current part's total duration
                max_part_duration = session['output_split_hours'] * 3600  # Max duration per part in seconds
                # Determine if splitting is actually needed based on total duration
                needs_split = total_duration > (int(session['output_split_hours']) * 2) * 3600
                
                # Distribute chapters into parts based on duration limits
                for idx, (file, dur) in enumerate(zip(chapter_files, durations)):
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
                            txt = os.path.join(tmpdir, f'chunk_{i:04d}.txt')
                            out = os.path.join(tmpdir, f'chunk_{i:04d}.{default_audio_proc_format}')
                            
                            # Create ffmpeg concat file for this batch
                            with open(txt, 'w') as f:
                                for file in batch:
                                    path = os.path.join(session['chapters_dir'], file).replace("\\", "/")
                                    f.write(f"file '{path}'\n")
                            chunk_list.append((txt, out))
                        
                        # Process all batches in parallel using multiprocessing
                        with Pool(cpu_count()) as pool:
                            results = pool.starmap(self.assemble_chunks, chunk_list)
                        
                        # Check if all batch processing was successful
                        if not all(results):
                            print(f"assemble_segments() One or more chunks failed for part {part_idx+1}.")
                            return None
                        
                        # Create final combined file path for this part
                        combined_chapters_file = os.path.join(
                            session['process_dir'],
                            f"{self.get_sanitized(session['metadata']['title'])}_part{part_idx+1}.{default_audio_proc_format}" if needs_split else f"{self.get_sanitized(session['metadata']['title'])}.{default_audio_proc_format}"
                        )
                        
                        # Create final concat file listing all processed chunks
                        final_list = os.path.join(tmpdir, f'part_{part_idx+1:02d}_final.txt')
                        with open(final_list, 'w') as f:
                            for _, chunk_path in chunk_list:
                                f.write(f"file '{chunk_path.replace(os.sep, '/')}'\n")
                        
                        # Merge all chunks into a single file for this part
                        if not self.assemble_chunks(final_list, combined_chapters_file):
                            print(f"assemble_segments() Final merge failed for part {part_idx+1}.")
                            return None

                        # Generate metadata file with chapter information for this part
                        metadata_file = os.path.join(session['process_dir'], f'metadata_part{part_idx+1}.txt')
                        part_chapters = [(chapter_files[i], chapter_titles[i]) for i in indices]
                        self._generate_ffmpeg_metadata(part_chapters, session, metadata_file, default_audio_proc_format)

                        # Determine final output file path
                        final_file = os.path.join(
                            session['audiobooks_dir'],
                            f"{session['final_name'].rsplit('.', 1)[0]}_part{part_idx+1}.{session['output_format']}" if needs_split else session['final_name']
                        )
                        
                        # Export the final file with metadata and add to exported files list
                        if self._export_audio(combined_chapters_file, metadata_file, final_file, session):
                            exported_files.append(final_file)
            else:
                # Handle single file output (no splitting)
                with tempfile.TemporaryDirectory() as tmpdir:
                    # 1) Create ffmpeg concat file listing all chapter files
                    txt = os.path.join(tmpdir, 'all_chapters.txt')
                    merged_tmp = os.path.join(tmpdir, f'all.{default_audio_proc_format}')
                    with open(txt, 'w') as f:
                        for file in chapter_files:
                            path = os.path.join(session['chapters_dir'], file).replace("\\", "/")
                            f.write(f"file '{path}'\n")

                    # 2) Merge all chapters into a single temporary file
                    if not self.assemble_chunks(txt, merged_tmp):
                        print("assemble_segments() Final merge failed.")
                        return None

                    # 3) Generate metadata file with chapter information for the entire book
                    metadata_file = os.path.join(session['process_dir'], 'metadata.txt')
                    all_chapters = list(zip(chapter_files, chapter_titles))
                    self._generate_ffmpeg_metadata(all_chapters, session, metadata_file, default_audio_proc_format)

                    # 4) Export the final audiobook file with metadata
                    final_file = os.path.join(
                        session['audiobooks_dir'],
                        session['final_name']
                    )
                    if self._export_audio(merged_tmp, metadata_file, final_file, session):
                        exported_files.append(final_file)
            
            # Return list of exported files or None if no files were exported
            return exported_files if exported_files else None
        except Exception as e:
            DependencyError(e)
            return False

    def assemble_chunks(self, txt_file, out_file):
        try:
            ffmpeg_cmd = [
                shutil.which('ffmpeg'), '-hide_banner', '-nostats', '-y',
                '-safe', '0', '-f', 'concat', '-i', txt_file,
                '-c:a', default_audio_proc_format, '-map_metadata', '-1', '-threads', '1', out_file
            ]
            process = subprocess.Popen(
                ffmpeg_cmd,
                env={},
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding='utf-8',
                errors='ignore'
            )
            for line in process.stdout:
                print(line, end='')  # Print each line of stdout
            process.wait()
            if process.returncode == 0:
                return True
            else:
                error = process.returncode
                print(error, ffmpeg_cmd)
                return False
        except subprocess.CalledProcessError as e:
            DependencyError(e)
            return False
        except Exception as e:
            error = f"assemble_chanks() Error: Failed to process {txt_file} → {out_file}: {e}"
            print(error)
            return False

    def combine_audio_sentences(self, chapter_audio_file, start, end, session):
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
                if start <= int(os.path.splitext(f)[0]) <= end
            ]
            if not selected_files:
                print('No audio files found in the specified range.')
                return False
            with tempfile.TemporaryDirectory() as tmpdir:
                chunk_list = []
                for i in range(0, len(selected_files), batch_size):
                    batch = selected_files[i:i + batch_size]
                    txt = os.path.join(tmpdir, f'chunk_{i:04d}.txt')
                    out = os.path.join(tmpdir, f'chunk_{i:04d}.{default_audio_proc_format}')
                    with open(txt, 'w') as f:
                        for file in batch:
                            f.write(f"file '{file.replace(os.sep, '/')}'\n")
                    chunk_list.append((txt, out))
                try:
                    with Pool(cpu_count()) as pool:
                        results = pool.starmap(self.assemble_chunks, chunk_list)
                except Exception as e:
                    error = f"combine_audio_sentences() multiprocessing error: {e}"
                    print(error)
                    return False
                if not all(results):
                    error = "combine_audio_sentences() One or more chunks failed."
                    print(error)
                    return False
                # Final merge
                final_list = os.path.join(tmpdir, 'sentences_final.txt')
                with open(final_list, 'w') as f:
                    for _, chunk_path in chunk_list:
                        f.write(f"file '{chunk_path.replace(os.sep, '/')}'\n")
                if self.assemble_chunks(final_list, chapter_audio_file):
                    msg = f'********* Combined chapter audio file saved in {chapter_audio_file}'
                    print(msg)
                    return True
                else:
                    error = "combine_audio_sentences() Final merge failed."
                    print(error)
                    return False
        except Exception as e:
            DependencyError(e)
            return False
