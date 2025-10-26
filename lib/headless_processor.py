import fnmatch
import hashlib
import os
import shutil
import sys
import uuid
from glob import glob
from pathlib import Path

import torch
from ebooklib import epub
from iso639 import languages

from lib.ebook_audio import combine_audio_chapters, get_sanitized
from .functions import (
    NATIVE,
    TTS_ENGINES,
    VoiceExtractor,
    analyze_uploaded_file,
    check_programs,
    default_engine_settings,
    default_gpu_wiki,
    default_output_split_hours,
    ebook_formats,
    extract_custom_model,
    get_chapters,
    get_compatible_tts_engines,
    get_cover,
    get_vram,
    is_gui_process,
    language_mapping,
    models,
    models_dir,
    prepare_dirs,
    reset_ebook_session,
    show_alert,
    tmp_dir,
    voices_dir,
    context,
)
from lib.epub import EPubProcessor, convert_chapters2audio


class EBookProcessor:
    def convert_ebook_batch(self, args, ctx=None):
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
            reset_ebook_session(args["session"])
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

    def convert_ebook(self, args, ctx=None):
        try:
            # global is_gui_process, context
            error = None
            id = None
            if args["language"] is not None:
                err, ok = self.validate_language(args)
                if ok is False:
                    return err, False

                session, id = self.init_session(args, ctx)

                info_session = f"\n*********** Session: {id} **************\nStore it in case of interruption, crash, reuse of custom model or custom voice,\nyou can resume the conversion with --session option"

                if not is_gui_process:
                    error = self._process_custom_model(session)
                    error = self._process_voice(session)
                if error is None:
                    if session["script_mode"] == NATIVE:
                        bool, e = check_programs("Calibre", "ebook-convert", "--version")
                        if not bool:
                            error = f"check_programs() Calibre failed: {e}"
                        bool, e = check_programs("FFmpeg", "ffmpeg", "-version")
                        if not bool:
                            error = f"check_programs() FFMPEG failed: {e}"
                    if error is None:
                        if self.prepare_session_cache(args, session):
                            self.gpu_check(is_gui_process, session)

                            self.gpu_check(self.is_gui_process, session)

                            epub_processor = EPubProcessor()
                            if epub_processor.convert2epub(id, self.context):
                                progress_status, passed = self.process_epub(id, self.context)
                                if passed:
                                    return progress_status, True
                                else:
                                    error = progress_status
                            else:
                                error = "convert2epub() failed!"
                            error = f"Temporary directory {session['process_dir']} not removed due to failure."
            else:
                error = f"Language {args['language']} is not supported."
            if session["cancellation_requested"]:
                error = "Cancelled"
            else:
                    if not is_gui_process and id is not None:
                        error += f"\n*********** Session: {id} **************\nStore it in case of interruption, crash, reuse of custom model or custom voice,\nyou can resume the conversion with --session option"
            print(error)
            return error, False
        except Exception as e:
            print(f"convert_ebook() Exception: {e}")
            return e, False

    def gpu_check(self, is_gui_process, session):
        session["filename_noext"] = os.path.splitext(
            os.path.basename(session["ebook"])
        )[0]
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
        session["epub_path"] = os.path.join(
            session["process_dir"],
            "__" + session["filename_noext"] + ".epub",
            )
        return prepare_dirs(args["ebook"], session)

    def init_session(self, args, ctx):
        # global is_gui_process, context
        if ctx is not None:
            context = ctx

        is_gui_process = args["is_gui_process"]
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
            if not is_gui_process or args["custom_model"] is None
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
        session["output_split_hours"] = (
            args["output_split_hours"]
            if args["output_split_hours"] is not None
            else default_output_split_hours
        )
        return dict(session), id

    def process_epub_chapters(self, epubBook, id, context):
        try:
            session = context.get_session(id)
            err, ok = self.prepare_epub_metadata(session, epubBook)
            if not ok:
                return err, False

            if not convert_chapters2audio(id, context):
                return "convert_chapters2audio() failed!", False
            msg = "Conversion successful. Combining sentences and chapters..."
            show_alert({"type": "info", "msg": msg})
            exported_files = combine_audio_chapters(id, context)
            if exported_files is None:
                return "combine_audio_chapters() error: exported_files not created!", False

            self.session_cache_cleanup(session)
            progress_status = f'Audiobook(s) {", ".join(os.path.basename(f) for f in exported_files)} created!'
            session["audiobook"] = exported_files[-1]
            print(f"\n*********** Session: {id} **************\nStore it in case of interruption, crash, reuse of custom model or custom voice,\nyou can resume the conversion with --session option")
            return progress_status, True
        except Exception as e:
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
        if is_gui_process:
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
        try:
            metadata = dict(session["metadata"])
            for key, value in list(metadata.items()):
                data = epubBook.get_metadata("DC", key)
                if data:
                    for val, attributes in data:
                        metadata[key] = val
            metadata["language"] = session["language"]
            metadata["title"] = (
                metadata.get("title") or Path(session["ebook"]).stem.replace("_", " ")
            )
            creator = metadata.get("creator")
            metadata["creator"] = (
                False if not creator or creator == "Unknown" else creator
            )
            session["metadata"] = metadata
            try:
                if len(session["metadata"]["language"]) == 2:
                    lang_array = languages.get(part1=session["language"])
                    if lang_array:
                        session["metadata"]["language"] = lang_array.part3
            except Exception:
                pass
            if session["metadata"].get("language") != session["language"]:
                err = f"WARNING!!! language selected {session['language']} differs from the EPUB file language {session['metadata']['language']}"
                print(err)
            session["cover"] = get_cover(epubBook, session)
            if not session["cover"]:
                return "get_cover() failed!", False
            session["toc"], session["chapters"] = get_chapters(epubBook, session)
            session["final_name"] = get_sanitized(
                session["metadata"]["title"] + "." + session["output_format"]
            )
            if session["chapters"] is None:
                return "get_chapters() failed!", False
            return None, True
        except Exception as e:
            return str(e), False

    def process_epub(self, id, context):
        try:
            session = context.get_session(id)
            epubBook = epub.read_epub(session["epub_path"], {"ignore_ncx": True})
            return self.process_epub_chapters(epubBook, id, context)
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
                    model = extract_custom_model(session["custom_model"], session)
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
            voice_name = get_sanitized(
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
