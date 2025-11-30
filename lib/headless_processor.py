import fnmatch
import hashlib
import os
import shutil
import sys
import traceback
import uuid
from glob import glob
from pathlib import Path

import torch
from ebooklib import epub
from iso639 import languages

from lib.ebook_audio import EbookAudio
from .classes.voice_extractor import VoiceExtractor
from .functions import (
    NATIVE,
    TTS_ENGINES,
    analyze_uploaded_file,
    check_programs,
    default_engine_settings,
    default_gpu_wiki,
    default_output_split_minutes,
    get_compatible_tts_engines,
    get_vram,
    language_mapping,
    models,
    models_dir,
    prepare_dirs,
    reset_ebook_session,
    show_alert,
    ebook_formats,
    tmp_dir,
    voices_dir,
)
from lib.epub import EPubProcessor


class EBookProcessor:
    def __init__(self):
        self.ebook_audio = EbookAudio()

    def convert_ebook_batch(self, args, ctx):
        if isinstance(args["ebook_list"], list):
            ebook_list = args["ebook_list"][:]
            for file in ebook_list:  # Use a shallow copy
                if any(file.endswith(ext) for ext in ebook_formats):
                    args["ebook"] = file
                    print(f"Processing eBook file: {os.path.basename(file)}")
                    progress_status, passed = self.convert_ebook(args, ctx)
                    if passed is False:
                        print(f"Conversion failed: {progress_status}")
                        sys.exit(1)
                    args["ebook_list"].remove(file)
            reset_ebook_session(ctx, args["session"])
            return progress_status, passed
        else:
            print(f"the ebooks source is not a list!")
            sys.exit(1)

    def validate_language(self, args):
        try:
            if not os.path.splitext(args["ebook"])[1]:
                error = f"{args['ebook']} needs a format extension."
                print(error)
                return error, False
            if not os.path.exists(args["ebook"]):
                error = "File does not exist or Directory empty."
                print(error)
                return error, False
            try:
                if len(args["language"]) == 2:
                    lang_array = languages.get(part1=args["language"])
                    if lang_array:
                        args["language"] = lang_array.part3
                        args["language_iso1"] = lang_array.part1
                elif len(args["language"]) == 3:
                    lang_array = languages.get(part3=args["language"])
                    if lang_array:
                        args["language"] = lang_array.part3
                        args["language_iso1"] = lang_array.part1
                else:
                    args["language_iso1"] = None
            except Exception:
                pass

            if args["language"] not in language_mapping.keys():
                error = "The language you provided is not (yet) supported"
                print(error)
                return error, False

            return None, True
        except Exception as e:
            print(f"validate_language() Exception: {e}")
            return str(e), False

    def convert_ebook(self, args, context):
        """
        Orchestrates the conversion of a single ebook file to an audiobook.

        This method serves as the main entry point for the conversion process. It handles
        session initialization, language validation, dependency checks, and the step-by-step
        workflow from the source ebook file to the final audio output.

        Args:
            args (dict): A dictionary of arguments, typically from the command line or UI,
                         containing all necessary parameters for the conversion (e.g.,
                         ebook path, language, TTS engine).
            context (SessionContext): The session context manager.

        Returns:
            tuple: A tuple containing:
                - str: A status message indicating success, cancellation, or failure.
                - bool: True if the conversion was successful, False otherwise.
        """
        try:
            error = None
            id = None
            # 1. Validate that a language is provided.
            if args["language"] is not None:
                # Validate the language and ebook file path.
                err, ok = self.validate_language(args)
                if ok is False:
                    return err, False

                # 2. Initialize the session for this conversion.
                # This sets up a shared state for all processing steps.
                session, id = self.init_session(args, context)

                # 3. Process custom models and voices if running in headless mode.
                if not args.get("is_gui_process", False):
                    error = self._process_custom_model(session)
                    if error is None:
                        error = self._process_voice(session)

                # 4. Proceed if no errors have occurred yet.
                if error is None:
                    # 5. Check for required external dependencies (Calibre, FFmpeg) in native mode.
                    if session["script_mode"] == NATIVE:
                        bool, e = check_programs("Calibre", "ebook-convert", "--version")
                        if not bool:
                            error = f"check_programs() Calibre failed: {e}"
                        if error is None:
                            bool, e = check_programs("FFmpeg", "ffmpeg", "-version")
                            if not bool:
                                error = f"check_programs() FFMPEG failed: {e}"

                    # 6. Proceed if all dependencies are met.
                    if error is None:
                        # Prepare session-specific cache directories.
                        if self.prepare_session_cache(args, session):
                            # 7. Check GPU availability and configure the processing device.
                            self.gpu_check(self.is_gui_process, session)

                            # 8. Convert the source ebook to EPUB format, which is the standard for processing.
                            epub_processor = EPubProcessor()
                            if epub_processor.convert2epub(session):
                                # 9. Process the EPUB: extract text, generate TTS, and create the audiobook.
                                progress_status, passed = self.process_epub(session)
                                if passed:
                                    return progress_status, True
                                else:
                                    error = progress_status
                            else:
                                error = "convert2epub() failed!"
            else:
                error = f"Language {args['language']} is not supported."

            # 10. Final error and status handling.
            if session and session.get("cancellation_requested"):
                error = "Cancelled"

            if not self.is_gui_process and id is not None:
                error += f"\n*********** Session: {id} **************\nStore it in case of interruption, crash, reuse of custom model or custom voice,\nyou can resume the conversion with --session option"

            print(error)
            return error, False
        except Exception as e:
            print(f"convert_ebook() Exception: {e}")
            # print traceback
            traceback.print_exc()
            return e, False

    def gpu_check(self, is_gui_process, session):
        msg = ""
        msg_extra = ""
        vram_avail = get_vram()
        if vram_avail <= 4:
            msg_extra += (
                "VRAM capacity could not be detected. -"
                if vram_avail == 0
                else "VRAM under 4GB - "
            )
            if session["tts_engine"] == TTS_ENGINES["BARK"]:
                os.environ["SUNO_USE_SMALL_MODELS"] = "True"
                msg_extra += f"Switching BARK to SMALL models - "
        else:
            if session["tts_engine"] == TTS_ENGINES["BARK"]:
                os.environ["SUNO_USE_SMALL_MODELS"] = "False"
        if session["device"] == "cuda":
            session["device"] = (
                session["device"] if torch.cuda.is_available() else "cpu"
            )
            if session["device"] == "cpu":
                msg += f"GPU not recognized by torch! Read {default_gpu_wiki} - Switching to CPU - "
        elif session["device"] == "mps":
            session["device"] = (
                session["device"]
                if torch.backends.mps.is_available()
                else "cpu"
            )
            if session["device"] == "cpu":
                msg += f"MPS not recognized by torch! Read {default_gpu_wiki} - Switching to CPU - "
        if session["device"] == "cpu":
            if session["tts_engine"] == TTS_ENGINES["BARK"]:
                os.environ["SUNO_OFFLOAD_CPU"] = "True"
        if (
                default_engine_settings[TTS_ENGINES["XTTSv2"]][
                    "use_deepspeed"
                ]
                == True
        ):
            try:
                import deepspeed
            except:
                default_engine_settings[TTS_ENGINES["XTTSv2"]][
                    "use_deepspeed"
                ] = False
                msg_extra += "deepseed not installed or package is broken. set to False - "
            else:
                msg_extra += "deepspeed detected and ready!"
        if msg == "":
            msg = f"Using {session['device'].upper()} - "
        msg += msg_extra
        if is_gui_process:
            show_alert({"type": "warning", "msg": msg})
        print(msg)

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
        session["session_dir"] = os.path.join(
            tmp_dir, f"proc-{session['id']}"
        )
        if os.path.isdir(old_session_dir):
            os.rename(old_session_dir, session["session_dir"])
        session["process_dir"] = os.path.join(
            session["session_dir"],
            f"{hashlib.md5(session['ebook'].encode()).hexdigest()}",
        )
        session["chapters_dir"] = os.path.join(
            session["process_dir"], "chapters"
        )
        session["chapters_dir_sentences"] = os.path.join(
            session["chapters_dir"], "sentences"
        )
        session["filename_noext"] = os.path.splitext(
            os.path.basename(session["ebook"])
        )[0]
        
        session["epub_path"] = os.path.join(
            session["process_dir"],
            "__" + session["filename_noext"] + ".epub",
            )
        return prepare_dirs(args["ebook"], session)

    def init_session(self, args, ctx):
        # global is_gui_process, context
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
        if ctx is not None:
            context = ctx

        self.is_gui_process = args["is_gui_process"]
        id = args["session"] if args["session"] is not None else str(uuid.uuid4())

        session = context.get_session(id)
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
        session["voice"] = args["voice"]
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
        return dict(session), id

    def process_epub_chapters(self, epubBook, session):
        """
        Process the EPUB chapters and convert them to audio.
        
        This method orchestrates the conversion of an EPUB book's chapters into an audiobook.
        It handles metadata preparation, chapter-to-audio conversion, audio combination,
        and cleanup of temporary files.
        
        Args:
            epubBook (epub.EpubBook): The EPUB book object containing the content to be processed
            id (str): Unique session identifier for this conversion process
            context (Context): Context object containing session management functionality
            
        Returns:
            tuple: A tuple containing (progress_status, success_flag)
                - progress_status (str): Status message describing the result or error
                - success_flag (bool): True if conversion was successful, False otherwise
                
        Process:
            1. Retrieves the session data using the provided id
            2. Prepares EPUB metadata (title, author, cover, etc.)
            3. Converts each chapter to audio using convert_chapters2audio()
            4. Combines individual audio segments into final audiobook files
            5. Cleans up temporary files and directories
            6. Returns status message with information about created files
        """
        try:
            # Retrieve the session data associated with this conversion process
            # session = context.get_session(id)
            
            # Prepare and validate EPUB metadata (title, author, cover image, etc.)
            err, ok = self.prepare_epub_metadata(session, epubBook)
            if not ok:
                return err, False

            # Convert all chapters in the EPUB to audio files
            epub_processor = EPubProcessor()
            if not epub_processor.convert_chapters2audio(session):
                return "convert_chapters2audio() failed!", False
                
            # Notify user that conversion is complete and combining process is starting
            msg = "Conversion successful. Combining sentences and chapters..."
            show_alert({"type": "info", "msg": msg})
            
            # Combine individual chapter audio files into final audiobook file(s)
            exported_files = self.ebook_audio.combine_audio_chapters(session)
            if exported_files is None:
                return "combine_audio_chapters() error: exported_files not created!", False

            # Clean up temporary directories and files used during processing
            # self.session_cache_cleanup(session)
            
            # Generate success message with names of created audiobook files
            progress_status = f'Audiobook(s) {", ".join(os.path.basename(f) for f in exported_files)} created!'
            
            # Store the path to the last created audiobook file in the session
            session["audiobook"] = exported_files[-1]
            
            # Display session information for potential reuse/resume
            print(f"\n*********** Session: {id} **************\nStore it in case of interruption, crash, reuse of custom model or custom voice,\nyou can resume the conversion with --session option")
            
            return progress_status, True
        except Exception as e:
            # Handle any unexpected errors during the process
            print(f"processEPubChapters() Exception: {e}")
            return str(e), False

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


    def prepare_epub_metadata(self, session, epubBook):
        """
        Prepares the metadata for the EPUB file.
        
        This method extracts and processes metadata from the EPUB book and stores it in the session.
        It also extracts the cover image, table of contents, and chapters from the EPUB book.
        
        The following items are stored in the session:
        - metadata: Dictionary containing book metadata like title, creator, language, etc.
        - cover: Path to the extracted cover image
        - toc: Table of contents of the book
        - chapters: List of book chapters
        - final_name: Sanitized filename for the output audiobook file

        Args:
            session (dict): The session dictionary containing processing information and state.
            epubBook (EpubBook): The EPUB book object to extract metadata from.

        Returns:
            tuple: A tuple containing an error message (if any) and a boolean indicating success.
                  Returns (None, True) on success, (error_message, False) on failure.
        """
        try:
            # Create an instance of the EPubProcessor
            epub_processor = EPubProcessor()
            # Get the metadata from the session, or create an empty dictionary if it doesn't exist
            metadata = dict(session["metadata"]) if "metadata" in session else {}
            # Iterate over the metadata items
            for key, value in list(metadata.items()):
                # Get the metadata from the EPUB book
                data = epubBook.get_metadata("DC", key)
                # If the metadata exists, update the metadata dictionary
                if data:
                    for val, attributes in data:
                        metadata[key] = val
            # Set the language in metadata to the session's language if not already present
            if "language" not in metadata:
                metadata["language"] = session["language"]
            # Set the title in metadata to the title from the EPUB book, or the filename if it doesn't exist
            metadata["title"] = (
                metadata.get("title") or Path(session["ebook"]).stem.replace("_", " ")
            )
            # Get the creator from the metadata
            creator = metadata.get("creator")
            # Set the creator in metadata to False if it doesn't exist or is "Unknown"
            metadata["creator"] = (
                False if not creator or creator == "Unknown" else creator
            )
            # Update the session's metadata
            session["metadata"] = metadata
            try:
                # If the language in the metadata is 2 characters long, convert it to 3 characters
                meta_lan = session["metadata"]["language"]
                if len(meta_lan) == 2:
                    lang_array = languages.get(part1=meta_lan)
                    if lang_array:
                        session["metadata"]["language"] = lang_array.part3
            except Exception:
                traceback.print_exc()

            # If the language in the metadata is different from the session's language, print a warning
            if session["metadata"].get("language") != session["language"]:
                err = f"WARNING!!! language selected {session['language']} differs from the EPUB file language {session['metadata']['language']}"
                print(err)
            # Get the cover from the EPUB book
            session["cover"] = epub_processor.get_cover(epubBook, session)
            # If the cover doesn't exist, return an error
            if not session["cover"]:
                return "get_cover() failed!", False
            # Get the table of contents and chapters from the EPUB book
            session["toc"], session["chapters"] = epub_processor.get_chapters_in_sentences(epubBook, session)
            # Set the final name of the output file
            session["final_name"] = self.ebook_audio.get_sanitized(
                session["metadata"]["title"] + "." + session["output_format"]
            )
            # If the chapters don't exist, return an error
            if session["chapters"] is None:
                return "get_chapters_in_sentences() failed!", False
            # Return None for the error message and True for success
            return None, True
        except Exception as e:
            traceback.print_exc()
            return str(e), False

    def process_epub(self, session):
        try:
            epubBook = epub.read_epub(session["epub_path"], {"ignore_ncx": True})
            return self.process_epub_chapters(epubBook, session)
        except Exception as e:
            print(f"processEPub() Exception: {e}")
            return str(e), False

    def _process_custom_model(self, session):
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
                if analyze_uploaded_file(
                    session["custom_model"], required_files
                ):
                    model = self.ebook_audio.extract_custom_model(session["custom_model"], session)
                    if model is not None:
                        session["custom_model"] = model
                    else:
                        error = f"{model} could not be extracted or mandatory files are missing"
                else:
                    error = f'{os.path.basename(session["custom_model"])} is not a valid model or some required files are missing'
        return error

    def _process_voice(self, session):
        error = None
        session["voice_dir"] = os.path.join(
            voices_dir, "__sessions", f"voice-{session['id']}", session["language"]
        )
        os.makedirs(session["voice_dir"], exist_ok=True)
        [
            shutil.move(
                src, os.path.join(session["voice_dir"], os.path.basename(src))
            )
            for src in glob(
                os.path.join(os.path.dirname(session["voice_dir"]), "*.wav")
            )
            + (
                [
                    os.path.join(os.path.dirname(session["voice_dir"]), "bark")
                ]
                if os.path.isdir(
                    os.path.join(os.path.dirname(session["voice_dir"]), "bark")
                )
                and not os.path.exists(
                    os.path.join(session["voice_dir"], "bark")
                )
                else []
            )
        ]
        if session["voice"] is not None:
            voice_name = self.ebook_audio.get_sanitized(
                os.path.splitext(os.path.basename(session["voice"]))[0]
            )
            final_voice_file = os.path.join(
                session["voice_dir"], f"{voice_name}.wav"
            )
            if not os.path.exists(final_voice_file):
                extractor = VoiceExtractor(session, session["voice"], voice_name)
                status, msg = extractor.extract_voice()
                if status:
                    session["voice"] = final_voice_file
                else:
                    error = f"VoiceExtractor.extract_voice() failed! {msg}"
                    print(error)
        return error
