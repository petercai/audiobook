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

is_gui_process = False

class DependencyError(Exception):
    def __init__(self, message=None):
        super().__init__(message)
        print(message)
        # Automatically handle the exception when it's raised
        self.handle_exception()

    def handle_exception(self):
        # Print the full traceback of the exception
        traceback.print_exc()      
        # Print the exception message
        error = f'Caught DependencyError: {self}'
        print(error)    
        # Exit the script if it's not a web process
        if not is_gui_process:
            sys.exit(1)

def get_sanitized(str, replacement="_"):
    str = str.replace('&', 'And')
    forbidden_chars = r'[<>:"/\\|?*\x00-\x1F ()]'
    sanitized = re.sub(r'\s+', replacement, str)
    sanitized = re.sub(forbidden_chars, replacement, sanitized)
    sanitized = sanitized.strip("_")
    return sanitized


def combine_audio_chapters(id, context):

    def get_audio_duration(filepath):
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

    def generate_ffmpeg_metadata(part_chapters, session, output_metadata_path, default_audio_proc_format):
        try:
            out_fmt = session['output_format']
            is_mp4_like = out_fmt in ['mp4', 'm4a', 'm4b', 'mov']
            is_vorbis = out_fmt in ['ogg', 'webm']
            is_mp3 = out_fmt == 'mp3'
            def tag(key):
                return key.upper() if is_vorbis else key
            ffmpeg_metadata = ';FFMETADATA1\n'
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
            if session['metadata'].get('published'):
                try:
                    if '.' in session['metadata']['published']:
                        year = datetime.strptime(session['metadata']['published'], '%Y-%m-%dT%H:%M:%S.%f%z').year
                    else:
                        year = datetime.strptime(session['metadata']['published'], '%Y-%m-%dT%H:%M:%S%z').year
                except Exception:
                    year = datetime.now().year
            else:
                year = datetime.now().year
            if is_vorbis:
                ffmpeg_metadata += f"{tag('date')}={year}\n"
            else:
                ffmpeg_metadata += f"{tag('year')}={year}\n"
            if session['metadata'].get('identifiers') and isinstance(session['metadata']['identifiers'], dict):
                if is_mp3 or is_mp4_like:
                    isbn = session['metadata']['identifiers'].get('isbn')
                    if isbn:
                        ffmpeg_metadata += f"{tag('isbn')}={isbn}\n"
                    asin = session['metadata']['identifiers'].get('mobi-asin')
                    if asin:
                        ffmpeg_metadata += f"{tag('asin')}={asin}\n"
            start_time = 0
            for filename, chapter_title in part_chapters:
                filepath = os.path.join(session['chapters_dir'], filename)
                duration_ms = len(AudioSegment.from_file(filepath, format=default_audio_proc_format))
                clean_title = re.sub(r'(^#)|[=\\]|(-$)', lambda m: '\\' + (m.group(1) or m.group(0)), chapter_title.replace(TTS_SML['pause'], ''))
                ffmpeg_metadata += '[CHAPTER]\nTIMEBASE=1/1000\n'
                ffmpeg_metadata += f'START={start_time}\nEND={start_time + duration_ms}\n'
                ffmpeg_metadata += f"{tag('title')}={clean_title}\n"
                start_time += duration_ms
            with open(output_metadata_path, 'w', encoding='utf-8') as f:
                f.write(ffmpeg_metadata)
            return output_metadata_path
        except Exception as e:
            error = f"generate_ffmpeg_metadata() Error: Failed to generate metadata to {output_metadata_path}: {e}"
            print(error)
            return False

    def export_audio(ffmpeg_combined_audio, ffmpeg_metadata_file, ffmpeg_final_file):
        try:
            if session['cancellation_requested']:
                print('Cancel requested')
                return False
            cover_path = None
            ffmpeg_cmd = [shutil.which('ffmpeg'), '-hide_banner', '-nostats', '-i', ffmpeg_combined_audio]
            if session['output_format'] == 'wav':
                ffmpeg_cmd += ['-map', '0:a', '-ar', '44100', '-sample_fmt', 's16']
            elif session['output_format'] ==  'aac':
                ffmpeg_cmd += ['-c:a', 'aac', '-b:a', '192k', '-ar', '44100']
            elif session['output_format'] == 'flac':
                ffmpeg_cmd += ['-c:a', 'flac', '-compression_level', '5', '-ar', '44100', '-sample_fmt', 's16']
            else:
                ffmpeg_cmd += ['-f', 'ffmetadata', '-i', ffmpeg_metadata_file, '-map', '0:a']
                if session['output_format'] in ['m4a', 'm4b', 'mp4', 'mov']:
                    ffmpeg_cmd += ['-c:a', 'aac', '-b:a', '192k', '-ar', '44100', '-movflags', '+faststart+use_metadata_tags']
                elif session['output_format'] == 'mp3':
                    ffmpeg_cmd += ['-c:a', 'libmp3lame', '-b:a', '192k', '-ar', '44100']
                elif session['output_format'] == 'webm':
                    ffmpeg_cmd += ['-c:a', 'libopus', '-b:a', '192k', '-ar', '48000']
                elif session['output_format'] == 'ogg':
                    ffmpeg_cmd += ['-c:a', 'libopus', '-compression_level', '0', '-b:a', '192k', '-ar', '48000']
                ffmpeg_cmd += ['-map_metadata', '1']
            ffmpeg_cmd += ['-af', 'loudnorm=I=-16:LRA=11:TP=-1.5,afftdn=nf=-70', '-strict', 'experimental', '-threads', '1', '-y', ffmpeg_final_file]
            process = subprocess.Popen(
                ffmpeg_cmd,
                env={},
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding='utf-8',
                errors='ignore'
            )
            for line in process.stdout:
                print(line, end='')
            process.wait()
            if process.returncode == 0:
                if session['output_format'] in ['mp3', 'm4a', 'm4b', 'mp4']:
                    if session['cover'] is not None:
                        cover_path = session['cover']
                        msg = f'Adding cover {cover_path} into the final audiobook file...'
                        print(msg)
                        if session['output_format'] == 'mp3':
                            from mutagen.mp3 import MP3
                            from mutagen.id3 import ID3, APIC, error
                            audio = MP3(ffmpeg_final_file, ID3=ID3)
                            try:
                                audio.add_tags()
                            except error:
                                pass
                            with open(cover_path, 'rb') as img:
                                audio.tags.add(
                                    APIC(
                                        encoding=3,
                                        mime='image/jpeg',
                                        type=3,
                                        desc='Cover',
                                        data=img.read()
                                    )
                                )
                        elif session['output_format'] in ['mp4', 'm4a', 'm4b']:
                            from mutagen.mp4 import MP4, MP4Cover
                            audio = MP4(ffmpeg_final_file)
                            with open(cover_path, 'rb') as f:
                                cover_data = f.read()
                            audio["covr"] = [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
                        if audio:
                            audio.save()
                final_vtt = f"{Path(ffmpeg_final_file).stem}.vtt"
                proc_vtt_path = os.path.join(session['process_dir'], final_vtt)
                final_vtt_path = os.path.join(session['audiobooks_dir'], final_vtt)
                shutil.move(proc_vtt_path, final_vtt_path)
                return True
            else:
                error = process.returncode
                print(error, ffmpeg_cmd)
                return False
        except Exception as e:
            DependencyError(e)
            return False

    try:
        session = context.get_session(id)
        _cdir = session['chapters_dir']
        chapter_files = [f for f in os.listdir(_cdir) if f.endswith(f'.{default_audio_proc_format}')]
        chapter_files = sorted(chapter_files, key=lambda x: int(re.search(r'\d+', x).group()))
        chapter_titles = [c[0] for c in session['chapters']]
        if len(chapter_files) == 0:
            print('No chapter files exists!')
            return None
        # Calculate total duration
        durations = []
        for file in chapter_files:
            filepath = os.path.join(session['chapters_dir'], file)
            durations.append(get_audio_duration(filepath))
        total_duration = sum(durations)
        exported_files = []
        if session.get('output_split'):
            part_files = []
            part_chapter_indices = []
            cur_part = []
            cur_indices = []
            cur_duration = 0
            max_part_duration = session['output_split_hours'] * 3600
            needs_split = total_duration > (int(session['output_split_hours']) * 2) * 3600
            for idx, (file, dur) in enumerate(zip(chapter_files, durations)):
                if cur_part and (cur_duration + dur > max_part_duration):
                    part_files.append(cur_part)
                    part_chapter_indices.append(cur_indices)
                    cur_part = []
                    cur_indices = []
                    cur_duration = 0
                cur_part.append(file)
                cur_indices.append(idx)
                cur_duration += dur
            if cur_part:
                part_files.append(cur_part)
                part_chapter_indices.append(cur_indices)

            for part_idx, (part_file_list, indices) in enumerate(zip(part_files, part_chapter_indices)):
                with tempfile.TemporaryDirectory() as tmpdir:
                    batch_size = 1024
                    chunk_list = []
                    for i in range(0, len(part_file_list), batch_size):
                        batch = part_file_list[i:i + batch_size]
                        txt = os.path.join(tmpdir, f'chunk_{i:04d}.txt')
                        out = os.path.join(tmpdir, f'chunk_{i:04d}.{default_audio_proc_format}')
                        with open(txt, 'w') as f:
                            for file in batch:
                                path = os.path.join(session['chapters_dir'], file).replace("\\", "/")
                                f.write(f"file '{path}'\n")
                        chunk_list.append((txt, out))
                    with Pool(cpu_count()) as pool:
                        results = pool.starmap(assemble_chunks, chunk_list)
                    if not all(results):
                        print(f"assemble_segments() One or more chunks failed for part {part_idx+1}.")
                        return None
                    # Final merge for this part
                    combined_chapters_file = os.path.join(
                        session['process_dir'],
                        f"{get_sanitized(session['metadata']['title'])}_part{part_idx+1}.{default_audio_proc_format}" if needs_split else f"{get_sanitized(session['metadata']['title'])}.{default_audio_proc_format}"
                    )
                    final_list = os.path.join(tmpdir, f'part_{part_idx+1:02d}_final.txt')
                    with open(final_list, 'w') as f:
                        for _, chunk_path in chunk_list:
                            f.write(f"file '{chunk_path.replace(os.sep, '/')}'\n")
                    if not assemble_chunks(final_list, combined_chapters_file):
                        print(f"assemble_segments() Final merge failed for part {part_idx+1}.")
                        return None

                    metadata_file = os.path.join(session['process_dir'], f'metadata_part{part_idx+1}.txt')
                    part_chapters = [(chapter_files[i], chapter_titles[i]) for i in indices]
                    generate_ffmpeg_metadata(part_chapters, session, metadata_file, default_audio_proc_format)

                    final_file = os.path.join(
                        session['audiobooks_dir'],
                        f"{session['final_name'].rsplit('.', 1)[0]}_part{part_idx+1}.{session['output_format']}" if needs_split else session['final_name']
                    )
                    if export_audio(combined_chapters_file, metadata_file, final_file):
                        exported_files.append(final_file)
        else:
            with tempfile.TemporaryDirectory() as tmpdir:
                # 1) build a single ffmpeg file list
                txt = os.path.join(tmpdir, 'all_chapters.txt')
                merged_tmp = os.path.join(tmpdir, f'all.{default_audio_proc_format}')
                with open(txt, 'w') as f:
                    for file in chapter_files:
                        path = os.path.join(session['chapters_dir'], file).replace("\\", "/")
                        f.write(f"file '{path}'\n")

                # 2) merge into one temp file
                if not assemble_chunks(txt, merged_tmp):
                    print("assemble_segments() Final merge failed.")
                    return None

                # 3) generate metadata for entire book
                metadata_file = os.path.join(session['process_dir'], 'metadata.txt')
                all_chapters = list(zip(chapter_files, chapter_titles))
                generate_ffmpeg_metadata(all_chapters, session, metadata_file, default_audio_proc_format)

                # 4) export in one go
                final_file = os.path.join(
                    session['audiobooks_dir'],
                    session['final_name']
                )
                if export_audio(merged_tmp, metadata_file, final_file):
                    exported_files.append(final_file)
        return exported_files if exported_files else None
    except Exception as e:
        DependencyError(e)
        return False


def assemble_chunks(txt_file, out_file):
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

def combine_audio_sentences(chapter_audio_file, start, end, session):
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
                    results = pool.starmap(assemble_chunks, chunk_list)
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
            if assemble_chunks(final_list, chapter_audio_file):
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
