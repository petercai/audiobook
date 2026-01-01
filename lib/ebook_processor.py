import os
import sys
import traceback
from glob import glob
from pathlib import Path

import torch
from ebooklib import epub
from iso639 import languages

from lib.ebook_audio import EbookAudio
from .classes.voice_extractor import VoiceExtractor
from lib.conf import default_gpu_wiki, ebook_formats
from lib.conf import NATIVE
from lib.models import TTS_ENGINES
from lib.customized_model import CustomizedModel
from lib.functions import check_programs
from lib.models import default_engine_settings
from lib.functions import get_vram
from lib.functions import show_alert
from lib.conf import voices_dir
from lib.epub import EPubProcessor
from lib.session_managment import SessionManagement
from .lang import language_mapping


class EBookProcessor:
    def __init__(self):
        self.ebook_audio = EbookAudio()
        self.customized_model = CustomizedModel()
        self.session_management = SessionManagement()

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
            self.session_management.reset_ebook_session(ctx, args["session"])
            return progress_status, passed
        else:
            print(f"the ebooks source is not a list!")
            sys.exit(1)

    def validate_language(self, args):
        """
        Validates the language and ebook file path provided in the arguments.

        This method performs several checks:
        1. Ensures the ebook file has a format extension.
        2. Verifies that the ebook file exists.
        3. Converts the language code to ISO 639-2 (part3) and ISO 639-1 (part1) if a 2-letter or 3-letter code is provided.
        4. Checks if the provided language is supported by the system.

        Args:
            args (dict): A dictionary containing the following keys:
                - "ebook" (str): The path to the ebook file.
                - "language" (str): The language code (e.g., "en", "eng").

        Returns:
            tuple: A tuple containing:
                - str or None: An error message if validation fails, otherwise None.
                - bool: True if validation is successful, False otherwise.
        """
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
                self.is_gui_process = args["is_gui_process"]
                self.session_management.set_is_gui_process(self.is_gui_process)
                session, id = self.session_management.init_session(args, context)

                # 3. Process custom models and voices if running in headless mode.
                # if not args.get("is_gui_process", False):
                #     error = self.customized_model.process_custom_model(session)
                #     if error is None:
                #         error = self._process_voice(session)

                # 4. Proceed if no errors have occurred yet.
                if error is None:
                    # 5. Check for required external dependencies (FFmpeg) in native mode.
                    if session["script_mode"] == NATIVE:
                        bool, e = check_programs("FFmpeg", "ffmpeg", "-version")
                        if not bool:
                            error = f"check_programs() FFMPEG failed: {e}"

                    # 6. Proceed if all dependencies are met.
                    if error is None:
                        # Prepare session-specific cache directories.
                        if self.session_management.prepare_session_cache(args, session):
                            # 7. Check GPU availability and configure the processing device.
                            self.gpu_check(self.is_gui_process, session)

                            # 8. Convert the source ebook to EPUB format, which is the standard for processing.
                            # 8. onely support epub now. no need to convert
                            # epub_processor = EPubProcessor(session)
                            session["epub_path"] = session["ebook"]
                            # if epub_processor.convert2epub(session):
                            # 9. Process the EPUB: extract text, generate TTS, and create the audiobook.
                            progress_status, passed = self.process_epub(session)
                            if passed:
                                return progress_status, True
                            else:
                                error = progress_status
                            # else:
                            #     error = "convert2epub() failed!"
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
            epub_processor = EPubProcessor(session)
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
            # self.session_management.session_cache_cleanup(session)
            
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
            epub_processor = EPubProcessor(session)
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
