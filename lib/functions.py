import hashlib
import os
import platform
import shutil
import subprocess
import time
import traceback
from collections.abc import Mapping
from multiprocessing import Manager
from multiprocessing.managers import DictProxy
import zipfile

import gradio as gr
import psutil
from bs4 import BeautifulSoup

from lib.conf import NATIVE, default_device, tmp_dir, voices_dir
from lib.conf import models_dir
from lib.conf import  default_output_format, default_output_split, default_output_split_minutes
from lib.lang import default_language_code, language_tts
from lib.models import default_tts_engine, default_fine_tuned, default_engine_settings, TTS_ENGINES, models


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
        # Exit the script if it's not a web process
        # if not is_gui_process:
        #     sys.exit(1)



class SessionContext:
    def __init__(self):
        self.manager = Manager()
        self.sessions = self.manager.dict()
        self.cancellation_events = {}

    def get_session(self, id):
        if id not in self.sessions:
            self.sessions[id] = recursive_proxy({
                "script_mode": NATIVE,
                "id": id,
                "tab_id": None,
                "process_id": None,
                "status": None,
                "event": None,
                "progress": 0,
                "offline_mode": False,
                "cancellation_requested": False,
                "device": default_device,
                "system": None,
                "client": None,
                "language": default_language_code,
                "language_iso1": None,
                "audiobook": None,
                "audiobooks_dir": None,
                "process_dir": None,
                "ebook": None,
                "ebook_list": None,
                "ebook_mode": "single",
                "chapters_dir": None,
                "chapters_dir_sentences": None,
                "epub_path": None,
                "filename_noext": None,
                "tts_engine": default_tts_engine,
                "fine_tuned": default_fine_tuned,
                "voice": None,
                "voice_dir": None,
                "custom_model": None,
                "custom_model_dir": None,
                "temperature": default_engine_settings[TTS_ENGINES['XTTSv2']]['temperature'],
                "length_penalty": default_engine_settings[TTS_ENGINES['XTTSv2']]['length_penalty'],
                "num_beams": default_engine_settings[TTS_ENGINES['XTTSv2']]['num_beams'],
                "repetition_penalty": default_engine_settings[TTS_ENGINES['XTTSv2']]['repetition_penalty'],
                "top_k": default_engine_settings[TTS_ENGINES['XTTSv2']]['top_k'],
                "top_p": default_engine_settings[TTS_ENGINES['XTTSv2']]['top_p'],
                "speed": default_engine_settings[TTS_ENGINES['XTTSv2']]['speed'],
                "enable_text_splitting": default_engine_settings[TTS_ENGINES['XTTSv2']]['enable_text_splitting'],
                "text_temp": default_engine_settings[TTS_ENGINES['BARK']]['text_temp'],
                "waveform_temp": default_engine_settings[TTS_ENGINES['BARK']]['waveform_temp'],
                "cfg_value": default_engine_settings[TTS_ENGINES['VOXCPM']]['cfg_value'],
                "inference_timesteps": default_engine_settings[TTS_ENGINES['VOXCPM']]['inference_timesteps'],
                "normalize": default_engine_settings[TTS_ENGINES['VOXCPM']]['normalize'],
                "denoise": default_engine_settings[TTS_ENGINES['VOXCPM']]['denoise'],
                "retry_badcase": default_engine_settings[TTS_ENGINES['VOXCPM']]['retry_badcase'],
                "retry_badcase_max_times": default_engine_settings[TTS_ENGINES['VOXCPM']]['retry_badcase_max_times'],
                "retry_badcase_ratio_threshold": default_engine_settings[TTS_ENGINES['VOXCPM']]['retry_badcase_ratio_threshold'],
                "prompt_text": "Default prompt text",
                "final_name": None,
                "output_format": default_output_format,
                "output_split": default_output_split,
                "output_split_minutes": default_output_split_minutes,
                "metadata": {
                    "title": None, 
                    "creator": None,
                    "contributor": None,
                    "language": None,
                    "identifier": None,
                    "publisher": None,
                    "date": None,
                    "description": None,
                    "subject": None,
                    "rights": None,
                    "format": None,
                    "type": None,
                    "coverage": None,
                    "relation": None,
                    "Source": None,
                    "Modified": None,
                },
                "toc": None,
                "chapters": None,
                "cover": None,
                "duration": 0,
                "playback_time": 0
            }, manager=self.manager)
        return self.sessions[id]

    def find_id_by_hash(self, socket_hash):
        for id, session in self.sessions.items():
            if socket_hash in session:
                return session.get('id')
        return None

def show_alert(state):
    if isinstance(state, dict):
        if state['type'] is not None:
            if state['type'] == 'error':
                gr.Error(state['msg'])
            elif state['type'] == 'warning':
                gr.Warning(state['msg'])
            elif state['type'] == 'info':
                gr.Info(state['msg'])
            elif state['type'] == 'success':
                gr.Success(state['msg'])
def recursive_proxy(data, manager=None):
    """
    Recursively convert plain Python data structures into multiprocessing.Manager
    proxy objects so they can be shared across processes.

    - dict -> manager.dict() with values recursively proxied
    - list -> manager.list() with items recursively proxied
    - primitives (str, int, float, bool, None) -> returned unchanged
    - unsupported types -> prints an error and returns None
    """
    # Create a Manager if one wasn't provided (needed to create proxy containers)
    if manager is None:
        manager = Manager()

    # Convert dictionaries to a proxy dict and recursively proxy values
    if isinstance(data, dict):
        proxy_dict = manager.dict()
        for key, value in data.items():
            # Recursively convert nested structures; simple types are returned as-is
            proxy_dict[key] = recursive_proxy(value, manager)
        return proxy_dict

    # Convert lists to a proxy list and recursively proxy items
    elif isinstance(data, list):
        proxy_list = manager.list()
        for item in data:
            proxy_list.append(recursive_proxy(item, manager))
        return proxy_list

    # Return primitive scalar values unchanged (safe to share)
    elif isinstance(data, (str, int, float, bool, type(None))):
        return data

    # Any other type is not supported for automatic proxying here
    else:
        error = f"Unsupported data type: {type(data)}"
        print(error)
        return None

def prepare_dirs(src, session):
    """
    Prepare directories for an ebook conversion session.

    This function creates all necessary directories for a conversion session, including the
    session directory, process directory, custom model directory, voice directory, audiobooks
    directory, chapters directory, and chapters sentences directory. It also checks if the
    ebook file already exists in the process directory and if so, it sets the resume flag to
    True. If the ebook file does not exist, it removes the chapters directory and recreates
    it. Finally, it copies the ebook file to the process directory.

    :param src: The path to the ebook file.
    :param session: The session dictionary containing all necessary fields for the conversion session.
    :return: True if the directories were prepared successfully, False otherwise.
    """
    try:
        resume = False
        os.makedirs(os.path.join(models_dir,'tts'), exist_ok=True)
        os.makedirs(session['session_dir'], exist_ok=True)
        os.makedirs(session['process_dir'], exist_ok=True)
        os.makedirs(session['custom_model_dir'], exist_ok=True)
        os.makedirs(session['voice_dir'], exist_ok=True)
        os.makedirs(session['audiobooks_dir'], exist_ok=True)
        session['ebook'] = os.path.join(session['process_dir'], os.path.basename(src))
        if os.path.exists(session['ebook']):
            if compare_files_by_hash(session['ebook'], src):
                resume = True
        if not resume:
            shutil.rmtree(session['chapters_dir'], ignore_errors=True)
        os.makedirs(session['chapters_dir'], exist_ok=True)
        os.makedirs(session['chapters_dir_sentences'], exist_ok=True)
        shutil.copy(src, session['ebook']) 
        return True
    except Exception as e:
        DependencyError(e)
        return False

def check_programs(prog_name, command, options):
    try:
        subprocess.run(
            [command, options],
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            check=True,
            text=True,
            encoding='utf-8'
        )
        return True, None
    except FileNotFoundError:
        e = f'''********** Error: {prog_name} is not installed! if your OS calibre package version 
        is not compatible you still can run ebook2audiobook.sh (linux/mac) or ebook2audiobook.cmd (windows) **********'''
        DependencyError(e)
        return False, None
    except subprocess.CalledProcessError:
        e = f'Error: There was an issue running {prog_name}.'
        DependencyError(e)
        return False, None

def analyze_uploaded_file(zip_path, required_files):
    try:
        if not os.path.exists(zip_path):
            error = f"The file does not exist: {os.path.basename(zip_path)}"
            print(error)
            return False
        files_in_zip = {}
        empty_files = set()
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for file_info in zf.infolist():
                file_name = file_info.filename
                if file_info.is_dir():
                    continue
                base_name = os.path.basename(file_name)
                files_in_zip[base_name.lower()] = file_info.file_size
                if file_info.file_size == 0:
                    empty_files.add(base_name.lower())
        required_files = [file.lower() for file in required_files]
        missing_files = [f for f in required_files if f not in files_in_zip]
        required_empty_files = [f for f in required_files if f in empty_files]
        if missing_files:
            print(f"Missing required files: {missing_files}")
        if required_empty_files:
            print(f"Required files with 0 KB: {required_empty_files}")
        return not missing_files and not required_empty_files
    except zipfile.BadZipFile:
        error = "The file is not a valid ZIP archive."
        raise ValueError(error)
    except Exception as e:
        error = f"An error occurred: {e}"
        raise RuntimeError(error)

def hash_proxy_dict(proxy_dict):
    return hashlib.md5(str(proxy_dict).encode('utf-8')).hexdigest()

def calculate_hash(filepath, hash_algorithm='sha256'):
    hash_func = hashlib.new(hash_algorithm)
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):  # Read in chunks to handle large files
            hash_func.update(chunk)
    return hash_func.hexdigest()

def compare_files_by_hash(file1, file2, hash_algorithm='sha256'):
    return calculate_hash(file1, hash_algorithm) == calculate_hash(file2, hash_algorithm)

def compare_dict_keys(d1, d2):
    if not isinstance(d1, Mapping) or not isinstance(d2, Mapping):
        return d1 == d2
    d1_keys = set(d1.keys())
    d2_keys = set(d2.keys())
    missing_in_d2 = d1_keys - d2_keys
    missing_in_d1 = d2_keys - d1_keys
    if missing_in_d2 or missing_in_d1:
        return {
            "missing_in_d2": missing_in_d2,
            "missing_in_d1": missing_in_d1,
        }
    for key in d1_keys.intersection(d2_keys):
        nested_result = compare_dict_keys(d1[key], d2[key])
        if nested_result:
            return {key: nested_result}
    return None

def proxy2dict(proxy_obj):
    def recursive_copy(source, visited):
        # Handle circular references by tracking visited objects
        if id(source) in visited:
            return None  # Stop processing circular references
        visited.add(id(source))  # Mark as visited
        if isinstance(source, dict):
            result = {}
            for key, value in source.items():
                result[key] = recursive_copy(value, visited)
            return result
        elif isinstance(source, list):
            return [recursive_copy(item, visited) for item in source]
        elif isinstance(source, set):
            return list(source)
        elif isinstance(source, (int, float, str, bool, type(None))):
            return source
        elif isinstance(source, DictProxy):
            # Explicitly handle DictProxy objects
            return recursive_copy(dict(source), visited)  # Convert DictProxy to dict
        else:
            return str(source)  # Convert non-serializable types to strings
    return recursive_copy(proxy_obj, set())

def get_ebook_title(epubBook, all_docs):
    # 1. Try metadata (official EPUB title)
    meta_title = epubBook.get_metadata("DC", "title")
    if meta_title and meta_title[0][0].strip():
        return meta_title[0][0].strip()
    # 2. Try <title> in the head of the first XHTML document
    if all_docs:
        html = all_docs[0].get_content().decode("utf-8")
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.select_one("head > title")
        if title_tag and title_tag.text.strip():
            return title_tag.text.strip()
        # 3. Try <img alt="..."> if no visible <title>
        img = soup.find("img", alt=True)
        if img:
            alt = img['alt'].strip()
            if alt and "cover" not in alt.lower():
                return alt
    return None

def get_ram():
    vm = psutil.virtual_memory()
    return vm.total // (1024 ** 3)

def get_vram():
    os_name = platform.system()
    # NVIDIA (Cross-Platform: Windows, Linux, macOS)
    try:
        from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetMemoryInfo
        nvmlInit()
        handle = nvmlDeviceGetHandleByIndex(0)  # First GPU
        info = nvmlDeviceGetMemoryInfo(handle)
        vram = info.total
        return int(vram // (1024 ** 3))  # Convert to GB
    except ImportError:
        pass
    except Exception as e:
        pass
    # AMD (Windows)
    if os_name == "Windows":
        try:
            cmd = 'wmic path Win32_VideoController get AdapterRAM'
            output = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            lines = output.stdout.splitlines()
            vram_values = [int(line.strip()) for line in lines if line.strip().isdigit()]
            if vram_values:
                return int(vram_values[0] // (1024 ** 3))
        except Exception as e:
            pass
    # AMD (Linux)
    if os_name == "Linux":
        try:
            cmd = "lspci -v | grep -i 'VGA' -A 12 | grep -i 'preallocated' | awk '{print $2}'"
            output = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            if output.stdout.strip().isdigit():
                return int(output.stdout.strip()) // 1024
        except Exception as e:
            pass
    # Intel (Linux Only)
    intel_vram_paths = [
        "/sys/kernel/debug/dri/0/i915_vram_total",  # Intel dedicated GPUs
        "/sys/class/drm/card0/device/resource0"  # Some integrated GPUs
    ]
    for path in intel_vram_paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    vram = int(f.read().strip()) // (1024 ** 3)
                    return vram
            except Exception as e:
                pass
    # macOS (OpenGL Alternative)
    if os_name == "Darwin":
        try:
            from OpenGL.GL import glGetIntegerv
            from OpenGL.GLX import GLX_RENDERER_VIDEO_MEMORY_MB_MESA
            vram = int(glGetIntegerv(GLX_RENDERER_VIDEO_MEMORY_MB_MESA) // 1024)
            return vram
        except ImportError:
            pass
        except Exception as e:
            pass
    msg = 'Could not detect GPU VRAM Capacity!'
    return 0

def _get_text_normalizer():
    from lib.text_normalizer import TextNormalizer
    if not hasattr(_get_text_normalizer, "_instance"):
        _get_text_normalizer._instance = TextNormalizer()
    return _get_text_normalizer._instance

def get_num2words_compat(lang_iso1):
    return _get_text_normalizer().get_num2words_compat(lang_iso1)

def set_formatted_number(text: str, lang_iso1: str, is_num2words_compat: bool, max_single_value: int = 999_999_999_999_999_999):
    return _get_text_normalizer()._set_formatted_number(text, lang_iso1, is_num2words_compat, max_single_value)

def year2words(year_str, lang_iso1, is_num2words_compat):
    return _get_text_normalizer()._year2words(year_str, lang_iso1, is_num2words_compat)

def clock2words(text, lang_iso1, tts_engine, is_num2words_compat):
    return _get_text_normalizer()._clock2words(text, lang_iso1, tts_engine, is_num2words_compat)

def math2words(text, lang_iso1, tts_engine, is_num2words_compat):
    return _get_text_normalizer()._math2words(text, lang_iso1, tts_engine, is_num2words_compat)

def roman2number(text):
    return _get_text_normalizer()._roman2number(text)

def filter_sml(text):
    return _get_text_normalizer()._filter_sml(text)

def normalize_text(text, lang_iso1, tts_engine):
    return _get_text_normalizer().normalize_text(text, lang_iso1)

def delete_unused_tmp_dirs(web_dir, days, session):
    dir_array = [
        tmp_dir,
        web_dir,
        os.path.join(models_dir, '__sessions'),
        os.path.join(voices_dir, '__sessions')
    ]
    current_user_dirs = {
        f"proc-{session['id']}",
        f"web-{session['id']}",
        f"voice-{session['id']}",
        f"model-{session['id']}"
    }
    current_time = time.time()
    threshold_time = current_time - (days * 24 * 60 * 60)  # Convert days to seconds
    for dir_path in dir_array:
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            for dir in os.listdir(dir_path):
                if dir in current_user_dirs:        
                    full_dir_path = os.path.join(dir_path, dir)
                    if os.path.isdir(full_dir_path):
                        try:
                            dir_mtime = os.path.getmtime(full_dir_path)
                            dir_ctime = os.path.getctime(full_dir_path)
                            if dir_mtime < threshold_time and dir_ctime < threshold_time:
                                shutil.rmtree(full_dir_path, ignore_errors=True)
                                msg = f"Deleted expired session: {full_dir_path}"
                                print(msg)
                        except Exception as e:
                            error = f"Error deleting {full_dir_path}: {e}"
                            print(error)

def compare_file_metadata(f1, f2):
    if os.path.getsize(f1) != os.path.getsize(f2):
        return False
    if os.path.getmtime(f1) != os.path.getmtime(f2):
        return False
    return True
    
def get_compatible_tts_engines(language):
    compatible_engines = [
        tts for tts in models.keys()
        if language in language_tts.get(tts, {})
    ]
    return compatible_engines

def restore_session_from_data(data, session):
    try:
        for key, value in data.items():
            if key in session:  # Check if the key exists in session
                if isinstance(value, dict) and isinstance(session[key], dict):
                    restore_session_from_data(value, session[key])
                else:
                    session[key] = value
    except Exception as e:
        DependencyError(e)

def reset_ebook_session(context, id):
    session = context.get_session(id)
    data = {
        "ebook": None,
        "chapters_dir": None,
        "chapters_dir_sentences": None,
        "epub_path": None,
        "filename_noext": None,
        "chapters": None,
        "cover": None,
        "status": None,
        "progress": 0,
        "duration": 0,
        "playback_time": 0,
        "cancellation_requested": False,
        "event": None,
        "metadata": {
            "title": None, 
            "creator": None,
            "contributor": None,
            "language": None,
            "identifier": None,
            "publisher": None,
            "date": None,
            "description": None,
            "subject": None,
            "rights": None,
            "format": None,
            "type": None,
            "coverage": None,
            "relation": None,
            "Source": None,
            "Modified": None
        }
    }
    restore_session_from_data(data, session)
