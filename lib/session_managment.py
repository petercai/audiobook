import fnmatch
import hashlib
import os
import shutil
import uuid

from lib.conf import NATIVE
from lib.conf import default_output_split_minutes
from lib.conf import models_dir
from lib.conf import tmp_dir
from lib.functions import get_compatible_tts_engines
from lib.functions import DependencyError
from lib.models import models
from lib.models import TTS_ENGINES


class SessionManagement:
    def __init__(self, is_gui_process=False):
        self.is_gui_process = is_gui_process

    def set_is_gui_process(self, is_gui_process):
        self.is_gui_process = is_gui_process

    @staticmethod
    def calculate_hash(filepath, hash_algorithm="sha256"):
        hash_func = hashlib.new(hash_algorithm)
        with open(filepath, "rb") as f:
            while chunk := f.read(8192):
                hash_func.update(chunk)
        return hash_func.hexdigest()

    def compare_files_by_hash(self, file1, file2, hash_algorithm="sha256"):
        return self.calculate_hash(file1, hash_algorithm) == self.calculate_hash(
            file2, hash_algorithm
        )

    def prepare_session_cache(self, args, session):
        """
        Prepares the session cache by renaming the old session directory to the new process directory and creating
        the necessary subdirectories for processing the ebook.

        The following session fields are updated:

        - session_dir: The root directory for the session.
        - process_dir: The directory for the current process.
        - chapters_dir: The directory for the chapters.
        - chapters_dir_sentences: The directory for the sentences of the chapters.
        - epub_path: The path to the epub file.

        Args:
            args (dict): A dictionary containing the configuration settings for the TTS engine.
            session (dict): A dictionary containing the session configuration settings.

        Returns:
            The updated session dictionary with the cache prepared.
        """
        old_session_dir = os.path.join(tmp_dir, f"ebook-{session['id']}")
        session["session_dir"] = os.path.join(tmp_dir, f"proc-{session['id']}")
        if os.path.isdir(old_session_dir):
            os.rename(old_session_dir, session["session_dir"])
        session["process_dir"] = os.path.join( session["session_dir"], f"{hashlib.md5(session['ebook'].encode()).hexdigest()}", )
        session["chapters_dir"] = os.path.join(session["process_dir"], "chapters")
        session["chapters_dir_sentences"] = os.path.join( session["chapters_dir"], "sentences" )
        session["filename_noext"] = os.path.splitext( os.path.basename(session["ebook"]) )[0]
        session["epub_path"] = os.path.join( session["process_dir"], "__" + session["filename_noext"] + ".epub" )
        return self.prepare_dirs(args["ebook"], session)

    
    def prepare_dirs(self, src, session):
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
            os.makedirs(os.path.join(models_dir, "tts"), exist_ok=True)
            os.makedirs(session["session_dir"], exist_ok=True)
            os.makedirs(session["process_dir"], exist_ok=True)
            # os.makedirs(session['custom_model_dir'], exist_ok=True)
            # os.makedirs(session['voice_dir'], exist_ok=True)
            os.makedirs(session["audiobooks_dir"], exist_ok=True)
            session["ebook"] = os.path.join(session["process_dir"], os.path.basename(src))
            if os.path.exists(session["ebook"]):
                if self.compare_files_by_hash(session["ebook"], src):
                    resume = True
            if not resume:
                shutil.rmtree(session["chapters_dir"], ignore_errors=True)
            os.makedirs(session["chapters_dir"], exist_ok=True)
            os.makedirs(session["chapters_dir_sentences"], exist_ok=True)
            shutil.copy(src, session["ebook"])
            return True
        except Exception as e:
            DependencyError(e)
            return False

    def init_session(self, args, ctx):
        """
        Initializes the session dictionary with the provided configuration settings.

        Updates the following session fields:

        - session: The unique identifier for the session.
        - script_mode: The script mode, either NATIVE or WEB.
        - ebook: The path to the ebook file or None if not provided.
        - ebook_list: The list of ebook files or None if not provided.
        - device: The device to use for computation, either 'cpu' or 'cuda'.
        - language: The language code for synthesis.
        - language_iso1: The ISO-1 language code for synthesis.
        - tts_engine: The TTS engine to use, either 'XTTSv2', 'Bark', 'VITS', or 'FAIRSEQ'.
        - custom_model: The custom model to use, either None or the path to the custom model.
        - fine_tuned: The fine-tuned model to use, either None or the path to the fine-tuned model.
        - voice: The voice to use, either None or the path to the voice file.
        - temperature: The temperature for sampling, either None or a float.
        - length_penalty: The length penalty for sampling, either None or a float.
        - num_beams: The number of beams for beam search, either None or an integer.
        - repetition_penalty: The repetition penalty for sampling, either None or a float.
        - top_k: The top-k sampling parameter, either None or an integer.
        - top_p: The top-p sampling parameter, either None or a float.
        - speed: The speaking speed, either None or a float.
        - enable_text_splitting: A boolean indicating whether to enable text splitting.
        - text_temp: The text temperature for Bark, either None or a float.
        - waveform_temp: The waveform temperature for Bark, either None or a float.
        - audiobooks_dir: The directory for the audiobooks, either None or a path.
        - output_format: The output format, either None or a string.
        - output_split: A boolean indicating whether to split the output into multiple files.
        - output_split_minutes: The number of minutes to split the output into, either None or an integer.

        Returns:
            A dictionary containing the updated session fields and the session ID.
        """
        session_id = (
            args["session"] if args["session"] is not None else str(uuid.uuid4())
        )

        session = ctx.get_session(session_id)
        session["script_mode"] = (
            args["script_mode"] if args["script_mode"] is not None else NATIVE
        )
        session["ebook"] = args["ebook"]
        session["ebook_list"] = args["ebook_list"]
        session["device"] = args["device"]
        session["language"] = args["language"]
        session["language_iso1"] = args["language_iso1"]
        session["tts_engine"] = (
            args["tts_engine"]
            if args["tts_engine"] is not None
            else get_compatible_tts_engines(args["language"])[0]
        )
        session["custom_model"] = (
            args["custom_model"]
            if not self.is_gui_process or args["custom_model"] is None
            else os.path.join(session["custom_model_dir"], args["custom_model"])
        )
        session["fine_tuned"] = args["fine_tuned"]
        if session["fine_tuned"] not in models.get(session["tts_engine"], {}):
            available = list(models.get(session["tts_engine"], {}).keys())
            session["fine_tuned"] = (
                available[0] if available else session["fine_tuned"]
            )
        session["voice"] = args["voice"]
        if (
            session["tts_engine"] == TTS_ENGINES["COSYVOICE"]
            and session["fine_tuned"] == "CosyVoice-300M-SFT"
            and session["voice"] is None
        ):
            session["voice"] = models[session["tts_engine"]][session["fine_tuned"]][
                "voice"
            ]
        session["temperature"] = args["temperature"]
        session["length_penalty"] = args["length_penalty"]
        session["num_beams"] = args["num_beams"]
        session["repetition_penalty"] = args["repetition_penalty"]
        session["top_k"] = args["top_k"]
        session["top_p"] = args["top_p"]
        session["speed"] = args["speed"]
        session["enable_text_splitting"] = args["enable_text_splitting"]
        session["text_temp"] = args["text_temp"]
        session["waveform_temp"] = args["waveform_temp"]
        session["audiobooks_dir"] = args["audiobooks_dir"]
        session["output_format"] = args["output_format"]
        session["output_split"] = args["output_split"]
        session["output_split_minutes"] = (
            args["output_split_minutes"]
            if args["output_split_minutes"] is not None
            else default_output_split_minutes
        )
        session["offline_mode"] = args.get("offline_mode", False)
        session["add_toc_title"] = args.get("add_toc_title", False)
        return dict(session), session_id

    def restore_session_from_data(self, data, session):
        try:
            for key, value in data.items():
                if key in session:  # Check if the key exists in session
                    if isinstance(value, dict) and isinstance(session[key], dict):
                        self.restore_session_from_data(value, session[key])
                    else:
                        session[key] = value
        except Exception as e:
            DependencyError(e)

    def reset_ebook_session(self, context, id):
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
                "creator": "Unknown",
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
        self.restore_session_from_data(data, session)

    def session_cache_cleanup(self, session):
        chapters_dirs = [
            dir_name
            for dir_name in os.listdir(session["process_dir"])
            if fnmatch.fnmatch(dir_name, "chapters_*")
            and os.path.isdir(os.path.join(session["process_dir"], dir_name))
        ]
        shutil.rmtree(os.path.join(session["voice_dir"], "proc"), ignore_errors=True)
        if self.is_gui_process:
            if len(chapters_dirs) > 1:
                if os.path.exists(session["chapters_dir"]):
                    shutil.rmtree(session["chapters_dir"], ignore_errors=True)
                if os.path.exists(session["epub_path"]):
                    os.remove(session["epub_path"])
                if os.path.exists(session["cover"]):
                    os.remove(session["cover"])
            else:
                if os.path.exists(session["process_dir"]):
                    shutil.rmtree(session["process_dir"], ignore_errors=True)
        else:
            if os.path.exists(session["voice_dir"]):
                if not any(os.scandir(session["voice_dir"])):
                    shutil.rmtree(session["voice_dir"], ignore_errors=True)
            if os.path.exists(session["custom_model_dir"]):
                if not any(os.scandir(session["custom_model_dir"])):
                    shutil.rmtree(session["custom_model_dir"], ignore_errors=True)
            if os.path.exists(session["session_dir"]):
                shutil.rmtree(session["session_dir"], ignore_errors=True)
