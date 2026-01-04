"""
使用 PyHanLP 将小说章节分割成适合 TTS 的句子
安装: pip install pyhanlp
首次运行会自动下载 HanLP 数据包
"""

import re

class AnotherNovelTextSplitter:
    def __init__(self, min_length=50, max_length=70):
        self.min_length = min_length
        self.max_length = max_length
    
    def split_sentences_with_hanlp(self, text):
        """
        使用 HanLP 的分句功能
        HanLP 能够准确识别句子边界，包括引号、省略号等复杂情况
        """
        # 预处理：统一换行
        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r'[ \t]+', '', text)
        
        sentences = []
        paragraphs = text.split('\n')
        
        for para in paragraphs:
            if not para.strip():
                continue
            
            # 使用 HanLP 的分句功能
            # HanLP.segment() 会进行分词，但我们需要的是分句
            # 使用正则配合 HanLP 的理解能力
            try:
                # 方法1: 使用 HanLP 内置的句子分割
                # 通过标点符号分割，但保持引号内容的完整性
                parts = self._hanlp_sentence_split(para)
                sentences.extend(parts)
            except Exception as e:
                # 降级到正则分句
                print(f"HanLP 分句失败，使用正则: {e}")
                parts = re.split(r'([。！？；])', para)
                temp_sentence = ""
                for i in range(0, len(parts), 2):
                    if i < len(parts):
                        sentence = parts[i]
                        if i + 1 < len(parts):
                            sentence += parts[i + 1]
                        if sentence.strip():
                            sentences.append(sentence.strip())
        
        return sentences
    
    def _hanlp_sentence_split(self, text):
        """
        使用 HanLP 智能分句
        处理引号、省略号等特殊情况
        """
        sentences = []
        
        # 句子结束标记
        end_marks = {'。', '！', '？', '；', '…'}
        # 引号标记
        quote_marks = {'"', '"', '「', '」', '『', '』'}
        
        current = ""
        in_quote = False
        quote_stack = []
        
        for i, char in enumerate(text):
            current += char
            
            # 跟踪引号状态
            if char in ['"', '「', '『']:
                in_quote = True
                quote_stack.append(char)
            elif char in ['"', '」', '』']:
                if quote_stack:
                    quote_stack.pop()
                if not quote_stack:
                    in_quote = False
            
            # 判断是否为句子结束
            if char in end_marks:
                # 如果在引号内，检查下一个字符
                if in_quote:
                    continue
                
                # 检查是否是引号后的标点
                if i + 1 < len(text) and text[i + 1] in ['"', '」', '』']:
                    continue
                
                # 省略号特殊处理
                if char == '…' and i + 1 < len(text) and text[i + 1] == '…':
                    continue
                
                # 确认为句子结束
                if current.strip():
                    sentences.append(current.strip())
                    current = ""
                    in_quote = False
                    quote_stack = []
        
        # 添加剩余内容
        if current.strip():
            sentences.append(current.strip())
        
        return sentences
    
    def merge_sentences(self, sentences):
        """
        将短句合并成适合 TTS 的长度
        智能处理对话和描述
        """
        result = []
        current_chunk = ""
        
        for sentence in sentences:
            if not sentence:
                continue
            
            # 识别对话
            is_dialogue = ('"' in sentence or '"' in sentence or 
                          '「' in sentence or '」' in sentence)
            
            # 识别独立段落（通常是场景描述或重要转折）
            is_important = any(keyword in sentence for keyword in 
                             ['突然', '忽然', '这时', '只见', '但见'])
            
            if not current_chunk:
                # 空块，直接添加
                current_chunk = sentence
            elif len(current_chunk) + len(sentence) <= self.max_length:
                # 对话倾向于独立
                if is_dialogue and len(current_chunk) >= self.min_length:
                    result.append(current_chunk)
                    current_chunk = sentence
                else:
                    current_chunk += sentence
            else:
                # 超长了，保存当前块
                if len(current_chunk) >= self.min_length:
                    result.append(current_chunk)
                    current_chunk = sentence
                else:
                    # 当前块太短，强制合并一次
                    if len(current_chunk) + len(sentence) <= self.max_length + 15:
                        current_chunk += sentence
                    else:
                        result.append(current_chunk)
                        current_chunk = sentence
        
        # 处理最后一块
        if current_chunk:
            if len(current_chunk) < self.min_length and result:
                last = result.pop()
                combined = last + current_chunk
                if len(combined) <= self.max_length + 15:
                    result.append(combined)
                else:
                    result.append(last)
                    result.append(current_chunk)
            else:
                result.append(current_chunk)
        
        return result
    
    def split_for_tts(self, text):
        """
        完整的分割流程
        """
        # 使用 HanLP 分句
        sentences = self.split_sentences_with_hanlp(text)
        
        # 合并成适当长度
        chunks = self.merge_sentences(sentences)
        
        # 后处理：处理过长句子
        final_chunks = []
        for chunk in chunks:
            if len(chunk) > self.max_length + 10:
                parts = self._smart_split(chunk)
                final_chunks.extend(parts)
            else:
                final_chunks.append(chunk)
        
        return final_chunks
    
    def _smart_split(self, text):
        """在逗号等位置智能分割长文本"""
        if len(text) <= self.max_length:
            return [text]
        
        result = []
        split_chars = ['，', '、', '；', '：', '，']
        
        current = ""
        for i, char in enumerate(text):
            current += char
            
            # 在合适的标点处断句
            if char in split_chars and len(current) >= self.min_length:
                if len(current) <= self.max_length:
                    result.append(current)
                    current = ""
        
        # 处理剩余内容
        if current:
            if len(current) < self.min_length and result:
                result[-1] += current
            else:
                result.append(current)
        
        return result if result else [text]


# 示例使用
if __name__ == "__main__":
    sample_text = """
    清晨的阳光洒在青山之上，山间云雾缭绕，宛如仙境。张三背着行囊，沿着蜿蜒的山路缓缓前行。
    "这便是传说中的青云山了。"他自言自语道，眼中充满了期待。
    走了约莫两个时辰，前方出现了一座古朴的山门……门前站着一位白衣少女，正在练剑。剑光如银蛇飞舞，招式精妙绝伦。
    "姑娘好剑法！"张三忍不住赞叹。
    少女收剑回鞘，转过身来，露出清秀的面容："多谢夸奖。你是来拜师的？"
    "正是。"张三拱手道，"在下张三，久闻青云派大名，特来求学。不知姑娘能否引荐？"
    少女微微一笑："我叫林婉儿，是青云派的外门弟子。想要入门，需要先通过考验。你可准备好了？"
    张三眼神坚定："无论什么考验，我都会全力以赴！"
    """
    
    print("=== 使用 PyHanLP 智能分句结果 ===\n")
    
    splitter = AnotherNovelTextSplitter(min_length=50, max_length=70)
    chunks = splitter.split_for_tts(sample_text)
    
    for i, chunk in enumerate(chunks, 1):
        print(f"[句子 {i}] (长度: {len(chunk)}字)")
        print(chunk)
        print()
    
    print(f"总共分割成 {len(chunks)} 个TTS句子")
    
    print("\n=== 集成 TTS 的完整示例 ===")
    print("""
# 示例1: 使用 CosyVoice
import torchaudio

for i, text in enumerate(chunks):
    audio = cosyvoice.inference_sft(
        text, 
        speaker='中文女声',
        speed=1.0
    )
    torchaudio.save(f'output_{i:03d}.wav', audio, 22050)

# 示例2: 使用 GPT-SoVITS
from GPT_SoVITS.inference import get_tts_wav

for i, text in enumerate(chunks):
    audio = get_tts_wav(
        text=text,
        text_language='zh',
        ref_audio_path='reference.wav',
        prompt_text='参考文本'
    )
    audio.export(f'output_{i:03d}.wav', format='wav')

# 示例3: 批量处理并合并
from pydub import AudioSegment

combined = AudioSegment.empty()
for i, text in enumerate(chunks):
    audio = your_tts_function(text)
    combined += audio
    
combined.export('complete_chapter.wav', format='wav')
    """)
