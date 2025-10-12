import os

from lib.models import TTS_ENGINES

class TTSManager:
    def __init__(self, session):   
        self.session = session
        self.tts = None
        self._build()
 
    def _build(self):
        if self.session['tts_engine'] in TTS_ENGINES.values():
            if self.session['tts_engine'] in [TTS_ENGINES['XTTSv2'], TTS_ENGINES['BARK'], TTS_ENGINES['VITS'], TTS_ENGINES['FAIRSEQ'], TTS_ENGINES['TACOTRON2'], TTS_ENGINES['YOURTTS']]:
                from lib.classes.tts_engines.coqui import Coqui
                self.tts = Coqui(self.session)
            elif self.session['tts_engine'] == TTS_ENGINES['VOXCPM']:
                from lib.classes.tts_voxcpm import TTSVoxCPM
                self.tts = TTSVoxCPM(self.session)
            #elif self.session['tts_engine'] in [TTS_ENGINES['NEW_TTS']]:
            #    from lib.classes.tts_engines.new_tts import NewTts
            #    self.tts = NewTts(self.session)
            if self.tts:
                return True
            else:
                error = 'TTS engine could not be created!'
                print(error)
        else:
            print('Other TTS engines coming soon!')
        return False

    def convert_sentence2audio(self, sentence_number, sentence):
        try:
            if self.session['tts_engine'] in TTS_ENGINES.values():
                if self.session['tts_engine'] == TTS_ENGINES['VOXCPM']:
                    # Assuming you have a way to get the prompt_wav_path and prompt_text
                    prompt_wav_path = self.session.get('voice')
                    prompt_text = "无论是互联网巨头还是刚起步的创业公司都在竞相努力成为元宇宙这条充满无限可能性赛道的领先者事实确实这些平台除了产品发布发新闻稿时热度高很快就回归平静就像horizon world一样"  # You might want to make this configurable
                    return self.tts.generate_audio(sentence, prompt_wav_path, prompt_text)
                else:
                    return self.tts.convert(sentence_number, sentence)
            else:
                print('Other TTS engines coming soon!')    
        except Exception as e:
            error = f'convert_sentence2audio(): {e}'
            raise ValueError(e)
        return False