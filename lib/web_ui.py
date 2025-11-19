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
from starlette.requests import ClientDisconnect
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
    default_output_split_minutes,
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
        self.context = None
        self.voice_options = []
        self.tts_engine_options = []
        self.custom_model_options = []
        self.fine_tuned_options = []
        self.audiobook_options = []
        self.is_gui_process = True
        self.src_label_file = 'Select a File'
        self.src_label_dir = 'Select a Directory'
        self.ebook_audio = EbookAudio()
        
    def cleanup_session(self, context, req: gr.Request):
        socket_hash = req.session_hash
        if any(socket_hash in session for session in context.sessions.values()):
            session_id = context.find_id_by_hash(socket_hash)
            ctx_tracker.end_session(session_id, socket_hash, context)

    def load_vtt_data(self, path):
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

    def launch(self, args, ctx):
        self.context = ctx
        self.script_mode = args['script_mode']
        self.is_gui_shared = args['share']
        self.offline_mode = args.get('offline_mode', False)
        title = 'Ebook2Audiobook'
        glass_mask_msg = 'Initialization, please wait...'
        ebook_src = None
        language_options = [(f"{details['name']} - {details['native_name']}" if details['name'] != details['native_name'] else details['name'], lang) for lang, details in language_mapping.items()]
        options_output_split_minutes = ['10', '15', '20', '30', '45', '60', '90', '120']
        
        
        
        visible_gr_tab_xtts_params = interface_component_options['gr_tab_xtts_params']
        visible_gr_tab_bark_params = interface_component_options['gr_tab_bark_params']
        self.visible_gr_group_custom_model = interface_component_options['gr_group_custom_model']
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
                                gr_ebook_file = gr.File(label=self.src_label_file, elem_id='gr_ebook_file', file_types=ebook_formats, file_count='single', allow_reordering=True, height=140)
                                gr_ebook_mode = gr.Radio(label='', elem_id='gr_ebook_mode', choices=[('File','single'), ('Directory','directory')], value='single', interactive=True)
                            with gr.Group(elem_id='gr_group_language'):
                                gr_language = gr.Dropdown(label='Language', elem_id='gr_language', choices=language_options, value=default_language_code, type='value', interactive=True)
                            gr_group_voice_file = gr.Group(elem_id='gr_group_voice_file', visible=visible_gr_group_voice_file)
                            with gr_group_voice_file:
                                gr_voice_file = gr.File(label='*Cloning Voice Audio Fiie', elem_id='gr_voice_file', file_types=voice_formats, value=None, height=140)
                                gr_row_voice_player = gr.Row(elem_id='gr_row_voice_player')
                                with gr_row_voice_player:
                                    gr_voice_player = gr.Audio(elem_id='gr_voice_player', type='filepath', interactive=False, show_download_button=False, container=False, visible=False, show_share_button=False, show_label=False, waveform_options=gr.WaveformOptions(show_controls=False), scale=0, min_width=60)
                                    gr_voice_list = gr.Dropdown(label='', elem_id='gr_voice_list', choices=self.voice_options, type='value', interactive=True, scale=2)
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
                                gr_tts_engine_list = gr.Dropdown(label='TTS Engine', elem_id='gr_tts_engine_list', choices=self.tts_engine_options, type='value', interactive=True)
                                gr_tts_rating = gr.HTML()
                                gr_fine_tuned_list = gr.Dropdown(label='Fine Tuned Models (Presets)', elem_id='gr_fine_tuned_list', choices=self.fine_tuned_options, type='value', interactive=True)
                                gr_group_custom_model = gr.Group(visible=self.visible_gr_group_custom_model)
                                with gr_group_custom_model:
                                    gr_custom_model_file = gr.File(label=f"Upload Fine Tuned Model", elem_id='gr_custom_model_file', value=None, file_types=['.zip'], height=140)
                                    with gr.Row(elem_id='gr_row_custom_model'):
                                        gr_custom_model_list = gr.Dropdown(label='', elem_id='gr_custom_model_list', choices=self.custom_model_options, type='value', interactive=True, scale=2)
                                        gr_custom_model_del_btn = gr.Button('🗑', elem_id='gr_custom_model_del_btn', elem_classes=['small-btn'], variant='secondary', interactive=True, visible=False, scale=0, min_width=60)
                                    gr_custom_model_markdown = gr.Markdown(elem_id='gr_markdown_custom_model', value='<p>&nbsp;&nbsp;* Optional</p>')
                            with gr.Group(elem_id='gr_group_output_format'):
                                with gr.Row(elem_id='gr_row_output_format'):
                                    gr_output_format_list = gr.Dropdown(label='Output Format', elem_id='gr_output_format_list', choices=output_formats, type='value', value=default_output_format, interactive=True, scale=2)
                                    gr_output_split = gr.Checkbox(label='Split Output File', elem_id='gr_output_split', value=default_output_split, interactive=True, scale=1)
                                    gr_output_split_minutes = gr.Dropdown(label='Max minutes / part', elem_id='gr_output_split_minutes', choices=options_output_split_minutes, type='value', value=default_output_split_minutes, interactive=True, visible=False, scale=2)
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
                    gr_audiobook_list = gr.Dropdown(elem_id='gr_audiobook_list', label='', choices=self.audiobook_options, type='value', interactive=True, visible=True, scale=2)
                    gr_audiobook_del_btn = gr.Button(elem_id='gr_audiobook_del_btn', value='🗑', elem_classes=['small-btn'], variant='secondary', interactive=True, visible=True, scale=0, min_width=60)
            gr_convert_btn = gr.Button(elem_id='gr_convert_btn', value='📚', elem_classes='icon-btn', variant='primary', interactive=False)
            
            gr_modal = gr.HTML(visible=False)
            gr_glass_mask = gr.HTML(f'<div id="glass-mask">{glass_mask_msg}</div>')
            gr_confirm_field_hidden = gr.Textbox(elem_id='confirm_hidden', visible=False)
            gr_confirm_yes_btn = gr.Button(elem_id='confirm_yes_btn', value='', visible=False)
            gr_confirm_no_btn = gr.Button(elem_id='confirm_no_btn', value='', visible=False)
            gr_ebook_file.change(
                fn=self.state_convert_btn,
                inputs=[gr_ebook_file, gr_ebook_mode, gr_custom_model_file, gr_session],
                outputs=[gr_convert_btn]
            ).then(
                fn=self.change_gr_ebook_file,
                inputs=[gr_ebook_file, gr_session],
                outputs=[gr_modal]
            )
            gr_ebook_mode.change(
                fn=self.change_gr_ebook_mode,
                inputs=[gr_ebook_mode, gr_session],
                outputs=[gr_ebook_file]
            )
            gr_voice_file.upload(
                fn=self.change_gr_voice_file,
                inputs=[gr_voice_file, gr_session],
                outputs=[gr_voice_file]
            ).then(
                fn=self.update_gr_voice_list,
                inputs=[gr_session],
                outputs=[gr_voice_list]
            )
            gr_voice_list.change(
                fn=self.change_gr_voice_list,
                inputs=[gr_voice_list, gr_session],
                outputs=[gr_voice_player, gr_voice_del_btn]
            )
            gr_voice_del_btn.click(
                fn=self.click_gr_voice_del_btn,
                inputs=[gr_voice_list, gr_session],
                outputs=[gr_confirm_field_hidden, gr_modal, gr_confirm_yes_btn, gr_confirm_no_btn]
            )
            gr_device.change(
                fn=self.change_gr_device,
                inputs=[gr_device, gr_session],
                outputs=None
            )
            gr_language.change(
                fn=self.change_gr_language,
                inputs=[gr_language, gr_session],
                outputs=[gr_language, gr_tts_engine_list, gr_custom_model_list, gr_fine_tuned_list]
            ).then(
                fn=self.update_gr_voice_list,
                inputs=[gr_session],
                outputs=[gr_voice_list]
            )
            gr_tts_engine_list.change(
                fn=self.change_gr_tts_engine_list,
                inputs=[gr_tts_engine_list, gr_session],
                outputs=[gr_tts_rating, gr_tab_xtts_params, gr_tab_bark_params, gr_tab_voxcpm_params,
                         gr_group_custom_model, gr_fine_tuned_list, gr_custom_model_file, gr_custom_model_list]
            ).then(
                fn=self.update_gr_voice_list,
                inputs=[gr_session],
                outputs=[gr_voice_list]
            )
            gr_fine_tuned_list.change(
                fn=self.change_gr_fine_tuned_list,
                inputs=[gr_fine_tuned_list, gr_session],
                outputs=[gr_group_custom_model]
            ).then(
                fn=self.update_gr_voice_list,
                inputs=[gr_session],
                outputs=[gr_voice_list]
            )
            gr_custom_model_file.upload(
                fn=self.change_gr_custom_model_file,
                inputs=[gr_custom_model_file, gr_tts_engine_list, gr_session],
                outputs=[gr_custom_model_file]
            ).then(
                fn=self.update_gr_custom_model_list,
                inputs=[gr_session],
                outputs=[gr_custom_model_list]
            )
            gr_custom_model_list.change(
                fn=self.change_gr_custom_model_list,
                inputs=[gr_custom_model_list, gr_session],
                outputs=[gr_fine_tuned_list, gr_custom_model_del_btn]
            )
            gr_custom_model_del_btn.click(
                fn=self.click_gr_custom_model_del_btn,
                inputs=[gr_custom_model_list, gr_session],
                outputs=[gr_confirm_field_hidden, gr_modal, gr_confirm_yes_btn, gr_confirm_no_btn]
            )
            gr_output_format_list.change(
                fn=self.change_gr_output_format_list,
                inputs=[gr_output_format_list, gr_session],
                outputs=None
            )
            gr_output_split.change(
                fn=self.change_gr_output_split,
                inputs=[gr_output_split, gr_session],
                outputs=gr_output_split_minutes
            )
            gr_output_split_minutes.change(
                fn=self.change_gr_output_split_hours,
                inputs=[gr_output_split_minutes, gr_session],
                outputs=None
            )
            gr_audiobook_vtt.change(
                fn=lambda: gr.update(value=''),
                inputs=[],
                outputs=[gr_audiobook_sentence]
            ).then(
                fn=None,
                inputs=[gr_audiobook_vtt],
                js='(data)=>{window.load_vtt?.(URL.createObjectURL(new Blob([data],{type: "text/vtt"})));}'
            )
            gr_tab_progress.change(
                fn=None,
                inputs=[gr_tab_progress],
                outputs=[],
                js=f'() => {{ document.title = "{title}"; }}'
            )
            gr_audiobook_player_playback_time.change(
                fn=self.change_gr_audiobook_player_playback_time,
                inputs=[gr_audiobook_player_playback_time, gr_session],
                outputs=[]
            )
            gr_audiobook_download_btn.click(
                fn=lambda audiobook: show_alert({"type": "info", "msg": f'Downloading {os.path.basename(audiobook)}'}),
                inputs=[gr_audiobook_list],
                outputs=None,
                show_progress='minimal'
            )
            gr_audiobook_list.change(
                fn=self.change_gr_audiobook_list,
                inputs=[gr_audiobook_list, gr_session],
                outputs=[gr_audiobook_download_btn, gr_audiobook_player, gr_audiobook_vtt, gr_group_audiobook_list]
            )
            gr_audiobook_del_btn.click(
                fn=self.click_gr_audiobook_del_btn,
                inputs=[gr_audiobook_list, gr_session],
                outputs=[gr_confirm_field_hidden, gr_modal, gr_confirm_yes_btn, gr_confirm_no_btn]
            )
            ########### XTTSv2 Params
            gr_xtts_temperature.change(
                fn=lambda val, id: self.change_param('temperature', val, id),
                inputs=[gr_xtts_temperature, gr_session],
                outputs=None
            )
            gr_xtts_length_penalty.change(
                fn=lambda val, id, val2: self.change_param('length_penalty', val, id, val2),
                inputs=[gr_xtts_length_penalty, gr_session, gr_xtts_num_beams],
                outputs=None,
            )
            gr_xtts_num_beams.change(
                fn=lambda val, id, val2: self.change_param('num_beams', val, id, val2),
                inputs=[gr_xtts_num_beams, gr_session, gr_xtts_length_penalty],
                outputs=None,
            )
            gr_xtts_repetition_penalty.change(
                fn=lambda val, id: self.change_param('repetition_penalty', val, id),
                inputs=[gr_xtts_repetition_penalty, gr_session],
                outputs=None
            )
            gr_xtts_top_k.change(
                fn=lambda val, id: self.change_param('top_k', val, id),
                inputs=[gr_xtts_top_k, gr_session],
                outputs=None
            )
            gr_xtts_top_p.change(
                fn=lambda val, id: self.change_param('top_p', val, id),
                inputs=[gr_xtts_top_p, gr_session],
                outputs=None
            )
            gr_xtts_speed.change(
                fn=lambda val, id: self.change_param('speed', val, id),
                inputs=[gr_xtts_speed, gr_session],
                outputs=None
            )
            gr_xtts_enable_text_splitting.change(
                fn=lambda val, id: self.change_param('enable_text_splitting', val, id),
                inputs=[gr_xtts_enable_text_splitting, gr_session],
                outputs=None
            )
            ########### BARK Params
            gr_bark_text_temp.change(
                fn=lambda val, id: self.change_param('text_temp', val, id),
                inputs=[gr_bark_text_temp, gr_session],
                outputs=None
            )
            gr_bark_waveform_temp.change(
                fn=lambda val, id: self.change_param('waveform_temp', val, id),
                inputs=[gr_bark_waveform_temp, gr_session],
                outputs=None
            )
            ########### VOXCPM Params
            gr_voxcpm_cfg_value.change(
                fn=lambda val, id: self.change_param('cfg_value', val, id),
                inputs=[gr_voxcpm_cfg_value, gr_session],
                outputs=None
            )
            gr_voxcpm_inference_timesteps.change(
                fn=lambda val, id: self.change_param('inference_timesteps', val, id),
                inputs=[gr_voxcpm_inference_timesteps, gr_session],
                outputs=None
            )
            gr_voxcpm_normalize.change(
                fn=lambda val, id: self.change_param('normalize', val, id),
                inputs=[gr_voxcpm_normalize, gr_session],
                outputs=None
            )
            gr_voxcpm_denoise.change(
                fn=lambda val, id: self.change_param('denoise', val, id),
                inputs=[gr_voxcpm_denoise, gr_session],
                outputs=None
            )
            gr_voxcpm_retry_badcase.change(
                fn=lambda val, id: self.change_param('retry_badcase', val, id),
                inputs=[gr_voxcpm_retry_badcase, gr_session],
                outputs=None
            )
            gr_voxcpm_retry_badcase_max_times.change(
                fn=lambda val, id: self.change_param('retry_badcase_max_times', val, id),
                inputs=[gr_voxcpm_retry_badcase_max_times, gr_session],
                outputs=None
            )
            gr_voxcpm_retry_badcase_ratio_threshold.change(
                fn=lambda val, id: self.change_param('retry_badcase_ratio_threshold', val, id),
                inputs=[gr_voxcpm_retry_badcase_ratio_threshold, gr_session],
                outputs=None
            )
            ############ Timer to save session to localStorage
            gr_timer = gr.Timer(9, active=False)
            gr_timer.tick(
                fn=self.save_session,
                inputs=[gr_session, gr_state_update],
                outputs=[gr_write_data, gr_state_update, gr_audiobook_list]
            ).then(
                fn=self.clear_event,
                inputs=[gr_session],
                outputs=None
            )
            gr_convert_btn.click(
                fn=self.state_convert_btn,
                inputs=None,
                outputs=[gr_convert_btn]
            ).then(
                fn=self.disable_components,
                inputs=[],
                outputs=[gr_ebook_mode, gr_language, gr_voice_file, gr_voice_list, gr_device, gr_tts_engine_list,
                         gr_fine_tuned_list, gr_custom_model_file, gr_custom_model_list]
            ).then(
                fn=self.submit_convert_btn,
                inputs=[
                    gr_session, gr_device, gr_ebook_file, gr_tts_engine_list, gr_language, gr_voice_list,
                    gr_custom_model_list, gr_fine_tuned_list, gr_output_format_list,
                    gr_xtts_temperature, gr_xtts_length_penalty, gr_xtts_num_beams, gr_xtts_repetition_penalty,
                    gr_xtts_top_k, gr_xtts_top_p, gr_xtts_speed, gr_xtts_enable_text_splitting,
                    gr_bark_text_temp, gr_bark_waveform_temp,
                    gr_voxcpm_cfg_value, gr_voxcpm_inference_timesteps, gr_voxcpm_normalize, gr_voxcpm_denoise,
                    gr_voxcpm_retry_badcase, gr_voxcpm_retry_badcase_max_times, gr_voxcpm_retry_badcase_ratio_threshold,
                    gr_voxcpm_prompt_text,
                    gr_output_split, gr_output_split_minutes
                ],
                outputs=[gr_tab_progress]
            ).then(
                fn=self.enable_components,
                inputs=[],
                outputs=[gr_ebook_mode, gr_language, gr_voice_file, gr_voice_list, gr_device, gr_tts_engine_list,
                         gr_fine_tuned_list, gr_custom_model_file, gr_custom_model_list]
            ).then(
                fn=self.refresh_interface,
                inputs=[gr_session],
                outputs=[gr_convert_btn, gr_ebook_file, gr_audiobook_list, gr_audiobook_player, gr_modal, gr_voice_list]
            )
            gr_write_data.change(
                fn=None,
                inputs=[gr_write_data],
                js="""
                        (data)=>{
                            try{
                                if(data){
                                    localStorage.clear();
                                    if(data['event'] != 'clear'){
                                        //console.log('save: ', data);
                                        window.localStorage.setItem('data', JSON.stringify(data));
                                    }
                                }
                            }catch(e){
                                console.log('gr_write_data.change error: '+e)
                            }
                        }
                    """
            )
            gr_read_data.change(
                fn=self.change_gr_read_data,
                inputs=[gr_read_data, gr_state_update],
                outputs=[gr_write_data, gr_state_update, gr_session, gr_glass_mask]
            ).then(
                fn=self.restore_interface,
                inputs=[gr_session],
                outputs=[
                    gr_ebook_file, gr_ebook_mode, gr_device, gr_language,
                    gr_tts_engine_list, gr_custom_model_list, gr_fine_tuned_list,
                    gr_output_format_list, gr_audiobook_list, gr_audiobook_vtt,
                    gr_xtts_temperature, gr_xtts_length_penalty, gr_xtts_num_beams, gr_xtts_repetition_penalty,
                    gr_xtts_top_k, gr_xtts_top_p, gr_xtts_speed, gr_xtts_enable_text_splitting, gr_bark_text_temp,
                    gr_bark_waveform_temp,
                    gr_voxcpm_cfg_value, gr_voxcpm_inference_timesteps, gr_voxcpm_normalize, gr_voxcpm_denoise,
                    gr_voxcpm_retry_badcase, gr_voxcpm_retry_badcase_max_times, gr_voxcpm_retry_badcase_ratio_threshold,
                    gr_voice_list, gr_output_split, gr_output_split_minutes, gr_timer
                ]
            ).then(
                fn=lambda session: self.update_gr_glass_mask(attr='class="hide"') if session else gr.update(),
                inputs=[gr_session],
                outputs=[gr_glass_mask]
            )
            gr_confirm_yes_btn.click(
                fn=self.confirm_deletion,
                inputs=[gr_voice_list, gr_custom_model_list, gr_audiobook_list, gr_session, gr_confirm_field_hidden],
                outputs=[gr_custom_model_list, gr_audiobook_list, gr_modal, gr_voice_list, gr_confirm_yes_btn,
                         gr_confirm_no_btn]
            )
            gr_confirm_no_btn.click(
                fn=self.confirm_deletion,
                inputs=[gr_voice_list, gr_custom_model_list, gr_audiobook_list, gr_session],
                outputs=[gr_custom_model_list, gr_audiobook_list, gr_modal, gr_voice_list, gr_confirm_yes_btn,
                         gr_confirm_no_btn]
            )
            app.load(
                fn=None,
                js=r'''
                        ()=>{
                            try {
                                if (typeof(window.init_elements) !== "function") {
                                    window.init_elements = () => {
                                        try {
                                            let lastCue = null;
                                            let fade_timeout = null;
                                            let last_time = 0;
                                            if (gr_root && gr_checkboxes && gr_radios && gr_audiobook_player_playback_time && gr_audiobook_sentence && gr_tab_progress) {
                                                let set_playback_time = false;
                                                gr_audiobook_player.addEventListener("loadedmetadata", () => {
                                                    //console.log("loadedmetadata:", window.playback_time);
                                                    if (window.playback_time > 0) {
                                                        gr_audiobook_player.currentTime = window.playback_time;
                                                    }
                                                    set_playback_time = true;
                                                },{once: true});
                                                gr_audiobook_player.addEventListener("timeupdate", () => {
                                                    if (set_playback_time == true) {
                                                        window.playback_time = gr_audiobook_player.currentTime;
                                                        const cue = findCue(window.playback_time);
                                                        if (cue && cue !== lastCue) {
                                                            if (fade_timeout) {
                                                                gr_audiobook_sentence.style.opacity = "1";
                                                            } else {
                                                                gr_audiobook_sentence.style.opacity = "0";
                                                            }
                                                            gr_audiobook_sentence.style.transition = "none";
                                                            gr_audiobook_sentence.value = cue.text;
                                                            clearTimeout(fade_timeout);
                                                            fade_timeout = setTimeout(() => {
                                                                gr_audiobook_sentence.style.transition = "opacity 0.1s ease-in";
                                                                gr_audiobook_sentence.style.opacity = "1";
                                                                fade_timeout = null;
                                                            }, 33);
                                                            lastCue = cue;
                                                        } else if (!cue && lastCue !== null) {
                                                            gr_audiobook_sentence.value = "...";
                                                            lastCue = null;
                                                        }
                                                        const now = performance.now();
                                                        if (now - last_time > 1000) {
                                                            //console.log("timeupdate", window.playback_time);
                                                            gr_audiobook_player_playback_time.value = String(window.playback_time);
                                                            gr_audiobook_player_playback_time.dispatchEvent(new Event("input", { bubbles: true }));
                                                            last_time = now;
                                                        }
                                                    }
                                                });
                                                gr_audiobook_player.addEventListener("ended", () => {
                                                    gr_audiobook_sentence.value = "...";
                                                    lastCue = null;
                                                });

                                                ///////////////

                                                // Observe programmatic changes
                                                new MutationObserver(tab_progress).observe(gr_tab_progress, { attributes: true, childList: true, subtree: true, characterData: true });
                                                // Also catch user edits
                                                gr_tab_progress.addEventListener("input", tab_progress);

                                                ///////////////

                                                const url = new URL(window.location);
                                                const theme = url.searchParams.get("__theme");
                                                let osTheme;
                                                let audioFilter = "";
                                                let elColor = "#666666";
                                                if (theme) {
                                                    if (theme === "dark") {
                                                        if (gr_audiobook_player) {
                                                            audioFilter = "invert(1) hue-rotate(180deg)";
                                                        }
                                                        elColor = "#fff";
                                                    }
                                                    gr_checkboxes.forEach(cb => { cb.style.border = "1px solid " + elColor; });
                                                    gr_radios.forEach(cb => { cb.style.border = "1px solid " + elColor; });
                                                } else {
                                                    osTheme = window.matchMedia?.("(prefers-color-scheme: dark)").matches;
                                                    if (osTheme) {
                                                        if (gr_audiobook_player) {
                                                            audioFilter = "invert(1) hue-rotate(180deg)";
                                                        }
                                                        elColor = "#fff";
                                                    }
                                                    gr_checkboxes.forEach(cb => { cb.style.border = "1px solid " + elColor; });
                                                    gr_radios.forEach(cb => { cb.style.border = "1px solid " + elColor; });
                                                }
                                                if (!gr_audiobook_player.style.transition) {
                                                    gr_audiobook_player.style.transition = "filter 1s ease";
                                                }
                                                gr_audiobook_player.style.filter = audioFilter;
                                            }
                                        } catch (e) {
                                            console.log("init_elements error:", e);
                                        }
                                    };
                                }
                                if (typeof(window.load_vtt) !== "function") {
                                    window.load_vtt_timeout = null;
                                    window.load_vtt = (path) => {
                                        try {
                                            if (gr_audiobook_player && gr_audiobook_player_playback_time && gr_audiobook_sentence) {
                                                // Remove any <track> to bypass browser subtitle engine
                                                let existing = gr_root.querySelector("#gr_audiobook_track");
                                                if (existing) {
                                                    existing.remove();
                                                }
                                                gr_audiobook_sentence.style.fontSize = "14px";
                                                gr_audiobook_sentence.style.fontWeight = "bold";
                                                gr_audiobook_sentence.style.width = "100%";
                                                gr_audiobook_sentence.style.height = "auto";
                                                gr_audiobook_sentence.style.textAlign = "center";
                                                gr_audiobook_sentence.style.margin = "0";
                                                gr_audiobook_sentence.style.padding = "7px 0 7px 0";
                                                gr_audiobook_sentence.style.lineHeight = "14px";
                                                gr_audiobook_sentence.value = "...";
                                                if (path) {
                                                    fetch(path).then(res => res.text()).then(vttText => {
                                                        parseVTTFast(vttText);
                                                    });
                                                }
                                                gr_audiobook_player.load();
                                            } else {
                                                clearTimeout(window.load_vtt_timeout);
                                                window.load_vtt_timeout = setTimeout(window.load_vtt, 500, path);
                                            }
                                        } catch (e) {
                                            console.log("load_vtt error:", e);
                                        }
                                    };
                                }
                                if (typeof(window.tab_progress) !== "function") {
                                    window.tab_progress = () => {
                                        const val = gr_tab_progress?.value || gr_tab_progress?.textContent || "";
                                        const prct = val.trim().split(" ")[4];
                                        if (prct && /^\d+(\.\d+)?%$/.test(prct)) {
                                            document.title = "Ebook2Audiobook: " + prct;
                                        }
                                    };
                                }
                                function parseVTTFast(vtt) {
                                    const lines = vtt.split(/\r?\n/);
                                    const timePattern = /(\d{2}:)?\d{2}:\d{2}\.\d{3}/;
                                    let start = null, end = null, textBuffer = [];
                                    cues = [];

                                    function pushCue() {
                                        if (start !== null && end !== null && textBuffer.length) {
                                            cues.push({ start, end, text: textBuffer.join("\n") });
                                        }
                                        start = end = null;
                                        textBuffer.length = 0;
                                    }

                                    for (let i = 0, len = lines.length; i < len; i++) {
                                        const line = lines[i];
                                        if (!line.trim()) { pushCue(); continue; }
                                        if (line.includes("-->")) {
                                            const [s, e] = line.split("-->").map(l => l.trim().split(" ")[0]);
                                            if (timePattern.test(s) && timePattern.test(e)) {
                                                start = toSeconds(s);
                                                end = toSeconds(e);
                                            }
                                        } else if (!timePattern.test(line)) {
                                            textBuffer.push(line);
                                        }
                                    }
                                    pushCue();
                                }

                                function toSeconds(ts) {
                                    const parts = ts.split(":");
                                    if (parts.length === 3) {
                                        return parseInt(parts[0], 10) * 3600 +
                                               parseInt(parts[1], 10) * 60 +
                                               parseFloat(parts[2]);
                                    }
                                    return parseInt(parts[0], 10) * 60 + parseFloat(parts[1]);
                                }

                                function findCue(time) {
                                    let lo = 0, hi = cues.length - 1;
                                    while (lo <= hi) {
                                        const mid = (lo + hi) >> 1;
                                        const cue = cues[mid];
                                        if (time < cue.start) {
                                            hi = mid - 1;
                                        } else if (time >= cue.end) {
                                            lo = mid + 1;
                                        } else {
                                            return cue;
                                        }
                                    }
                                    return null;
                                }

                                //////////////////////

                                let gr_root;
                                let gr_checkboxes;
                                let gr_radios;
                                let gr_audiobook_player_playback_time;
                                let gr_audiobook_sentence;
                                let gr_audiobook_player;
                                let gr_tab_progress;
                                let load_timeout;
                                let cues = [];

                                function init() {
                                    try {
                                        gr_root = (window.gradioApp && window.gradioApp()) || document;
                                        if (!gr_root) {
                                            clearTimeout(load_timeout);
                                            load_timeout = setTimeout(init, 1000);
                                            return;
                                        }
                                        gr_audiobook_player = gr_root.querySelector("#gr_audiobook_player");
                                        gr_audiobook_player_playback_time = gr_root.querySelector("#gr_audiobook_player_playback_time input");
                                        gr_audiobook_sentence = gr_root.querySelector("#gr_audiobook_sentence textarea");
                                        gr_tab_progress = gr_root.querySelector("#gr_tab_progress");
                                        gr_checkboxes = gr_root.querySelectorAll("input[type='checkbox']");
                                        gr_radios = gr_root.querySelectorAll("input[type='radio']");
                                        // If key elements aren’t mounted yet, retry
                                        if (!gr_audiobook_player || !gr_audiobook_player_playback_time) {
                                            clearTimeout(load_timeout);
                                            //console.log("Componenents not ready... retrying");
                                            load_timeout = setTimeout(init, 1000);
                                            return;
                                        }
                                        // if container, get inner <audio>/<video>
                                        if (gr_audiobook_player && !gr_audiobook_player.matches?.("audio,video")) {
                                            const real = gr_audiobook_player.querySelector?.("audio,video");
                                            if (real) gr_audiobook_player = real;
                                        }
                                        //console.log("Componenents ready!");
                                        window.init_elements();
                                    } catch (e) {
                                        console.log("init error:", e);
                                        clearTimeout(load_timeout);
                                        load_timeout = setTimeout(init, 1000);
                                    }
                                }

                                init();

                                window.addEventListener("beforeunload", () => {
                                    try {
                                        const saved = JSON.parse(localStorage.getItem("data") || "{}");
                                        if (saved.tab_id == window.tab_id || !saved.tab_id) {
                                            saved.tab_id = undefined;
                                            saved.status = undefined;
                                            localStorage.setItem("data", JSON.stringify(saved));
                                        }
                                    } catch (e) {
                                        console.log("Error updating status on unload:", e);
                                    }
                                });

                                window.playback_time = 0;
                                const stored = window.localStorage.getItem("data");
                                if (stored) {
                                    const parsed = JSON.parse(stored);
                                    parsed.tab_id = "tab-" + performance.now().toString(36) + "-" + Math.random().toString(36).substring(2, 10);
                                    window.playback_time = parsed.playback_time;
                                    //console.log("window.playback_time", window.playback_time);
                                    return parsed;
                                }
                            } catch (e) {
                                console.log("gr_raed_data js error:", e);
                            }
                            return null;
                        }
                    ''',
                outputs=[gr_read_data],
            )
            app.unload(lambda req: self.cleanup_session(self.context, req))
        try:
            all_ips = get_all_ip_addresses()
            msg = f'IPs available for connection:\n{all_ips}\nNote: 0.0.0.0 is not the IP to connect. Instead use an IP above to connect.'
            show_alert({"type": "info", "msg": msg})
            os.environ['no_proxy'] = ' ,'.join(all_ips)
            app.queue(default_concurrency_limit=interface_concurrency_limit).launch(
                debug=bool(int(os.environ.get('GRADIO_DEBUG', '0'))), show_error=debug_mode,
                favicon_path='./favicon.ico', server_name=interface_host, server_port=interface_port,
                share=self.is_gui_shared, max_file_size=max_upload_size)
        except OSError as e:
            error = f'Connection error: {e}'
            self.alert_exception(error)
        except socket.error as e:
            error = f'Socket error: {e}'
            self.alert_exception(error)
        except KeyboardInterrupt:
            error = 'Server interrupted by user. Shutting down...'
            self.alert_exception(error)
        except Exception as e:
            error = f'An unexpected error occurred: {e}'
            self.alert_exception(error)

    def show_modal(self, type, msg):
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
                {self.show_confirm() if type == 'confirm' else '<div class="spinner"></div>'}
            </div>
        </div>
        '''

    def show_confirm(self):
        return '''
        <div class="confirm-buttons">
            <button class="confirm_yes_btn" onclick="document.querySelector('#confirm_yes_btn').click()">✔</button>
        <button class="confirm_no_btn" onclick="document.querySelector('#confirm_no_btn').click()">⨉</button>
        </div>
        '''

    def show_rating(self, tts_engine):

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

    def alert_exception(self, error):
        gr.Error(error)
        DependencyError(error)

    def restore_interface(self, id, req: gr.Request):
        try:
            session = self.context.get_session(id)
            socket_hash = req.session_hash
            if not session.get(socket_hash):
                outputs = tuple([gr.update() for _ in range(24)])
                return outputs
            session = self.context.get_session(id)
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
                self.update_gr_fine_tuned_list(id), gr.update(value=session['output_format']), self.update_gr_audiobook_list(id), gr.update(value=self.load_vtt_data(session['audiobook'])),
                gr.update(value=float(session['temperature'])), gr.update(value=float(session['length_penalty'])), gr.update(value=int(session['num_beams'])),
                gr.update(value=float(session['repetition_penalty'])), gr.update(value=int(session['top_k'])), gr.update(value=float(session['top_p'])), gr.update(value=float(session['speed'])), 
                gr.update(value=bool(session['enable_text_splitting'])), gr.update(value=float(session['text_temp'])), gr.update(value=float(session['waveform_temp'])),
                gr.update(value=float(session['cfg_value'])), gr.update(value=int(session['inference_timesteps'])), gr.update(value=bool(session['normalize'])),
                gr.update(value=bool(session['denoise'])), gr.update(value=bool(session['retry_badcase'])), gr.update(value=int(session['retry_badcase_max_times'])),
                gr.update(value=float(session['retry_badcase_ratio_threshold'])),
                self.update_gr_voice_list(id),
                gr.update(value=session['output_split']), gr.update(value=session['output_split_minutes']), gr.update(active=True)
            )
        except Exception as e:
            error = f'restore_interface(): {e}'
            self.alert_exception(error)
            outputs = tuple([gr.update() for _ in range(24)])
            return outputs

    def refresh_interface(self, id):
        session = self.context.get_session(id)
        return (
                gr.update(interactive=False), gr.update(value=None), self.update_gr_audiobook_list(id), 
                gr.update(value=session['audiobook']), gr.update(visible=False), self.update_gr_voice_list(id)
        )

    def change_gr_audiobook_list(self, selected, id):
        """
        Handles changes in the audiobook selection dropdown.

        This method is triggered when a user selects a different audiobook from the list.
        It updates the session with the selected audiobook, retrieves its metadata,
        and updates the UI components accordingly, such as the audio player and VTT data.

        Args:
            selected (str): The file path of the selected audiobook.
            id (str): The session ID to retrieve the correct session context.

        Returns:
            tuple: A tuple of Gradio updates for various UI components, including
                   the download button, audio player, VTT data, and the visibility
                   of the audiobook list group.
        """
        # Retrieve the current session using the provided ID.
        session = self.context.get_session(id)
        
        # Update the 'audiobook' key in the session with the selected file path.
        session['audiobook'] = selected
        
        # If an audiobook is selected (not None), get its media information.
        if selected is not None:
            # Use mediainfo to get metadata from the audio file.
            audio_info = mediainfo(selected)
            # Store the duration of the audiobook in the session.
            try:
                session['duration'] = float(audio_info['duration'])
            except (ValueError, TypeError, KeyError):
                session['duration'] = 0.0
        
        # Determine if the audiobook list group should be visible.
        # It is visible only if there are audiobooks in the options list.
        visible = True if len(self.audiobook_options) else False
        
        # Return a series of Gradio updates to refresh the UI.
        return (
            gr.update(value=selected),  # Update the value of the download button.
            gr.update(value=selected),  # Update the audio player with the new source.
            gr.update(value=self.load_vtt_data(selected)),  # Load and update the VTT data.
            gr.update(visible=visible)  # Set the visibility of the audiobook list group.
        )
    
    def update_gr_glass_mask(self, str='Initialization, please wait...', attr=''):
        return gr.update(value=f'<div id="glass-mask" {attr}>{str}</div>')
    
    def state_convert_btn(self, upload_file=None, upload_file_mode=None, custom_model_file=None, session=None):
        try:
            if session is None:
                return gr.update(variant='primary', interactive=False)
            else:
                if hasattr(upload_file, 'name') and not hasattr(custom_model_file, 'name'):
                    return gr.update(variant='primary', interactive=True)
                elif isinstance(upload_file, list) and len(upload_file) > 0 and upload_file_mode == 'directory' and not hasattr(custom_model_file, 'name'):
                    return gr.update(variant='primary', interactive=True)
                else:
                    return gr.update(variant='primary', interactive=False)
        except Exception as e:
            error = f'state_convert_btn(): {e}'
            self.alert_exception(error)
    
    def disable_components(self):
        outputs = tuple([gr.update(interactive=False) for _ in range(9)])
        return outputs
    
    def enable_components(self):
        outputs = tuple([gr.update(interactive=True) for _ in range(9)])
        return outputs

    def change_gr_ebook_file(self, data, id):
        try:
            session = self.context.get_session(id)
            session['ebook'] = None
            session['ebook_list'] = None
            if data is None:
                if session['status'] == 'converting':
                    session['cancellation_requested'] = True
                    msg = 'Cancellation requested, please wait...'
                    yield gr.update(value=self.show_modal('wait', msg),visible=True)
                    return
            if isinstance(data, list):
                session['ebook_list'] = data
            else:
                session['ebook'] = data
            session['cancellation_requested'] = False
        except Exception as e:
            error = f'change_gr_ebook_file(): {e}'
            self.alert_exception(error)
        return gr.update(visible=False)
        
    def change_gr_ebook_mode(self, val, id):
        session = self.context.get_session(id)
        session['ebook_mode'] = val
        if val == 'single':
            return gr.update(label=self.src_label_file, value=None, file_count='single')
        else:
            return gr.update(label=self.src_label_dir, value=None, file_count='directory')

    def change_gr_voice_file(self, f, id):
        if f is not None:
            state = {}
            if len(self.voice_options) > max_custom_voices:
                error = f'You are allowed to upload a max of {max_custom_voices} voices'
                state['type'] = 'warning'
                state['msg'] = error
            elif os.path.splitext(f.name)[1] not in voice_formats:
                error = f'The audio file format selected is not valid.'
                state['type'] = 'warning'
                state['msg'] = error
            else:                  
                session = self.context.get_session(id)
                voice_name = os.path.splitext(os.path.basename(f))[0].replace('&', 'And')
                eaudio = EbookAudio()
                voice_name = eaudio.get_sanitized(voice_name)
                final_voice_file = os.path.join(session['voice_dir'], f'{voice_name}.wav')
                extractor = VoiceExtractor(session, f, voice_name)
                status, msg = extractor.extract_voice()
                if status:
                    session['voice'] = final_voice_file
                    msg = f"Voice {voice_name} added to the voices list"
                    state['type'] = 'success'
                    state['msg'] = msg
                else:
                    error = 'failed! Check if you audio file is compatible.'
                    state['type'] = 'warning'
                    state['msg'] = error
            show_alert(state)
            return gr.update(value=None)
        return gr.update()

    def change_gr_voice_list(self, selected, id):
        session = self.context.get_session(id)
        session['voice'] = next((value for label, value in self.voice_options if value == selected), None)
        visible = True if session['voice'] is not None else False
        min_width = 60 if session['voice'] is not None else 0
        return gr.update(value=session['voice'], visible=visible, min_width=min_width), gr.update(visible=visible)

    def click_gr_voice_del_btn(self, selected, id):
        try:
            if selected is not None:
                session = self.context.get_session(id)
                speaker_path = os.path.abspath(selected)
                speaker = re.sub(r'\.wav$|\.npz$', '', os.path.basename(selected))
                builtin_root = os.path.join(voices_dir, session['language'])
                sessions_root = os.path.join(voices_dir, '__sessions')
                is_in_sessions = os.path.commonpath([speaker_path, os.path.abspath(sessions_root)]) == os.path.abspath(sessions_root)
                is_in_builtin = os.path.commonpath([speaker_path, os.path.abspath(builtin_root)]) == os.path.abspath(builtin_root)
                # Check if voice is built-in
                is_builtin = any(
                    speaker in settings.get('voices', {})
                    for settings in (default_engine_settings[engine] for engine in TTS_ENGINES.values())
                )
                if is_builtin and is_in_builtin:
                    error = f'Voice file {speaker} is a builtin voice and cannot be deleted.'
                    show_alert({"type": "warning", "msg": error})
                    return gr.update(), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)
                try:
                    selected_path = Path(selected).resolve()
                    parent_path = Path(session['voice_dir']).parent.resolve()
                    if parent_path in selected_path.parents:
                        msg = f'Are you sure to delete {speaker}...'
                        return (
                            gr.update(value='confirm_voice_del'),
                            gr.update(value=self.show_modal('confirm', msg), visible=True),
                            gr.update(visible=True),
                            gr.update(visible=True)
                        )
                    else:
                        error = f'{speaker} is part of the global voices directory. Only your own custom uploaded voices can be deleted!'
                        show_alert({"type": "warning", "msg": error})
                        return gr.update(), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)
                except Exception as e:
                    error = f'Could not delete the voice file {selected}!\n{e}'
                    self.alert_exception(error)
                    return gr.update(), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)
            # Fallback/default return if not selected or after errors
            return gr.update(), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)
        except Exception as e:
            error = f'click_gr_voice_del_btn(): {e}'
            self.alert_exception(error)
            return gr.update(), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)

    def click_gr_custom_model_del_btn(self, selected, id):
        try:
            if selected is not None:
                session = self.context.get_session(id)
                selected_name = os.path.basename(selected)
                msg = f'Are you sure to delete {selected_name}...'
                return gr.update(value='confirm_custom_model_del'), gr.update(value=self.show_modal('confirm', msg),visible=True), gr.update(visible=True), gr.update(visible=True)
        except Exception as e:
            error = f'Could not delete the custom model {selected_name}!'
            self.alert_exception(error)
        return gr.update(), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)

    def click_gr_audiobook_del_btn(self, selected, id):
        try:
            if selected is not None:
                session = self.context.get_session(id)
                selected_name = Path(selected).stem
                msg = f'Are you sure to delete {selected_name}...'
                return gr.update(value='confirm_audiobook_del'), gr.update(value=self.show_modal('confirm', msg),visible=True), gr.update(visible=True), gr.update(visible=True)
        except Exception as e:
            error = f'Could not delete the audiobook {selected_name}!'
            self.alert_exception(error)
        return gr.update(), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False)

    def confirm_deletion(self, voice_path, custom_model, audiobook, id, method=None):
        try:
            if method is not None:
                session = self.context.get_session(id)
                if method == 'confirm_voice_del':
                    selected_name = Path(voice_path).stem
                    pattern = re.sub(r'\.wav$', '*.wav', voice_path)
                    files2remove = glob(pattern)
                    for file in files2remove:
                        os.remove(file)
                    shutil.rmtree(os.path.join(os.path.dirname(voice_path), 'bark', selected_name), ignore_errors=True)
                    msg = f"Voice file {re.sub(r'.wav$', '', selected_name)} deleted!"
                    session['voice'] = None
                    show_alert({"type": "warning", "msg": msg})
                    return gr.update(), gr.update(), gr.update(visible=False), self.update_gr_voice_list(id), gr.update(visible=False), gr.update(visible=False)
                elif method == 'confirm_custom_model_del':
                    selected_name = os.path.basename(custom_model)
                    shutil.rmtree(custom_model, ignore_errors=True)                           
                    msg = f'Custom model {selected_name} deleted!'
                    session['custom_model'] = None
                    show_alert({"type": "warning", "msg": msg})
                    return self.update_gr_custom_model_list(id), gr.update(), gr.update(visible=False), gr.update(), gr.update(visible=False), gr.update(visible=False)
                elif method == 'confirm_audiobook_del':
                    selected_name = Path(audiobook).stem
                    if os.path.isdir(audiobook):
                        shutil.rmtree(audiobook, ignore_errors=True)
                    elif os.path.exists(audiobook):
                        os.remove(audiobook)
                    vtt_path = Path(audiobook).with_suffix('.vtt')
                    if os.path.exists(vtt_path):
                        os.remove(vtt_path)
                    msg = f'Audiobook {selected_name} deleted!'
                    session['audiobook'] = None
                    show_alert({"type": "warning", "msg": msg})
                    return gr.update(), self.update_gr_audiobook_list(id), gr.update(visible=False), gr.update(), gr.update(visible=False), gr.update(visible=False)
            return gr.update(), gr.update(), gr.update(visible=False), gr.update(), gr.update(visible=False), gr.update(visible=False)
        except Exception as e:
            error = f'confirm_deletion(): {e}!'
            self.alert_exception(error)
        return gr.update(), gr.update(), gr.update(visible=False), gr.update(), gr.update(visible=False), gr.update(visible=False)
            
    def prepare_audiobook_download(self, selected):
        if os.path.exists(selected):
            return selected
        return None           

    def update_gr_voice_list(self, id):
        try:
            session = self.context.get_session(id)
            lang_dir = session['language'] if session['language'] != 'con' else 'con-'  # Bypass Windows CON reserved name
            file_pattern = "*.wav"
            eng_options = []
            bark_options = []
            builtin_options = [
                (os.path.splitext(f.name)[0], str(f))
                for f in Path(os.path.join(voices_dir, lang_dir)).rglob(file_pattern)
            ]
            if session['language'] in language_tts[TTS_ENGINES['XTTSv2']]:
                builtin_names = {t[0]: None for t in builtin_options}
                eng_dir = Path(os.path.join(voices_dir, "eng"))
                eng_options = [
                    (base, str(f))
                    for f in eng_dir.rglob(file_pattern)
                    for base in [os.path.splitext(f.name)[0]]
                    if base not in builtin_names
                ]
            if session['tts_engine'] == TTS_ENGINES['BARK']:
                lang_array = languages.get(part3=session['language'])
                if lang_array:
                    lang_iso1 = lang_array.part1 
                    lang = lang_iso1.lower()
                    speakers_path = Path(default_engine_settings[TTS_ENGINES['BARK']]['speakers_path'])
                    pattern_speaker = re.compile(r"^.*?_speaker_(\d+)$")
                    bark_options = [
                        (pattern_speaker.sub(r"Speaker \1", f.stem), str(f.with_suffix(".wav")))
                        for f in speakers_path.rglob(f"{lang}_speaker_*.npz")
                    ]
            self.voice_options = builtin_options + eng_options + bark_options
            session['voice_dir'] = os.path.join(voices_dir, '__sessions', f"voice-{session['id']}", session['language'])
            os.makedirs(session['voice_dir'], exist_ok=True)
            if session['voice_dir'] is not None:
                parent_dir = Path(session['voice_dir']).parent
                self.voice_options += [
                    (os.path.splitext(f.name)[0], str(f))
                    for f in parent_dir.rglob(file_pattern)
                    if f.is_file()
                ]
            if session['tts_engine'] in [TTS_ENGINES['VITS'], TTS_ENGINES['FAIRSEQ'], TTS_ENGINES['TACOTRON2'], TTS_ENGINES['YOURTTS']]:
                voice_options = [('Default', None)] + sorted(self.voice_options, key=lambda x: x[0].lower())
            else:
                self.voice_options = sorted(self.voice_options, key=lambda x: x[0].lower())
            default_voice_path = models[session['tts_engine']][session['fine_tuned']]['voice']
            if session['voice'] is None:
                if self.voice_options[0][1] is not None:
                    default_name = Path(default_voice_path).stem
                    for name, value in self.voice_options:
                        if name == default_name:
                            session['voice'] = value
                            break
                    else:
                        values = [v for _, v in self.voice_options]
                        if default_voice_path in values:
                            session['voice'] = default_voice_path
                        else:
                            session['voice'] = self.voice_options[0][1]
            else:
                current_voice_name = Path(session['voice']).stem
                current_voice_path = next(
                    (path for name, path in self.voice_options if name == current_voice_name and path == session['voice']), False
                )
                if current_voice_path:
                    session['voice'] = current_voice_path
                else:
                    session['voice'] = default_voice_path
            return gr.update(choices=self.voice_options, value=session['voice'])
        except Exception as e:
            error = f'update_gr_voice_list(): {e}!'
            self.alert_exception(error)
            return gr.update()

    def update_gr_tts_engine_list(self, id):
        try:
            session = self.context.get_session(id)
            self.tts_engine_options = get_compatible_tts_engines(session['language'])
            session['tts_engine'] = session['tts_engine'] if session['tts_engine'] in self.tts_engine_options else self.tts_engine_options[0]
            return gr.update(choices=self.tts_engine_options, value=session['tts_engine'])
        except Exception as e:
            error = f'update_gr_tts_engine_list(): {e}!'
            self.alert_exception(error)              
            return gr.update()

    def update_gr_custom_model_list(self, id):
        try:
            session = self.context.get_session(id)
            custom_model_tts_dir = self.check_custom_model_tts(session['custom_model_dir'], session['tts_engine'])
            self.custom_model_options = [('None', None)] + [
                (
                    str(dir),
                    os.path.join(custom_model_tts_dir, dir)
                )
                for dir in os.listdir(custom_model_tts_dir)
                if os.path.isdir(os.path.join(custom_model_tts_dir, dir))
            ]
            session['custom_model'] = session['custom_model'] if session['custom_model'] in [option[1] for option in self.custom_model_options] else self.custom_model_options[0][1]
            return gr.update(choices=self.custom_model_options, value=session['custom_model'])
        except Exception as e:
            error = f'update_gr_custom_model_list(): {e}!'
            self.alert_exception(error)
            return gr.update()

    def update_gr_fine_tuned_list(self, id):
        try:
            session = self.context.get_session(id)
            self.fine_tuned_options = [
                name for name, details in models.get(session['tts_engine'],{}).items()
                if details.get('lang') == 'multi' or details.get('lang') == session['language']
            ]
            session['fine_tuned'] = session['fine_tuned'] if session['fine_tuned'] in self.fine_tuned_options else default_fine_tuned
            return gr.update(choices=self.fine_tuned_options, value=session['fine_tuned'])
        except Exception as e:
            error = f'update_gr_fine_tuned_list(): {e}!'
            self.alert_exception(error)              
            return gr.update()

    def change_gr_device(self, device, id):
        session = self.context.get_session(id)
        session['device'] = device

    def change_gr_language(self, selected, id):
        if selected:
            session = self.context.get_session(id)
            prev = session['language']      
            session['language'] = selected
            return[
                gr.update(value=session['language']),
                self.update_gr_tts_engine_list(id),
                self.update_gr_custom_model_list(id),
                self.update_gr_fine_tuned_list(id)
            ]
        return (gr.update(), gr.update(), gr.update(), gr.update())

    def check_custom_model_tts(self, custom_model_dir, tts_engine):
        dir_path = None
        if custom_model_dir is not None and tts_engine is not None:
            dir_path = os.path.join(custom_model_dir, tts_engine)
            if not os.path.isdir(dir_path):
                os.makedirs(dir_path, exist_ok=True)
        return dir_path

    def change_gr_custom_model_file(self, f, t, id):
        if f is not None:
            state = {}
            try:
                if len(self.custom_model_options) > max_custom_model:
                    error = f'You are allowed to upload a max of {max_custom_model} models'   
                    state['type'] = 'warning'
                    state['msg'] = error
                else:
                    session = self.context.get_session(id)
                    session['tts_engine'] = t
                    required_files = models[session['tts_engine']]['internal']['files']
                    if analyze_uploaded_file(f, required_files):
                        model = self.ebook_audio.extract_custom_model(f, session)
                        if model is None:
                            error = f'Cannot extract custom model zip file {os.path.basename(f)}'
                            state['type'] = 'warning'
                            state['msg'] = error
                        else:
                            session['custom_model'] = model
                            msg = f'{os.path.basename(model)} added to the custom models list'
                            state['type'] = 'success'
                            state['msg'] = msg
                    else:
                        error = f'{os.path.basename(f)} is not a valid model or some required files are missing'
                        state['type'] = 'warning'
                        state['msg'] = error
            except ClientDisconnect:
                error = 'Client disconnected during upload. Operation aborted.'
                state['type'] = 'error'
                state['msg'] = error
            except Exception as e:
                error = f'change_gr_custom_model_file() exception: {str(e)}'
                state['type'] = 'error'
                state['msg'] = error
            show_alert(state)
            return gr.update(value=None)
        return gr.update()

    def change_gr_tts_engine_list(self, engine, id):
        session = self.context.get_session(id)
        session['tts_engine'] = engine
        default_voice_path = models[session['tts_engine']][session['fine_tuned']]['voice']
        if default_voice_path is None:
            session['voice'] = default_voice_path
        xtts_visible = False
        bark_visible = False
        voxcpm_visible = False
        if session['tts_engine'] == TTS_ENGINES['XTTSv2']:
            xtts_visible = True
            visible_custom_model = True
            if session['fine_tuned'] != 'internal':
                visible_custom_model = False
            return (
                   gr.update(value=self.show_rating(session['tts_engine'])), 
                   gr.update(visible=xtts_visible), gr.update(visible=bark_visible), gr.update(visible=voxcpm_visible),
                   gr.update(visible=visible_custom_model), self.update_gr_fine_tuned_list(id),
                   gr.update(label=f"*Upload {session['tts_engine']} Model (Should be a ZIP file with {', '.join(models[session['tts_engine']][default_fine_tuned]['files'])})"),
                   gr.update(label=f"My {session['tts_engine']} custom models")
            )
        else:
            if session['tts_engine'] == TTS_ENGINES['BARK']:
                bark_visible = True
            elif session['tts_engine'] == TTS_ENGINES['VOXCPM']:
                voxcpm_visible = True
            return (
                    gr.update(value=self.show_rating(session['tts_engine'])), gr.update(visible=xtts_visible), gr.update(visible=bark_visible),
                    gr.update(visible=voxcpm_visible),
                    gr.update(visible=False), self.update_gr_fine_tuned_list(id), gr.update(label=f"*Upload Fine Tuned Model not available for {session['tts_engine']}"), gr.update(label='')
            )
            
    def change_gr_fine_tuned_list(self, selected, id):
        if selected:
            session = self.context.get_session(id)
            visible = False
            if session['tts_engine'] == TTS_ENGINES['XTTSv2']:
                if selected == 'internal':
                    visible = self.visible_gr_group_custom_model
            session['fine_tuned'] = selected
            return gr.update(visible=visible)
        return gr.update()

    def change_gr_custom_model_list(self, selected, id):
        session = self.context.get_session(id)
        session['custom_model'] = next((value for label, value in self.custom_model_options if value == selected), None)
        visible = True if session['custom_model'] is not None else False
        return gr.update(visible=not visible), gr.update(visible=visible)
    
    def change_gr_output_format_list(self, val, id):
        session = self.context.get_session(id)
        session['output_format'] = val
        return
        
    def change_gr_output_split(self, bool, id):
        session = self.context.get_session(id)
        session['output_split'] = bool
        return gr.update(visible=bool)

    def change_gr_output_split_hours(self, selected, id):
        session = self.context.get_session(id)
        session['output_split_minutes'] = selected
        return

    def change_gr_audiobook_player_playback_time(self, str, id):
        session = self.context.get_session(id)
        session['playback_time'] = float(str)
        return

    def change_param(self, key, val, id, val2=None):
        session = self.context.get_session(id)
        session[key] = val
        state = {}
        if key == 'length_penalty':
            if val2 is not None:
                if float(val) > float(val2):
                    error = 'Length penalty must be always lower than num beams if greater than 1.0 or equal if 1.0'   
                    state['type'] = 'warning'
                    state['msg'] = error
                    show_alert(state)
        elif key == 'num_beams':
            if val2 is not None:
                if float(val) < float(val2):
                    error = 'Num beams must be always higher than length penalty or equal if its value is 1.0'   
                    state['type'] = 'warning'
                    state['msg'] = error
                    show_alert(state)
        return

    def submit_convert_btn(
            self, id, device, ebook_file, tts_engine, language, voice, custom_model, fine_tuned, output_format, temperature, 
            length_penalty, num_beams, repetition_penalty, top_k, top_p, speed, enable_text_splitting, text_temp, waveform_temp,
            cfg_value, inference_timesteps, normalize, denoise, retry_badcase, retry_badcase_max_times, retry_badcase_ratio_threshold,
            prompt_text,
            output_split, output_split_minutes
        ):
        try:
            session = self.context.get_session(id)
            args = {
                "is_gui_process": self.is_gui_process,
                "session": id,
                "offline_mode": self.offline_mode,
                "script_mode": self.script_mode,
                "device": device.lower(),
                "tts_engine": tts_engine,
                "ebook": ebook_file if isinstance(ebook_file, str) else None,
                "ebook_list": ebook_file if isinstance(ebook_file, list) else None,
                "audiobooks_dir": session['audiobooks_dir'],
                "voice": voice,
                "language": language,
                "custom_model": custom_model,
                "fine_tuned": fine_tuned,
                "output_format": output_format,
                "temperature": float(temperature),
                "length_penalty": float(length_penalty),
                "num_beams": session['num_beams'],
                "repetition_penalty": float(repetition_penalty),
                "top_k": int(top_k),
                "top_p": float(top_p),
                "speed": float(speed),
                "enable_text_splitting": enable_text_splitting,
                "text_temp": float(text_temp),
                "waveform_temp": float(waveform_temp),
                "cfg_value": float(cfg_value),
                "inference_timesteps": int(inference_timesteps),
                "normalize": normalize,
                "denoise": denoise,
                "retry_badcase": retry_badcase,
                "retry_badcase_max_times": int(retry_badcase_max_times),
                "retry_badcase_ratio_threshold": float(retry_badcase_ratio_threshold),
                "prompt_text": prompt_text,
                "output_split": output_split,
                "output_split_minutes": output_split_minutes
            }
            error = None
            if args['ebook'] is None and args['ebook_list'] is None:
                error = 'Error: a file or directory is required.'
                show_alert({"type": "warning", "msg": error})
            elif args['num_beams'] < args['length_penalty']:
                error = 'Error: num beams must be greater or equal than length penalty.'
                show_alert({"type": "warning", "msg": error})                   
            else:
                session['status'] = 'converting'
                session['progress'] = len(self.audiobook_options)
                if isinstance(args['ebook_list'], list):
                    ebook_list = args['ebook_list'][:]
                    for file in ebook_list:
                        if any(file.endswith(ext) for ext in ebook_formats):
                            print(f'Processing eBook file: {os.path.basename(file)}')
                            args['ebook'] = file
                            ebook_processor = EBookProcessor()
                            progress_status, passed = ebook_processor.convert_ebook(args)
                            if passed is False:
                                if session['status'] == 'converting':
                                    error = 'Conversion cancelled.'
                                    break
                                else:
                                    error = 'Conversion failed.'
                                    break
                            else:
                                show_alert({"type": "success", "msg": progress_status})
                                args['ebook_list'].remove(file)
                                reset_ebook_session(args['session'])
                                count_file = len(args['ebook_list'])
                                if count_file > 0:
                                    msg = f"{len(args['ebook_list'])} remaining..."
                                else: 
                                    msg = 'Conversion successful!'
                                yield gr.update(value=msg)
                    session['status'] = 'ready'
                else:
                    print(f"Processing eBook file: {os.path.basename(args['ebook'])}")
                    ebook_processor = EBookProcessor()
                    progress_status, passed = ebook_processor.convert_ebook(args, self.context)
                    if passed is False:
                        if session['status'] == 'converting':
                            error = 'Conversion cancelled.'
                        else:
                            error = 'Conversion failed.'
                        session['status'] = 'ready'
                    else:
                        show_alert({"type": "success", "msg": progress_status})
                        reset_ebook_session(self.context, args['session'])
                        msg = 'Conversion successful!'
                        return gr.update(value=msg)
            if error is not None:
                show_alert({"type": "warning", "msg": error})
        except Exception as e:
            error = f'submit_convert_btn(): {e}'
            self.alert_exception(error)
        return gr.update(value='')

    def update_gr_audiobook_list(self, id):
        try:
            session = self.context.get_session(id)
            self.audiobook_options = [
                (f, os.path.join(session['audiobooks_dir'], str(f)))
                for f in os.listdir(session['audiobooks_dir'])
                if not f.lower().endswith(".vtt")  # exclude VTT files
            ]
            self.audiobook_options.sort(
                key=lambda x: os.path.getmtime(x[1]),
                reverse=True
            )
            session['audiobook'] = (
                session['audiobook']
                if session['audiobook'] in [option[1] for option in self.audiobook_options]
                else None
            )
            if len(self.audiobook_options) > 0:
                if session['audiobook'] is not None:
                    return gr.update(choices=self.audiobook_options, value=session['audiobook'])
                else:
                    return gr.update(choices=self.audiobook_options, value=self.audiobook_options[0][1])
            return gr.update(choices=self.audiobook_options)
        except Exception as e:
            error = f'update_gr_audiobook_list(): {e}!'
            self.alert_exception(error)              
            return gr.update()

    def change_gr_read_data(self, data, state, req: gr.Request):
        try:
            # This function is the entry point for creating and managing user sessions.
            # It's triggered when the frontend loads and sends back any session data stored in the browser's localStorage.

            msg = 'Error while loading saved session. Please try to delete your cookies and refresh the page'
            
            # Step 1: Check for existing session data.
            if data is None or 'id' not in data:
                # If no session data or session ID is found, create a new session.
                # A unique session ID is generated using UUID.
                session = self.context.get_session(str(uuid.uuid4()))
                if data is not None:
                    # If there's some data but no ID, try to restore from it.
                    restore_session_from_data(data, session)
                data = session
            else:
                # If a session ID is found, retrieve the existing session from the context.
                session = self.context.get_session(data['id'])

            # Restore session data from the provided data object.
            if data.get('tab_id') == session.get('tab_id') or len(active_sessions) == 0:
                restore_session_from_data(data, session)
                session['status'] = None

            # Step 2: Start tracking the session to manage its lifecycle.
            if not ctx_tracker.start_session(session['id'], self.context):
                # If the session is already active elsewhere, show an error.
                error = "Your session is already active.<br>If it's not the case please close your browser and relaunch it."
                return gr.update(), gr.update(), gr.update(value=''), self.update_gr_glass_mask(str=error)
            else:
                # If the session is new or inactive, add it to the active sessions set.
                active_sessions.add(req.session_hash)
                session[req.session_hash] = req.session_hash
                session['cancellation_requested'] = False
            if isinstance(session['ebook'], str):
                if not os.path.exists(session['ebook']):
                    session['ebook'] = None
            if session['voice'] is not None:
                if not os.path.exists(session['voice']):
                    session['voice'] = None
            if session['custom_model'] is not None:
                if not os.path.exists(session['custom_model_dir']):
                    session['custom_model'] = None 
            if session['fine_tuned'] is not None:
                if session['tts_engine'] is not None:
                    if session['tts_engine'] in models.keys():
                        if session['fine_tuned'] not in models[session['tts_engine']].keys():
                            session['fine_tuned'] = default_fine_tuned
                    else:
                        session['tts_engine'] = default_tts_engine
                        session['fine_tuned'] = default_fine_tuned
            if session['audiobook'] is not None:
                if not os.path.exists(session['audiobook']):
                    session['audiobook'] = None
            if session['status'] == 'converting':
                session['status'] = 'ready'
            session['system'] = (f"{platform.system()}-{platform.release()}").lower()
            session['custom_model_dir'] = os.path.join(models_dir, '__sessions', f"model-{session['id']}")
            session['voice_dir'] = os.path.join(voices_dir, '__sessions', f"voice-{session['id']}", session['language'])
            os.makedirs(session['custom_model_dir'], exist_ok=True)
            os.makedirs(session['voice_dir'], exist_ok=True)
            # As now uploaded voice files are in their respective language folder so check if no wav and bark folder are on the voice_dir root from previous versions
            [shutil.move(src, os.path.join(session['voice_dir'], os.path.basename(src))) for src in glob(os.path.join(os.path.dirname(session['voice_dir']), '*.wav')) + ([os.path.join(os.path.dirname(session['voice_dir']), 'bark')] if os.path.isdir(os.path.join(os.path.dirname(session['voice_dir']), 'bark')) and not os.path.exists(os.path.join(session['voice_dir'], 'bark')) else [])]                
            if self.is_gui_shared:
                msg = f' Note: access limit time: {interface_shared_tmp_expire} days'
                session['audiobooks_dir'] = os.path.join(audiobooks_gradio_dir, f"web-{session['id']}")
                delete_unused_tmp_dirs(audiobooks_gradio_dir, interface_shared_tmp_expire, session)
            else:
                msg = f' Note: if no activity is detected after {tmp_expire} days, your session will be cleaned up.'
                session['audiobooks_dir'] = os.path.join(audiobooks_host_dir, f"web-{session['id']}")
                delete_unused_tmp_dirs(audiobooks_host_dir, tmp_expire, session)
            if not os.path.exists(session['audiobooks_dir']):
                os.makedirs(session['audiobooks_dir'], exist_ok=True)
            previous_hash = state['hash']
            new_hash = hash_proxy_dict(MappingProxyType(dict(session)))
            state['hash'] = new_hash
            session_dict = proxy2dict(session)
            show_alert({"type": "info", "msg": msg})
            return gr.update(value=session_dict), gr.update(value=state), gr.update(value=session['id']), gr.update()
        except Exception as e:
            error = f'change_gr_read_data(): {e}'
            self.alert_exception(error)
            return gr.update(), gr.update(), gr.update(), gr.update()

    def save_session(self, id, state):
        try:
            if id:
                if id in self.context.sessions:
                    session = self.context.get_session(id)
                    if session:
                        if session['event'] == 'clear':
                            session_dict = session
                        else:
                            previous_hash = state['hash']
                            new_hash = hash_proxy_dict(MappingProxyType(dict(session)))
                            if previous_hash == new_hash:
                                return gr.update(), gr.update(), gr.update()
                            else:
                                state['hash'] = new_hash
                                session_dict = proxy2dict(session)
                        if session['status'] == 'converting':
                            if session['progress'] != len(self.audiobook_options):
                                session['progress'] = len(self.audiobook_options)
                                return gr.update(value=json.dumps(session_dict, indent=4)), gr.update(value=state), self.update_gr_audiobook_list(id)
                        return gr.update(value=json.dumps(session_dict, indent=4)), gr.update(value=state), gr.update()
            return gr.update(), gr.update(), gr.update()
        except Exception as e:
            error = f'save_session(): {e}!'
            self.alert_exception(error)              
            return gr.update(), gr.update(value=e), gr.update()
    
    def clear_event(self, id):
        if id:
            session = self.context.get_session(id)
            if session['event'] is not None:
                session['event'] = None
