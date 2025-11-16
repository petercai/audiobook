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
    Appends a sentence object to a VTT (Web Video Text Tracks) file.

    This function takes a sentence object containing text, start time, and end time,
    and appends it as a new subtitle entry to the specified VTT file. It handles
    file creation, timestamp formatting, and indexing of subtitle entries. It also
    includes a check to prevent duplicate entries when resuming an operation.

    Args:
        sentence_obj (dict): A dictionary containing sentence information.
            Expected keys:
            - "start" (float): The start time of the sentence in seconds.
            - "end" (float): The end time of the sentence in seconds.
            - "text" (str): The text of the sentence.
            - "resume_check" (int, optional): An index used to check if the
              sentence has already been written to the file.
        path (str): The file path for the VTT file.

    Returns:
        int or False: The index of the next entry to be written, or False if an
                      error occurs. If the sentence has already been written,
                      it returns the current index.
    """

    def format_timestamp(seconds):
        """Converts seconds to a VTT-compliant timestamp string (HH:MM:SS.mmm)."""
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return f"{int(h):02}:{int(m):02}:{s:06.3f}"

    try:
        # Initialize the subtitle entry index.
        index = 1
        # If the VTT file already exists, count the number of existing entries.
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines:
                    # Each timestamp line ("-->") signifies a subtitle entry.
                    if "-->" in line:
                        index += 1
        
        # If resuming, check if this sentence has already been written.
        if index > 1 and "resume_check" in sentence_obj and sentence_obj["resume_check"] < index:
            return index  # Return current index, indicating it's already processed.

        # If the VTT file does not exist, create it and write the required header.
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write("WEBVTT\n\n")
        
        # Open the file in append mode to add the new subtitle entry.
        with open(path, "a", encoding="utf-8") as f:
            # Format the start and end times.
            start = format_timestamp(sentence_obj["start"])
            end = format_timestamp(sentence_obj["end"])
            # Sanitize the text by removing newlines and stripping whitespace.
            text = re.sub(r'[\r\n]+', ' ', sentence_obj["text"]).strip()
            # Write the formatted timestamp and text to the file.
            f.write(f"{start} --> {end}\n{text}\n\n")
        
        # Return the index for the *next* entry.
        return index + 1
    except Exception as e:
        # Log any errors that occur during the file operation.
        error = f'append_sentence2vtt() error: {e}'
        print(error)
        return False
