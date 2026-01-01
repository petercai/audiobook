import os
import re
import shutil
import zipfile
from pathlib import Path

from tqdm import tqdm

from lib.conf import models_dir
from lib.models import default_fine_tuned
from lib.models import models
from lib.util import util


class CustomizedModel:
    def process_custom_model(self, session):
        error = None
        session["custom_model_dir"] = os.path.join(
            models_dir, "__sessions", f"model-{session['id']}"
        )
        if session["custom_model"] is not None:
            if not os.path.exists(session["custom_model_dir"]):
                os.makedirs(session["custom_model_dir"], exist_ok=True)
            src_path = Path(session["custom_model"])
            src_name = src_path.stem
            if not os.path.exists(
                os.path.join(session["custom_model_dir"], src_name)
            ):
                required_files = models[session["tts_engine"]]["internal"][
                    "files"
                ]
                if self.analyze_uploaded_file(
                    session["custom_model"], required_files
                ):
                    model = self.extract_custom_model(
                        session["custom_model"], session
                    )
                    if model is not None:
                        session["custom_model"] = model
                    else:
                        error = f"{model} could not be extracted or mandatory files are missing"
                else:
                    error = f'{os.path.basename(session["custom_model"])} is not a valid model or some required files are missing'
        return error

    @staticmethod
    def analyze_uploaded_file(zip_path, required_files):
        try:
            if not os.path.exists(zip_path):
                error = f"The file does not exist: {os.path.basename(zip_path)}"
                print(error)
                return False
            required_lc = set(file.lower() for file in required_files)
            missing_files = set(required_lc)
            empty_files = set()
            with zipfile.ZipFile(zip_path, "r") as zf:
                for file_info in zf.infolist():
                    if file_info.is_dir():
                        continue
                    base_name = os.path.basename(file_info.filename).lower()
                    if base_name in required_lc:
                        missing_files.discard(base_name)
                        if file_info.file_size == 0:
                            empty_files.add(base_name)
                        if not missing_files and not empty_files:
                            break
            if missing_files:
                print(f"Missing required files: {sorted(missing_files)}")
            if empty_files:
                print(f"Required files with 0 KB: {sorted(empty_files)}")
            return not missing_files and not empty_files
        except zipfile.BadZipFile:
            error = "The file is not a valid ZIP archive."
            raise ValueError(error)
        except Exception as e:
            error = f"An error occurred: {e}"
            raise RuntimeError(error)

    def extract_custom_model(self, file_src, session, required_files=None):
        """
        Extracts a custom TTS model from a ZIP archive and places it in the session's model directory.

        This method handles the extraction of a user-provided ZIP file containing a fine-tuned model.
        It validates the contents of the ZIP, creates a dedicated directory for the model,
        and extracts only the required files. This ensures that custom models are organized
        and ready for use by the TTS engine.

        Args:
            file_src (str): The file path of the ZIP archive containing the custom model.
            session (dict): The session object, which contains configuration details like
                            'tts_engine' and 'custom_model_dir'.
            required_files (list, optional): A list of filenames that must be present in the
                                             ZIP file for it to be considered a valid model.
                                             If None, it defaults to the requirements of the
                                             current TTS engine. Defaults to None.

        Returns:
            str or None: The path to the extracted model directory if successful, otherwise None.
        """
        try:
            is_gui_process = session.get("is_gui_process", False)

            model_path = None
            if required_files is None:
                required_files = models[session["tts_engine"]][
                    default_fine_tuned
                ]["files"]

            model_name = re.sub(
                ".zip", "", os.path.basename(file_src), flags=re.IGNORECASE
            )
            model_name = self._get_sanitized(model_name)

            with zipfile.ZipFile(file_src, "r") as zip_ref:
                files = zip_ref.namelist()
                files_length = len(files)
                tts_dir = session["tts_engine"]
                model_path = os.path.join(
                    session["custom_model_dir"], tts_dir, model_name
                )

                if os.path.exists(model_path):
                    print(
                        f"{model_path} already exists, bypassing files extraction"
                    )
                    return model_path

                os.makedirs(model_path, exist_ok=True)
                required_files_lc = set(x.lower() for x in required_files)

                with tqdm(total=files_length, unit="files") as t:
                    for f in files:
                        base_f = os.path.basename(f).lower()
                        if base_f in required_files_lc:
                            out_path = os.path.join(model_path, base_f)
                            with zip_ref.open(f) as src, open(
                                out_path, "wb"
                            ) as dst:
                                shutil.copyfileobj(src, dst)
                        t.update(1)

            if is_gui_process:
                os.remove(file_src)

            print(f"Extracted files to {model_path}")
            return model_path
        except Exception as e:
            util.print_error(e)
            if is_gui_process and file_src and os.path.exists(file_src):
                os.remove(file_src)
            return None

    @staticmethod
    def _get_sanitized(value, replacement="_"):
        value = value.replace("&", "And")
        forbidden_chars = r'[<>:"/\\|?*\x00-\x1F ()]'
        sanitized = re.sub(r"\s+", replacement, value)
        sanitized = re.sub(forbidden_chars, replacement, sanitized)
        sanitized = sanitized.strip("_")
        return sanitized
