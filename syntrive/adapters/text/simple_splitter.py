"""
将小说章节分割成适合 TTS 的句子
"""

import re

class SimpleNovelTextSplitter:
    def __init__(self, min_length=40, max_length=60):
        self.min_length = min_length
        self.max_length = max_length
        # HanLP 分句器
        # self.segment = HanLP.newSegment()
    
    def split_sentences(self, text):
        """使用 HanLP 分句"""
        # 预处理
        text = re.sub(r'\n+', '\n', text)
        # text = re.sub(r'[ \t]+', '', text)
        
        # HanLP 分句
        sentences = []
        paragraphs = text.split('\n')
        
        for para in paragraphs:
            if not para.strip():
                continue
            
            # 使用正则表达式在标点处分句
            # 这是简化版，HanLP 的完整分句功能需要 Java 支持
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
    
    def merge_sentences(self, sentences):
        """
        将短句合并成适合 TTS 的长度
        """
        result = []
        current_chunk = ""
        
        for sentence in sentences:
            if not sentence:
                continue
            
            # 如果是对话，检查是否需要保持独立
            is_dialogue = '"' in sentence or '"' in sentence or '「' in sentence
            
            # 空块，直接添加
            if not current_chunk:
                current_chunk = sentence
            # 合并后不超长
            elif len(current_chunk) + len(sentence) <= self.max_length:
                # 对话通常独立成句
                if is_dialogue and len(current_chunk) >= self.min_length:
                    result.append(current_chunk)
                    current_chunk = sentence
                else:
                    current_chunk += sentence
            else:
                # 当前块保存
                if len(current_chunk) >= self.min_length:
                    result.append(current_chunk)
                    current_chunk = sentence
                else:
                    # 块太短，继续合并但可能超长
                    if len(current_chunk) + len(sentence) <= self.max_length + 10:
                        current_chunk += sentence
                    else:
                        result.append(current_chunk)
                        current_chunk = sentence
        
        # 处理最后一块
        if current_chunk:
            if len(current_chunk) < self.min_length and result:
                last = result.pop()
                if len(last) + len(current_chunk) <= self.max_length + 10:
                    result.append(last + current_chunk)
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
        sentences = self.split_sentences(text)
        chunks = self.merge_sentences(sentences)
        
        # 后处理：分割过长的句子
        final_chunks = []
        for chunk in chunks:
            if len(chunk) > self.max_length:
                # 在逗号处分割
                parts = self._smart_split(chunk)
                final_chunks.extend(parts)
            else:
                final_chunks.append(chunk)
        
        return final_chunks
    
    def _smart_split(self, text):
        """在合适位置分割长文本"""
        if len(text) <= self.max_length:
            return [text]
        
        result = []
        split_chars = ['，', '、', '；', '：']
        
        current = ""
        for char in text:
            current += char
            
            if char in split_chars and len(current) >= self.min_length:
                if len(current) <= self.max_length:
                    result.append(current)
                    current = ""
        
        if current:
            # 最后一段太短，尝试合并
            if len(current) < self.min_length and result:
                result[-1] += current
            else:
                result.append(current)
        
        return result


# 示例使用
if __name__ == "__main__":
    sample_text = """
    清晨的阳光洒在青山之上，山间云雾缭绕，宛如仙境。张三背着行囊，沿着蜿蜒的山路缓缓前行。
    "这便是传说中的青云山了。"他自言自语道，眼中充满了期待。
    走了约莫两个时辰，前方出现了一座古朴的山门。门前站着一位白衣少女，正在练剑。剑光如银蛇飞舞，招式精妙绝伦。
    "姑娘好剑法！"张三忍不住赞叹。
    少女收剑回鞘，转过身来，露出清秀的面容："多谢夸奖。你是来拜师的？"
    "正是。"张三拱手道，"在下张三，久闻青云派大名，特来求学。"
    少女微微一笑："我叫林婉儿，是青云派的外门弟子。想要入门，需要先通过考验。你可准备好了？"
    """
    
    print("=== 使用 PyHanLP 分割结果 ===\n")
    
    splitter = SimpleNovelTextSplitter(min_length=40, max_length=60)
    chunks = splitter.split_for_tts(sample_text)
    
    for i, chunk in enumerate(chunks, 1):
        print(f"[句子 {i}] (长度: {len(chunk)})")
        print(chunk)
        # print()
    
    print(f"总共分割成 {len(chunks)} 个句子")
    print("\n=== TTS 调用示例 ===")
    print("""
# 使用分割后的句子调用 TTS
for i, text in enumerate(chunks):
    # CosyVoice 示例
    audio = cosyvoice.inference_sft(text, speaker='中文女声')
    # 或 GPT-SoVITS 示例
    # audio = tts_model.get_audio(text, ref_audio_path='ref.wav')
    
    # 保存音频
    torchaudio.save(f'output_{i:03d}.wav', audio, sample_rate=22050)
    """)
