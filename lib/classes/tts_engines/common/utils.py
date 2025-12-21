import os
import torch
import regex as re

from lib.models import loaded_tts, max_tts_in_memory, tts_lock

def unload_tts(device, reserved_keys=None, tts_key=None):
    """
    Unloads TTS models from memory to manage resource usage.

    This function can operate in two modes:
    1. Unload a specific model by providing `tts_key`.
    2. Free up memory by unloading models if the cache size exceeds `max_tts_in_memory`.
       In this mode, it preserves models whose keys are in `reserved_keys`.

    It is thread-safe and handles CUDA cache clearing.

    Args:
        device (str): The device ('cuda' or 'cpu') from which to unload.
        reserved_keys (list, optional): A list of keys for models to keep in memory.
        tts_key (str, optional): The key of a specific model to unload.

    Returns:
        bool: True on success, False on failure.
    """    
    try:
        with tts_lock:
            # Case 1: Unload a specific model if tts_key is provided.
            if tts_key is not None:
                if tts_key in loaded_tts:
                    del loaded_tts[tts_key]
                    if device == 'cuda':
                        torch.cuda.empty_cache()
                        torch.cuda.ipc_collect()
                return True

            # Case 2: Free up memory if the cache is full.
            if len(loaded_tts) >= max_tts_in_memory:
                if reserved_keys is None:
                    reserved_keys = []
                
                unloaded_something = False
                for key in list(loaded_tts.keys()):
                    if key not in reserved_keys:
                        del loaded_tts[key]
                        unloaded_something = True
                
                if unloaded_something and device == 'cuda':        
                    torch.cuda.empty_cache()
                    torch.cuda.ipc_collect()
    except Exception as e:
        error = f'unload_tts() error: {e}'
        print(error)
        return False
    return True


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
