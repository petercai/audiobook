import json
import os
import platform
import re
import shutil
import socket
import threading
import uuid
from glob import glob
from pathlib import Path
from types import MappingProxyType

import gradio as gr
import psutil
from pydub.utils import mediainfo
from iso639 import languages
from lib.classes.voice_extractor import VoiceExtractor
from lib.conf import (
    models_dir,
    default_device,
    default_output_format,
    default_output_split,
    default_output_split_hours,
    ebook_formats,
    voice_formats,
    output_formats,
    prog_version,
    interface_component_options,
    voices_dir,
    audiobooks_gradio_dir,
    interface_shared_tmp_expire,
    tmp_expire,
    audiobooks_host_dir,
    debug_mode,
    interface_concurrency_limit,
    interface_host,
    interface_port,
)
from lib.models import (
    models,
    default_fine_tuned,
    default_tts_engine,
    default_engine_settings,
    TTS_ENGINES,
    max_custom_voices,
    max_custom_model,
    max_upload_size)
from lib.ebook_audio import EbookAudio
from lib.functions import (
    DependencyError,
    hash_proxy_dict,
    proxy2dict,
    delete_unused_tmp_dirs,
    get_compatible_tts_engines,
    reset_ebook_session,
    restore_session_from_data,
    show_alert,
    analyze_uploaded_file,
    extract_custom_model
)
from lib.headless_processor import EBookProcessor
from lib.lang import (language_mapping,
    default_language_code,
                      language_tts
                      )

active_sessions = set()

class SessionTracker:
    def __init__(self):
        self.lock = threading.Lock()

    def start_session(self, id, context):
        with self.lock:
            session = context.get_session(id)
            if session['status'] is None:
                session['status'] = 'ready'
                return True
        return False

    def end_session(self, id, socket_hash, context):
        active_sessions.discard(socket_hash)
        with self.lock:
            session = context.get_session(id)
            session['cancellation_requested'] = True
            session['tab_id'] = None
            session['status'] = None
            session[socket_hash] = None

ctx_tracker = SessionTracker()

def get_all_ip_addresses():
    ip_addresses = []
    for interface, addresses in psutil.net_if_addrs().items():
        for address in addresses:
            if address.family == socket.AF_INET:
                ip_addresses.append(address.address)
            elif address.family == socket.AF_INET6:
                ip_addresses.append(address.address)  
    return ip_addresses

class WebUI:
    def __init__(self):
        pass  # No logic in constructor, minimal/no states

    def launch(self, args, ctx):
        context = ctx
        script_mode = args['script_mode']
        is_gui_process = args['is_gui_process']
        is_gui_shared = args['share']
        title = 'Ebook2Audiobook'
        glass_mask_msg = 'Initialization, please wait...'
        ebook_src = None
        language_options = [
            (
                f"{details['name']} - {details['native_name']}" if details['name'] != details['native_name'] else details['name'],
                lang
            )
            for lang, details in language_mapping.items()
        ]
        voice_options = []
        tts_engine_options = []
        custom_model_options = []
        fine_tuned_options = []
        audiobook_options = []
        options_output_split_hours = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12']
        
        src_label_file = 'Select a File'
        src_label_dir = 'Select a Directory'
        
        visible_gr_tab_xtts_params = interface_component_options['gr_tab_xtts_params']
        visible_gr_tab_bark_params = interface_component_options['gr_tab_bark_params']
        visible_gr_group_custom_model = interface_component_options['gr_group_custom_model']
        visible_gr_group_voice_file = interface_component_options['gr_group_voice_file']

        theme = gr.themes.Origin(
            primary_hue='green',
            secondary_hue='amber',
            neutral_hue='gray',
            radius_size='lg',
            font_mono=['JetBrains Mono', 'monospace', 'Consolas', 'Menlo', 'Liberation Mono']
        )

        header_css = '''
            <style>
                /* Global Scrollbar Customization */
                /* The entire scrollbar */
                ::-webkit-scrollbar {
                    width: 6px !important;
                    height: 6px !important;
                    cursor: pointer !important;;
                }
                /* The scrollbar track (background) */
                ::-webkit-scrollbar-track {
                    background: none transparent !important;
                    border-radius: 6px !important;
                }
                /* The scrollbar thumb (scroll handle) */
                ::-webkit-scrollbar-thumb {
                    background: #c09340 !important;
                    border-radius: 6px !important;
                }
                /* The scrollbar thumb on hover */
                ::-webkit-scrollbar-thumb:hover {
                    background: #ff8c00 !important;
                }
                /* Firefox scrollbar styling */
                html {
                    scrollbar-width: thin !important;
                    scrollbar-color: #c09340 none !important;
                }
                .svelte-1xyfx7i.center.boundedheight.flex{
                    height: 120px !important;
                }
                .wrap-inner {
                    border: 1px solid #666666;
                }
                .block.svelte-5y6bt2 {
                    padding: 10px !important;
                    margin: 0 !important;
                    height: auto !important;
                    font-size: 16px !important;
                }
                .wrap.svelte-12ioyct {
                    padding: 0 !important;
                    margin: 0 !important;
                    font-size: 12px !important;
                }
                .block.svelte-5y6bt2.padded {
                    height: auto !important;
                    padding: 10px !important;
                }
                .block.svelte-5y6bt2.padded.hide-container {
                    height: auto !important;
                    padding: 0 !important;
                }
                .waveform-container.svelte-19usgod {
                    height: 58px !important;
                    overflow: hidden !important;
                    padding: 0 !important;
                    margin: 0 !important;
                }
                .component-wrapper.svelte-19usgod {
                    height: 110px !important;
                }
                .timestamps.svelte-19usgod {
                    display: none !important;
                }
                .controls.svelte-ije4bl {
                    padding: 0 !important;
                    margin: 0 !important;
                }
                .icon-btn {
                    font-size: 30px !important;
                }
                .small-btn {
                    font-size: 22px !important;
                    width: 60px !important;
                    height: 60px !important;
                    margin: 0 !important;
                    padding: 0 !important;
                }
                .file-preview-holder {
                    height: 116px !important;
                    overflow: auto !important;
                }
                .selected {
                    color: orange !important;
                }
                .progress-bar.svelte-ls20lj {
                    background: orange !important;
                }
                #glass-mask {
                    position: fixed !important;
                    top: 0 !important;
                    left: 0 !important;
                    width: 100vw !important; 
                    height: 100vh !important;
                    background: rgba(0,0,0,0.6) !important;
                    display: flex !important;
                    text-align: center;
                    align-items: center !important;
                    justify-content: center !important;
                    font-size: 1.2rem !important;
                    color: #fff !important;
                    z-index: 9999 !important;
                    transition: opacity 2s ease-out 2s !important;
                    pointer-events: all !important;
                }
                #glass-mask.hide {
                    opacity: 0 !important;
                    pointer-events: none !important;
                }
                #gr_markdown_logo {
                    position: absolute !important; 
                    text-align: right !important;
                }
                #gr_ebook_file, #gr_custom_model_file, #gr_voice_file {
                    height: 140px !important;
                }
                #gr_custom_model_file [aria-label="Clear"], #gr_voice_file [aria-label="Clear"] {
                    display: none !important;
                }               
                #gr_tts_engine_list, #gr_fine_tuned_list, #gr_session, #gr_output_format_list {
                    height: 95px !important;
                }
                #gr_voice_list {
                    height: 60px !important;
                }
                #gr_voice_list span[data-testid="block-info"],
                #gr_audiobook_list span[data-testid="block-info"]{
                    display: none !important;
                }
                ///////////////
                #gr_voice_player {
                    margin: 0 !important;
                    padding: 0 !important;
                    width: 60px !important;
                    height: 60px !important;
                }
                #gr_row_voice_player {
                    height: 60px !important;
                }
                #gr_voice_player :is(#waveform, .rewind, .skip, .playback, label, .volume, .empty) {
                    display: none !important;
                }
                #gr_voice_player .controls {
                    display: block !important;
                    position: absolute !important;
                    left: 15px !important;
                    top: 0 !important;
                }
                ///////////
                #gr_audiobook_player :is(.volume, .empty, .source-selection, .control-wrapper, .settings-wrapper) {
                    display: none !important;
                }
                #gr_audiobook_player label{
                    display: none !important;
                }
                #gr_audiobook_player audio {
                    width: 100% !important;
                    padding-top: 10px !important;
                    padding-bottom: 10px !important;
                    border-radius: 0px !important;
                    background-color: #ebedf0 !important;
                    color: #ffffff !important;
                }
                #gr_audiobook_player audio::-webkit-media-controls-panel {
                    width: 100% !important;
                    padding-top: 10px !important;
                    padding-bottom: 10px !important;
                    border-radius: 0px !important;
                    background-color: #ebedf0 !important;
                    color: #ffffff !important;
                }
                ////////////
                .fade-in {
                    animation: fadeIn 1s ease-in;
                    display: inline-block;
                }
                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
            </style>
        '''
        
        with gr.Blocks(theme=theme, title=title, css=header_css, delete_cache=(86400, 86400)) as app:
            with gr.Tabs(elem_id='gr_tabs'):
                gr_tab_main = gr.TabItem('Main Parameters', elem_id='gr_tab_main', elem_classes='tab_item')
                with gr_tab_main:
                    with gr.Row(elem_id='gr_row_tab_main'):
                        with gr.Column(elem_id='gr_col_1', scale=3):
                            with gr.Group(elem_id='gr1'):
                                gr_ebook_file = gr.File(label=src_label_file, elem_id='gr_ebook_file', file_types=ebook_formats, file_count='single', allow_reordering=True, height=140)
                                gr_ebook_mode = gr.Radio(label='', elem_id='gr_ebook_mode', choices=[('File','single'), ('Directory','directory')], value='single', interactive=True)
                            with gr.Group(elem_id='gr_group_language'):
                                gr_language = gr.Dropdown(label='Language', elem_id='gr_language', choices=language_options, value=default_language_code, type='value', interactive=True)
                            gr_group_voice_file = gr.Group(elem_id='gr_group_voice_file', visible=visible_gr_group_voice_file)
                            with gr_group_voice_file:
                                gr_voice_file = gr.File(label='*Cloning Voice Audio Fiie', elem_id='gr_voice_file', file_types=voice_formats, value=None, height=140)
                                gr_row_voice_player = gr.Row(elem_id='gr_row_voice_player')
                                with gr_row_voice_player:
                                    gr_voice_player = gr.Audio(elem_id='gr_voice_player', type='filepath', interactive=False, show_download_button=False, container=False, visible=False, show_share_button=False, show_label=False, waveform_options=gr.WaveformOptions(show_controls=False), scale=0, min_width=60)
                                    gr_voice_list = gr.Dropdown(label='', elem_id='gr_voice_list', choices=voice_options, type='value', interactive=True, scale=2)
                                    gr_voice_del_btn = gr.Button('🗑', elem_id='gr_voice_del_btn', elem_classes=['small-btn'], variant='secondary', interactive=True, visible=False, scale=0, min_width=60)
                                gr_optional_markdown = gr.Markdown(elem_id='gr_markdown_optional', value='<p>&nbsp;&nbsp;* Optional</p>')
                            with gr.Group(elem_id='gr_group_device'):
                                gr_device = gr.Dropdown(label='Processor Unit', elem_id='gr_device', choices=[('CPU','cpu'), ('GPU','cuda'), ('MPS','mps')], type='value', value=default_device, interactive=True)
                                gr_logo_markdown = gr.Markdown(elem_id='gr_logo_markdown', value=f'''
                                    <div style="right:0;margin:auto;padding:10px;text-align:right">
                                        <a href="https://github.com/DrewThomasson/ebook2audiobook" style="text-decoration:none;font-size:14px" target="_blank">
                                        <b>{title}</b>&nbsp;<b style="color:orange">{prog_version}</b></a>
                                    </div>
                                    '''
                                )
                        with gr.Column(elem_id='gr_col_2', scale=3):
                            with gr.Group(elem_id='gr_group_engine'):
                                gr_tts_engine_list = gr.Dropdown(label='TTS Engine', elem_id='gr_tts_engine_list', choices=tts_engine_options, type='value', interactive=True)
                                gr_tts_rating = gr.HTML()
                                gr_fine_tuned_list = gr.Dropdown(label='Fine Tuned Models (Presets)', elem_id='gr_fine_tuned_list', choices=fine_tuned_options, type='value', interactive=True)
                                gr_group_custom_model = gr.Group(visible=visible_gr_group_custom_model)
                                with gr_group_custom_model:
                                    gr_custom_model_file = gr.File(label=f"Upload Fine Tuned Model", elem_id='gr_custom_model_file', value=None, file_types=['.zip'], height=140)
                                    with gr.Row(elem_id='gr_row_custom_model'):
                                        gr_custom_model_list = gr.Dropdown(label='', elem_id='gr_custom_model_list', choices=custom_model_options, type='value', interactive=True, scale=2)
                                        gr_custom_model_del_btn = gr.Button('🗑', elem_id='gr_custom_model_del_btn', elem_classes=['small-btn'], variant='secondary', interactive=True, visible=False, scale=0, min_width=60)
                                    gr_custom_model_markdown = gr.Markdown(elem_id='gr_markdown_custom_model', value='<p>&nbsp;&nbsp;* Optional</p>')
                            with gr.Group(elem_id='gr_group_output_format'):
                                with gr.Row(elem_id='gr_row_output_format'):
                                    gr_output_format_list = gr.Dropdown(label='Output Format', elem_id='gr_output_format_list', choices=output_formats, type='value', value=default_output_format, interactive=True, scale=2)
                                    gr_output_split = gr.Checkbox(label='Split Output File', elem_id='gr_output_split', value=default_output_split, interactive=True, scale=1)
                                    gr_output_split_hours = gr.Dropdown(label='Max hours / part', elem_id='gr_output_split_hours', choices=options_output_split_hours, type='value', value=default_output_split_hours, interactive=True, visible=False, scale=2)
                            gr_session = gr.Textbox(label='Session', elem_id='gr_session', interactive=False)
                gr_tab_xtts_params = gr.TabItem('XTTSv2 Fine Tuned Parameters', elem_id='gr_tab_xtts_params', elem_classes='tab_item', visible=visible_gr_tab_xtts_params)           
                with gr_tab_xtts_params:
                    gr.Markdown(
                        elem_id='gr_markdown_tab_xtts_params',
                        value='''
                        ### Customize XTTSv2 Parameters
                        Adjust the settings below to influence how the audio is generated. You can control the creativity, speed, repetition, and more.
                        '''
                    )
                    gr_xtts_temperature = gr.Slider(
                        label='Temperature',
                        minimum=0.05,
                        maximum=10.0,
                        step=0.05,
                        value=float(default_engine_settings[TTS_ENGINES['XTTSv2']]['temperature']),
                        elem_id='gr_xtts_temperature',
                        info='Higher values lead to more creative, unpredictable outputs. Lower values make it more monotone.'
                    )
                    gr_xtts_length_penalty = gr.Slider(
                        label='Length Penalty',
                        minimum=0.3,
                        maximum=5.0,
                        step=0.1,
                        value=float(default_engine_settings[TTS_ENGINES['XTTSv2']]['length_penalty']),
                        elem_id='gr_xtts_length_penalty',
                        info='Adjusts how much longer sequences are preferred. Higher values encourage the model to produce longer and more natural speech.',
                        visible=False
                    )
                    gr_xtts_num_beams = gr.Slider(
                        label='Number Beams',
                        minimum=1,
                        maximum=10,
                        step=1,
                        value=int(default_engine_settings[TTS_ENGINES['XTTSv2']]['num_beams']),
                        elem_id='gr_xtts_num_beams',
                        info='Controls how many alternative sequences the model explores. Higher values improve speech coherence and pronunciation but increase inference time.',
                        visible=False
                    )
                    gr_xtts_repetition_penalty = gr.Slider(
                        label='Repetition Penalty',
                        minimum=1.0,
                        maximum=10.0,
                        step=0.1,
                        value=float(default_engine_settings[TTS_ENGINES['XTTSv2']]['repetition_penalty']),
                        elem_id='gr_xtts_repetition_penalty',
                        info='Penalizes repeated phrases. Higher values reduce repetition.'
                    )
                    gr_xtts_top_k = gr.Slider(
                        label='Top-k Sampling',
                        minimum=10,
                        maximum=100,
                        step=1,
                        value=int(default_engine_settings[TTS_ENGINES['XTTSv2']]['top_k']),
                        elem_id='gr_xtts_top_k',
                        info='Lower values restrict outputs to more likely words and increase speed at which audio generates.'
                    )
                    gr_xtts_top_p = gr.Slider(
                        label='Top-p Sampling',
                        minimum=0.1,
                        maximum=1.0, 
                        step=0.01,
                        value=float(default_engine_settings[TTS_ENGINES['XTTSv2']]['top_p']),
                        elem_id='gr_xtts_top_p',
                        info='Controls cumulative probability for word selection. Lower values make the output more predictable and increase speed at which audio generates.'
                    )
                    gr_xtts_speed = gr.Slider(
                        label='Speed', 
                        minimum=0.5, 
                        maximum=3.0, 
                        step=0.1, 
                        value=float(default_engine_settings[TTS_ENGINES['XTTSv2']]['speed']),
                        elem_id='gr_xtts_speed',
                        info='Adjusts how fast the narrator will speak.'
                    )
                    gr_xtts_enable_text_splitting = gr.Checkbox(
                        label='Enable Text Splitting', 
                        value=default_engine_settings[TTS_ENGINES['XTTSv2']]['enable_text_splitting'],
                        elem_id='gr_xtts_enable_text_splitting',
                        info='Coqui-tts builtin text splitting. Can help against hallucinations bu can also be worse.',
                        visible=False
                    )
                gr_tab_bark_params = gr.TabItem('BARK fine Tuned Parameters', elem_id='gr_tab_bark_params', elem_classes='tab_item', visible=visible_gr_tab_bark_params)           
                with gr_tab_bark_params:
                    gr.Markdown(
                        elem_id='gr_markdown_tab_bark_params',
                        value='''
                        ### Customize BARK Parameters
                        Adjust the settings below to influence how the audio is generated, emotional and voice behavior random or more conservative
                        '''
                    )
                    gr_bark_text_temp = gr.Slider(
                        label='Text Temperature', 
                        minimum=0.0,
                        maximum=1.0,
                        step=0.01,
                        value=float(default_engine_settings[TTS_ENGINES['BARK']]['text_temp']),
                        elem_id='gr_bark_text_temp',
                        info='Higher values lead to more creative, unpredictable outputs. Lower values make it more conservative.'
                    )
                    gr_bark_waveform_temp = gr.Slider(
                        label='Waveform Temperature', 
                        minimum=0.0,
                        maximum=1.0,
                        step=0.01,
                        value=float(default_engine_settings[TTS_ENGINES['BARK']]['waveform_temp']),
                        elem_id='gr_bark_waveform_temp',
                        info='Higher values lead to more creative, unpredictable outputs. Lower values make it more conservative.'
                    )
                gr_tab_voxcpm_params = gr.TabItem('VOXCPM fine Tuned Parameters', elem_id='gr_tab_voxcpm_params', elem_classes='tab_item', visible=False)
                with gr_tab_voxcpm_params:
                    gr.Markdown(
                        elem_id='gr_markdown_tab_voxcpm_params',
                        value='''
                        ### Customize VOXCPM Parameters
                        Adjust the settings below to influence how the audio is generated.
                        '''
                    )
                    gr_voxcpm_cfg_value = gr.Slider(
                        label='CFG Value',
                        minimum=0.0,
                        maximum=10.0,
                        step=0.1,
                        value=float(default_engine_settings[TTS_ENGINES['VOXCPM']]['cfg_value']),
                        elem_id='gr_voxcpm_cfg_value',
                        info='Higher for better adherence to the prompt, but maybe worse.'
                    )
                    gr_voxcpm_inference_timesteps = gr.Slider(
                        label='Inference Timesteps',
                        minimum=1,
                        maximum=100,
                        step=1,
                        value=int(default_engine_settings[TTS_ENGINES['VOXCPM']]['inference_timesteps']),
                        elem_id='gr_voxcpm_inference_timesteps',
                        info='Higher for better result, lower for fast speed.'
                    )
                    gr_voxcpm_normalize = gr.Checkbox(
                        label='Normalize',
                        value=default_engine_settings[TTS_ENGINES['VOXCPM']]['normalize'],
                        elem_id='gr_voxcpm_normalize',
                        info='Enable external TN tool.'
                    )
                    gr_voxcpm_denoise = gr.Checkbox(
                        label='Denoise',
                        value=default_engine_settings[TTS_ENGINES['VOXCPM']]['denoise'],
                        elem_id='gr_voxcpm_denoise',
                        info='Enable external Denoise tool.'
                    )
                    gr_voxcpm_retry_badcase = gr.Checkbox(
                        label='Retry Badcase',
                        value=default_engine_settings[TTS_ENGINES['VOXCPM']]['retry_badcase'],
                        elem_id='gr_voxcpm_retry_badcase',
                        info='Enable retrying mode for some bad cases (unstoppable).'
                    )
                    gr_voxcpm_retry_badcase_max_times = gr.Slider(
                        label='Retry Badcase Max Times',
                        minimum=1,
                        maximum=10,
                        step=1,
                        value=int(default_engine_settings[TTS_ENGINES['VOXCPM']]['retry_badcase_max_times']),
                        elem_id='gr_voxcpm_retry_badcase_max_times',
                        info='Maximum retrying times.'
                    )
                    gr_voxcpm_retry_badcase_ratio_threshold = gr.Slider(
                        label='Retry Badcase Ratio Threshold',
                        minimum=0.0,
                        maximum=10.0,
                        step=0.1,
                        value=float(default_engine_settings[TTS_ENGINES['VOXCPM']]['retry_badcase_ratio_threshold']),
                        elem_id='gr_voxcpm_retry_badcase_ratio_threshold',
                        info='Maximum length restriction for bad case detection.'
                    )
                    gr_voxcpm_prompt_text = gr.Textbox(
                        label='Prompt Text',
                        value="Default prompt text",
                        elem_id='gr_voxcpm_prompt_text',
                        info='Reference text for the prompt speech.'
                    )
            gr_state_update = gr.State(value={"hash": None})
            gr_read_data = gr.JSON(visible=False, elem_id='gr_read_data')
            gr_write_data = gr.JSON(visible=False, elem_id='gr_write_data')
            gr_tab_progress = gr.Textbox(elem_id='gr_tab_progress', label='Progress', interactive=False)
            gr_group_audiobook_list = gr.Group(elem_id='gr_group_audiobook_list', visible=False)
            with gr_group_audiobook_list:
                gr_audiobook_vtt = gr.Textbox(elem_id='gr_audiobook_vtt', label='', interactive=False, visible=False)
                gr_audiobook_sentence = gr.Textbox(elem_id='gr_audiobook_sentence', label='Audiobook', value='...', interactive=False, visible=True, lines=3, max_lines=3)
                gr_audiobook_player = gr.Audio(elem_id='gr_audiobook_player', label='',type='filepath', autoplay=False, waveform_options=gr.WaveformOptions(show_recording_waveform=False), show_download_button=False, show_share_button=False, container=True, interactive=False, visible=True)
                gr_audiobook_player_playback_time = gr.Number(label='', interactive=False, visible=True, elem_id="gr_audiobook_player_playback_time", value=0.0)
                with gr.Row(elem_id='gr_row_audiobook_list'):
                    gr_audiobook_download_btn = gr.DownloadButton(elem_id='gr_audiobook_download_btn', label='↧', elem_classes=['small-btn'], variant='secondary', interactive=True, visible=True, scale=0, min_width=60)
                    gr_audiobook_list = gr.Dropdown(elem_id='gr_audiobook_list', label='', choices=audiobook_options, type='value', interactive=True, visible=True, scale=2)
                    gr_audiobook_del_btn = gr.Button(elem_id='gr_audiobook_del_btn', value='🗑', elem_classes=['small-btn'], variant='secondary', interactive=True, visible=True, scale=0, min_width=60)
            gr_convert_btn = gr.Button(elem_id='gr_convert_btn', value='📚', elem_classes='icon-btn', variant='primary', interactive=False)
            
            gr_modal = gr.HTML(visible=False)
            gr_glass_mask = gr.HTML(f'<div id="glass-mask">{glass_mask_msg}</div>')
            gr_confirm_field_hidden = gr.Textbox(elem_id='confirm_hidden', visible=False)
            gr_confirm_yes_btn = gr.Button(elem_id='confirm_yes_btn', value='', visible=False)
            gr_confirm_no_btn = gr.Button(elem_id='confirm_no_btn', value='', visible=False)

            def cleanup_session(req: gr.Request):
                socket_hash = req.session_hash
                if any(socket_hash in session for session in context.sessions.values()):
                    session_id = context.find_id_by_hash(socket_hash)
                    ctx_tracker.end_session(session_id, socket_hash, context)

            def load_vtt_data(path):
                if not path or not os.path.exists(path):
                    return None
                try:
                    vtt_path = Path(path).with_suffix('.vtt')
                    if not os.path.exists(vtt_path):
                        return None
                    with open(vtt_path, "r", encoding="utf-8-sig", errors="replace") as f:
                        content = f.read()
                    return content
                except Exception:
                    return None

            def show_modal(type, msg):
                return f'''
                <style>
                    .modal {{
                        display: none; /* Hidden by default */
                        position: fixed;
                        top: 0;
                        left: 0;
                        width: 100%;
                        height: 100%;
                        background-color: rgba(0, 0, 0, 0.5);
                        z-index: 9999;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                    }}
                    .modal-content {{
                        background-color: #333;
                        padding: 20px;
                        border-radius: 8px;
                        text-align: center;
                        max-width: 300px;
                        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.5);
                        border: 2px solid #FFA500;
                        color: white;
                        position: relative;
                    }}
                    .modal-content p {{
                        margin: 10px 0;
                    }}
                    .confirm-buttons {{
                        display: flex;
                        justify-content: space-evenly;
                        margin-top: 20px;
                    }}
                    .confirm-buttons button {{
                        padding: 10px 20px;
                        border: none;
                        border-radius: 5px;
                        font-size: 16px;
                        cursor: pointer;
                    }}
                    .confirm-buttons .confirm_yes_btn {{
                        background-color: #28a745;
                        color: white;
                    }}
                    .confirm-buttons .confirm_no_btn {{
                        background-color: #dc3545;
                        color: white;
                    }}
                    .confirm-buttons .confirm_yes_btn:hover {{
                        background-color: #34d058;
                    }}
                    .confirm-buttons .confirm_no_btn:hover {{
                        background-color: #ff6f71;
                    }}
                    /* Spinner */
                    .spinner {{
                        margin: 15px auto;
                        border: 4px solid rgba(255, 255, 255, 0.2);
                        border-top: 4px solid #FFA500;
                        border-radius: 50%;
                        width: 30px;
                        height: 30px;
                        animation: spin 1s linear infinite;
                    }}
                    @keyframes spin {{
                        0% {{ transform: rotate(0deg); }}
                        100% {{ transform: rotate(360deg); }}
                    }}
                </style>
                <div id="custom-modal" class="modal">
                    <div class="modal-content">
                        <p style="color:#ffffff">{msg}</p>            
                        {show_confirm() if type == 'confirm' else '<div class="spinner"></div>'}
                    </div>
                </div>
                '''

            def show_confirm():
                return '''
                <div class="confirm-buttons">
                    <button class="confirm_yes_btn" onclick="document.querySelector('#confirm_yes_btn').click()">✔</button>
                    <button class="confirm_no_btn" onclick="document.query_selector('#confirm_no_btn').click()">⨉</button>
                </div>
                '''

            def show_rating(tts_engine):

                def yellow_stars(n):
                    return "".join(
                        "<span style='color:#f0bc00; font-size:12px'>★</span>" for _ in range(n)
                    )

                def color_box(value):
                    if value <= 4:
                        color = "#4CAF50"  # Green = low
                    elif value <= 8:
                        color = "#FF9800"  # Orange = medium
                    else:
                        color = "#F44336"  # Red = high
                    return f"<span style='background:{color};color:white;padding:1px 5px;border-radius:3px;font-size:11px'>{value} GB</span>"
                
                rating = default_engine_settings[tts_engine]['rating']

                return f"""
                <div style='margin:0; padding:0; font-size:12px; line-height:1.2; height:auto; display:flex; flex-wrap:wrap; align-items:center; gap:6px 12px;'>
                  <span style='display:inline-flex; white-space:nowrap; padding:0 10px'><b>GPU VRAM:</b> {color_box(rating["GPU VRAM"])}</span>
                  <span style='display:inline-flex; white-space:nowrap; padding:0 10px'><b>CPU:</b> {yellow_stars(rating["CPU"])}</span>
                  <span style='display:inline-flex; white-space:nowrap; padding:0 10px'><b>RAM:</b> {color_box(rating["RAM"])}</span>
                  <span style='display:inline-flex; white-space:nowrap; padding:0 10px'><b>Realism:</b> {yellow_stars(rating["Realism"])}</span>
                </div>
                """

            def alert_exception(error):
                gr.Error(error)
                DependencyError(error)

            def restore_interface(id, req: gr.Request):
                try:
                    session = context.get_session(id)
                    socket_hash = req.session_hash
                    if not session.get(socket_hash):
                        outputs = tuple([gr.update() for _ in range(24)])
                        return outputs
                    session = context.get_session(id)
                    ebook_data = None
                    file_count = session['ebook_mode']
                    if isinstance(session['ebook_list'], list) and file_count == 'directory':
                        #ebook_data = session['ebook_list']
                        ebook_data = None
                    elif isinstance(session['ebook'], str) and file_count == 'single':
                        ebook_data = session['ebook']
                    else:
                        ebook_data = None
                    ### XTTSv2 Params
                    session['temperature'] = session['temperature'] if session['temperature'] else default_engine_settings[TTS_ENGINES['XTTSv2']]['temperature']
                    session['length_penalty'] = default_engine_settings[TTS_ENGINES['XTTSv2']]['length_penalty']
                    session['num_beams'] = default_engine_settings[TTS_ENGINES['XTTSv2']]['num_beams']
                    session['repetition_penalty'] = session['repetition_penalty'] if session['repetition_penalty'] else default_engine_settings[TTS_ENGINES['XTTSv2']]['repetition_penalty']
                    session['top_k'] = session['top_k'] if session['top_k'] else default_engine_settings[TTS_ENGINES['XTTSv2']]['top_k']
                    session['top_p'] = session['top_p'] if session['top_p'] else default_engine_settings[TTS_ENGINES['XTTSv2']]['top_p']
                    session['speed'] = session['speed'] if session['speed'] else default_engine_settings[TTS_ENGINES['XTTSv2']]['speed']
                    session['enable_text_splitting'] = default_engine_settings[TTS_ENGINES['XTTSv2']]['enable_text_splitting']
                    ### BARK Params
                    session['text_temp'] = session['text_temp'] if session['text_temp'] else default_engine_settings[TTS_ENGINES['BARK']]['text_temp']
                    session['waveform_temp'] = session['waveform_temp'] if session['waveform_temp'] else default_engine_settings[TTS_ENGINES['BARK']]['waveform_temp']
                    ### VOXCPM Params
                    session['cfg_value'] = session['cfg_value'] if session['cfg_value'] else default_engine_settings[TTS_ENGINES['VOXCPM']]['cfg_value']
                    session['inference_timesteps'] = session['inference_timesteps'] if session['inference_timesteps'] else default_engine_settings[TTS_ENGINES['VOXCPM']]['inference_timesteps']
                    session['normalize'] = session['normalize'] if session['normalize'] else default_engine_settings[TTS_ENGINES['VOXCPM']]['normalize']
                    session['denoise'] = session['denoise'] if session['denoise'] else default_engine_settings[TTS_ENGINES['VOXCPM']]['denoise']
                    session['retry_badcase'] = session['retry_badcase'] if session['retry_badcase'] else default_engine_settings[TTS_ENGINES['VOXCPM']]['retry_badcase']
                    session['retry_badcase_max_times'] = session['retry_badcase_max_times'] if session['retry_badcase_max_times'] else default_engine_settings[TTS_ENGINES['VOXCPM']]['retry_badcase_max_times']
                    session['retry_badcase_ratio_threshold'] = session['retry_badcase_ratio_threshold'] if session['retry_badcase_ratio_threshold'] else default_engine_settings[TTS_ENGINES['VOXCPM']]['retry_badcase_ratio_threshold']
                    return (
                        gr.update(value=ebook_data), gr.update(value=session['ebook_mode']), gr.update(value=session['device']),
                        gr.update(value=session['language']), self.update_gr_tts_engine_list(id), self.update_gr_custom_model_list(id),
                        self.update_gr_fine_tuned_list(id), gr.update(value=session['output_format']), self.update_gr_audiobook_list(id), gr.update(value=load_vtt_data(session['audiobook'])),
                        gr.update(value=float(session['temperature'])), gr.update(value=float(session['length_penalty'])), gr.update(value=int(session['num_beams'])),
                        gr.update(value=float(session['repetition_penalty'])), gr.update(value=int(session['top_k'])), gr.update(value=float(session['top_p'])), gr.update(value=float(session['speed'])), 
                        gr.update(value=bool(session['enable_text_splitting'])), gr.update(value=float(session['text_temp'])), gr.update(value=float(session['waveform_temp'])),
                        gr.update(value=float(session['cfg_value'])), gr.update(value=int(session['inference_timesteps'])), gr.update(value=bool(session['normalize'])),
                        gr.update(value=bool(session['denoise'])), gr.update(value=bool(session['retry_badcase'])), gr.update(value=int(session['retry_badcase_max_times'])),
                        gr.update(value=float(session['retry_badcase_ratio_threshold'])),
                        self.update_gr_voice_list(id),
                        gr.update(value=session['output_split']), gr.update(value=session['output_split_hours']), gr.update(active=True)
                    )
                except Exception as e:
	                error = f'restore_interface(): {e}'
	                alert_exception(error)
	                outputs = tuple([gr.update() for _ in range(24)])
	                return outputs

