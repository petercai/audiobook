import argparse
import os
import socket
import subprocess
import sys
import tempfile

from lib import *
from lib.conf import (
    FULL_DOCKER,
    NATIVE,
    audiobooks_cli_dir,
    default_device,
    default_output_format,
    default_output_split,
    default_output_split_minutes,
    device_list,
    ebook_formats,
    interface_port,
    max_python_version,
    min_python_version,
    prog_version,
)
from lib.ebook_processor import EBookProcessor
from lib.functions import (
    SessionContext,
)
from lib.lang import default_language_code, install_info
from lib.models import TTS_ENGINES, default_engine_settings, default_fine_tuned
from lib.web_ui import WebUI


def build_arg_parser():
    # A single parser handles both GUI and headless flows; we partition arguments into groups
    # so `--help` stays readable and users immediately see which options apply to each mode.
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
    )
    tts_engine_list_keys = list(TTS_ENGINES.keys())
    tts_engine_list_values = list(TTS_ENGINES.values())

    # Always-available flags (common entry points and shared behavior).
    all_group = parser.add_argument_group(
        "**** The following options are for all modes", "Optional"
    )
    all_group.add_argument("--script_mode", type=str, help=argparse.SUPPRESS)
    parser.add_argument(
        "--session",
        type=str,
        help="""Session to resume the conversion in case of interruption, crash, 
    or reuse of custom models and custom cloning voices.""",
    )

    # GUI-only flags are isolated to prevent headless users from scanning through irrelevant args.
    gui_group = parser.add_argument_group(
        "**** The following option are for gradio/gui mode only", "Optional"
    )
    gui_group.add_argument(
        "--share",
        action="store_true",
        help="""Enable a public shareable Gradio link.""",
    )
    all_group.add_argument(
        "--offline_mode",
        action="store_true",
        help="""(Optional) Enable offline mode. The app will try to use cached models and data without internet access.""",
    )
    all_group.add_argument(
        "--add_toc_title",
        action="store_true",
        help="""(Optional) Enable adding TOC title to chapter for TTS.""",
    )

    # Headless options are split into required and optional groups so users can spot the
    # minimum viable arguments quickly; `batch_optional_group` keeps advanced tuning
    # flags separate, which avoids clutter in help output and reduces misconfiguration risk.
    batch_group = parser.add_argument_group(
        "**** The following options are for --headless mode only"
    )
    batch_group.add_argument(
        "--headless", action="store_true", help="""Run the script in headless mode"""
    )
    batch_group.add_argument(
        "--ebook",
        type=str,
        help="""Path to the ebook file for conversion. Cannot be used when --ebooks_dir is present.""",
    )
    batch_group.add_argument(
        "--ebooks_dir",
        type=str,
        help="""Relative or absolute path of the directory containing the files to convert. 
    Cannot be used when --ebook is present.""",
    )
    batch_group.add_argument(
        "--language",
        type=str,
        default=default_language_code,
        help="""Language of the e-book. Default language is set 
    in ./lib/lang.py sed as default if not present. All compatible language codes are in ./lib/lang.py""",
    )

    batch_optional_group = parser.add_argument_group("optional parameters")
    batch_optional_group.add_argument(
        "--voice",
        type=str,
        default=None,
        help="""(Optional) Path to the voice cloning file for TTS engine. 
    Uses the default voice if not present.""",
    )
    batch_optional_group.add_argument(
        "--device",
        type=str,
        default=default_device,
        choices=device_list,
        help="""(Optional) Pprocessor unit type for the conversion. 
    Default is set in ./lib/conf.py if not present. Fall back to CPU if GPU not available.""",
    )
    batch_optional_group.add_argument(
        "--tts_engine",
        type=str,
        default=None,
        choices=tts_engine_list_keys + tts_engine_list_values,
        help="""(Optional) Preferred TTS engine (available are: {tts_engine_list_keys + tts_engine_list_values}.
    Default depends on the selected language. The tts engine should be compatible with the chosen language""",
    )
    batch_optional_group.add_argument(
        "--custom_model",
        type=str,
        default=None,
        help="""(Optional) Path to the custom model zip file cntaining mandatory model files. 
    Please refer to ./lib/models.py""",
    )
    batch_optional_group.add_argument(
        "--fine_tuned",
        type=str,
        default=default_fine_tuned,
        help="""(Optional) Fine tuned model path. Default is builtin model.""",
    )
    batch_optional_group.add_argument(
        "--output_format",
        type=str,
        default=default_output_format,
        help="""(Optional) Output audio format. Default is set in ./lib/conf.py""",
    )
    batch_optional_group.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="""(xtts only, optional) Temperature for the model. 
    Default to config.json model. Higher temperatures lead to more creative outputs.""",
    )
    batch_optional_group.add_argument(
        "--length_penalty",
        type=float,
        default=None,
        help="""(xtts only, optional) A length penalty applied to the autoregressive decoder. 
    Default to config.json model. Not applied to custom models.""",
    )
    batch_optional_group.add_argument(
        "--num_beams",
        type=int,
        default=None,
        help="""(xtts only, optional) Controls how many alternative sequences the model explores. Must be equal or greater than length penalty. 
    Default to config.json model.""",
    )
    batch_optional_group.add_argument(
        "--repetition_penalty",
        type=float,
        default=None,
        help="""(xtts only, optional) A penalty that prevents the autoregressive decoder from repeating itself. 
    Default to config.json model.""",
    )
    batch_optional_group.add_argument(
        "--top_k",
        type=int,
        default=None,
        help="""(xtts only, optional) Top-k sampling. 
    Lower values mean more likely outputs and increased audio generation speed. 
    Default to config.json model.""",
    )
    batch_optional_group.add_argument(
        "--top_p",
        type=float,
        default=None,
        help="""(xtts only, optional) Top-p sampling. 
    Lower values mean more likely outputs and increased audio generation speed. Default to config.json model.""",
    )
    batch_optional_group.add_argument(
        "--speed",
        type=float,
        default=None,
        help="""(xtts only, optional) Speed factor for the speech generation. 
    Default to config.json model.""",
    )
    batch_optional_group.add_argument(
        "--enable_text_splitting",
        action="store_true",
        help="""(xtts only, optional) Enable TTS text splitting. This option is known to not be very efficient. 
    Default to config.json model.""",
    )
    batch_optional_group.add_argument(
        "--text_temp",
        type=float,
        default=None,
        help=f"""(bark only, optional) Text Temperature for the model. 
    Default to {default_engine_settings[TTS_ENGINES["BARK"]]["text_temp"]}. Higher temperatures lead to more creative outputs.""",
    )
    batch_optional_group.add_argument(
        "--waveform_temp",
        type=float,
        default=None,
        help=f"""(bark only, optional) Waveform Temperature for the model. 
    Default to {default_engine_settings[TTS_ENGINES["BARK"]]["waveform_temp"]}. Higher temperatures lead to more creative outputs.""",
    )
    batch_optional_group.add_argument(
        "--output_dir",
        type=str,
        help="""(Optional) Path to the output directory. Default is set in ./lib/conf.py""",
    )
    batch_optional_group.add_argument(
        "--version",
        action='version',
        version=f'ebook2audiobook version {prog_version}',
        help='''Show the version of the script and exit'''
    )
    batch_optional_group.add_argument(
        "--workflow", action='store_true', help=argparse.SUPPRESS
    )
    return parser


def parse_cli_args():
    parser = build_arg_parser()
    # Parse known args for speed, then explicitly reject unknown flags with a single error.
    args, unknown = parser.parse_known_args()
    if unknown:
        parser.error(f'Unrecognized option(s): {", ".join(unknown)}')
    return vars(args)


def main():
    args = parse_cli_args()

    if not 'help' in args:
        if not check_virtual_env(args['script_mode']):
            sys.exit(1)

        if not check_python_version():
            sys.exit(1)

        # Check if the port is already in use to prevent multiple launches
        if not args['headless'] and is_port_in_use(interface_port):
            error = f'Error: Port {interface_port} is already in use. The web interface may already be running.'
            print(error)
            sys.exit(1)

        args['script_mode'] = args.get('script_mode', NATIVE)
        # Set session ID to default if workflow mode is enabled
        if args['workflow']:
            args['session'] = 'ba800d22-ee51-11ef-ac34-d4ae52cfd9ce'
        # Set session ID to None if not provided
        elif not args['session']:
            args['session'] = None
        # args['offline_mode'] = bool(args['offline_mode'])
        args['share'] = bool(args['share'])
        args['ebook_list'] = None

        ctx = SessionContext()
        if args['headless']:
            start_batch(args, ctx)
        else:
            args['script_mode'] = '' # not script mode
            start_ui(args, ctx)


def start_batch(args, ctx):
    args['is_gui_process'] = False
    args['audiobooks_dir'] = os.path.abspath(args['output_dir']) if args['output_dir'] else audiobooks_cli_dir
    args['device'] = 'cuda' if args['device'] == 'gpu' else args['device']
    args['tts_engine'] = TTS_ENGINES[args['tts_engine']] if args['tts_engine'] in TTS_ENGINES.keys() else args[
        'tts_engine'] if args['tts_engine'] in TTS_ENGINES.values() else None
    args['output_split'] = default_output_split
    args['output_split_minutes'] = default_output_split_minutes
    args['offline_mode'] = args['offline_mode']
    # Condition to stop if both --ebook and --ebooks_dir are provided
    if args['ebook'] and args['ebooks_dir']:
        error = 'Error: You cannot specify both --ebook and --ebooks_dir in headless mode.'
        print(error)
        sys.exit(1)
    # convert in absolute path voice, custom_model if any
    if args['voice']:
        if os.path.exists(args['voice']):
            args['voice'] = os.path.abspath(args['voice'])
    if args['custom_model']:
        if os.path.exists(args['custom_model']):
            args['custom_model'] = os.path.abspath(args['custom_model'])
    if not os.path.exists(args['audiobooks_dir']):
        error = 'Error: --output_dir path does not exist.'
        print(error)
        sys.exit(1)
    if args['ebooks_dir']:
        args['ebooks_dir'] = os.path.abspath(args['ebooks_dir'])
        if not os.path.exists(args['ebooks_dir']):
            error = f'Error: The provided --ebooks_dir "{args["ebooks_dir"]}" does not exist.'
            print(error)
            sys.exit(1)
        args['ebook_list'] = []
        for file in os.listdir(args['ebooks_dir']):
            if any(file.endswith(ext) for ext in ebook_formats):
                full_path = os.path.abspath(os.path.join(args['ebooks_dir'], file))
                args['ebook_list'].append(full_path)
        ebook_processor = EBookProcessor()
        progress_status, passed = ebook_processor.convert_ebook_batch(args, ctx)
        if passed is False:
            error = f'Conversion failed: {progress_status}'
            print(error)
            sys.exit(1)
    elif args['ebook']:
        args['ebook'] = os.path.abspath(args['ebook'])
        if not os.path.exists(args['ebook']):
            error = f'Error: The provided --ebook "{args["ebook"]}" does not exist.'
            print(error)
            sys.exit(1)
        ebook_processor = EBookProcessor()
        progress_status, passed = ebook_processor.convert_ebook(args, ctx)
        if passed is False:
            error = f'Conversion failed: {progress_status}'
            print(error)
            sys.exit(1)
    else:
        error = 'Error: In headless mode, you must specify either an ebook file using --ebook or an ebook directory using --ebooks_dir.'
        print(error)
        sys.exit(1)


def start_ui(args, ctx):
    args['is_gui_process'] = True
    passed_arguments = sys.argv[1:]
    allowed_arguments = {'--share', '--script_mode', '--offline_mode'}
    passed_args_set = {arg for arg in passed_arguments if arg.startswith('--')}
    if passed_args_set.issubset(allowed_arguments):
        WebUI().launch(args, ctx)
    else:
        error = 'Error: In non-headless mode, no option or only --share can be passed'
        print(error)
        sys.exit(1)


if __name__ == '__main__':
    main()
