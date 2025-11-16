import os
import torch
import regex as re
import stanza

from lib.models import loaded_tts, max_tts_in_memory, TTS_ENGINES

def unload_tts(device, reserved_keys=None, tts_key=None):
    try:
        if len(loaded_tts) >= max_tts_in_memory:
            if reserved_keys is None:
                reserved_keys = []
            if tts_key is not None:
                if tts_key in loaded_tts.keys():
                    del loaded_tts[tts_key]
                if device == 'cuda':
                    torch.cuda.empty_cache()
                    torch.cuda.ipc_collect()
            else:
                for key in list(loaded_tts.keys()):
                    if key not in reserved_keys:
                        del loaded_tts[key]
    except Exception as e:
        error = f'unload_tts() error: {e}'
        print(error)
        return False
        
def append_sentence2vtt(sentence_obj, path):
    """
    Appends a sentence object to VTT, SRT, and LRC subtitle files.

    This function takes a sentence object and appends it as a new entry to the
    specified VTT file, and also creates and appends to corresponding SRT and
    LRC files. It handles file creation, timestamp formatting, and indexing.

    Args:
        sentence_obj (dict): A dictionary with sentence information, including
                             "start", "end", "text", and optional "resume_check".
        path (str): The file path for the VTT file. SRT and LRC files will be
                    created with the same base name.

    Returns:
        int or False: The index for the next entry, or False on error.
    """
    base_path, _ = os.path.splitext(path)
    srt_path = base_path + ".srt"
    lrc_path = base_path + ".lrc"

    def format_vtt_timestamp(seconds):
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{int(h):02}:{int(m):02}:{s:06.3f}"

    def format_srt_timestamp(seconds):
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{int(h):02}:{int(m):02}:{int(s):02},{int((s % 1) * 1000):03}"

    def format_lrc_timestamp(seconds):
        m, s = divmod(seconds, 60)
        return f"[{int(m):02}:{s:05.2f}]"

    try:
        index = 1
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines:
                    if "-->" in line:
                        index += 1
        
        if index > 1 and "resume_check" in sentence_obj and sentence_obj["resume_check"] < index:
            return index

        text = re.sub(r'[\r\n]+', ' ', sentence_obj["text"]).strip()
        start_time = sentence_obj["start"]
        end_time = sentence_obj["end"]

        # VTT
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write("WEBVTT\n\n")
        with open(path, "a", encoding="utf-8") as f:
            start = format_vtt_timestamp(start_time)
            end = format_vtt_timestamp(end_time)
            f.write(f"{start} --> {end}\n{text}\n\n")

        # SRT
        with open(srt_path, "a", encoding="utf-8") as f:
            start = format_srt_timestamp(start_time)
            end = format_srt_timestamp(end_time)
            f.write(f"{index}\n{start} --> {end}\n{text}\n\n")

        # LRC
        with open(lrc_path, "a", encoding="utf-8") as f:
            start = format_lrc_timestamp(start_time)
            f.write(f"{start}{text}\n")

        return index + 1
    except Exception as e:
        error = f'append_sentence2vtt() error: {e}'
        print(error)
        return False
