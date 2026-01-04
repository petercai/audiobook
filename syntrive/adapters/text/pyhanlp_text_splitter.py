"""
使用 PyHanLP 将小说章节分割成适合 TTS 的句子
安装: pip install pyhanlp
首次运行会自动下载 HanLP 数据包
"""

from pyhanlp import HanLP, JClass
import re

# 导入 HanLP 的分句器
NLPTokenizer = JClass('com.hankcs.hanlp.tokenizer.NLPTokenizer')
# 或者使用标准分句器
# StandardTokenizer = JClass('com.hankcs.hanlp.tokenizer.StandardTokenizer')

class HanLPNovelTextSplitter:
    def __init__(self, min_length=40, max_length=60):
        self.min_length = min_length
        self.max_length = max_length
        self.tokenizer = NLPTokenizer
    
    def split_sentences_with_hanlp(self, text):
        """
        真正使用 HanLP 的 NLPTokenizer 进行分句
        """
        # 预处理
        text = re.sub(r'\n+', '\n', text)
        # text = re.sub(r'[ \t]+', '', text)
        
        sentences = []
        paragraphs = text.split('\n')
        
        for para in paragraphs:
            if not para.strip():
                continue
            
            try:
                # 方法1: 使用 NLPTokenizer.segment() 进行分词
                # 然后通过标点符号重组成句子
                seg_result = self.tokenizer.segment(para)
                
                current_sentence = ""
                for term in seg_result:
                    word = str(term.word)
                    current_sentence += word
                    
                    # 检查是否是句子结束标点
                    if word in ['。', '！', '？', '；', '…']:
                        if current_sentence.strip():
                            sentences.append(current_sentence.strip())
                            current_sentence = ""
                
                # 添加剩余部分
                if current_sentence.strip():
                    sentences.append(current_sentence.strip())
                    
            except Exception as e:
                print(f"HanLP 处理出错: {e}, 使用备用方法")
                # 备用方法：使用正则分句
                parts = re.split(r'([。！？；])', para)
                temp = ""
                for i in range(0, len(parts), 2):
                    if i < len(parts):
                        s = parts[i]
                        if i + 1 < len(parts):
                            s += parts[i + 1]
                        if s.strip():
                            sentences.append(s.strip())
        
        return sentences
    
    def split_sentences_simple(self, text):
        """
        使用 HanLP 的简单分句方法
        直接使用 HanLP.segment() 然后按标点分组
        """
        text = re.sub(r'\n+', '\n', text)
        # text = re.sub(r'[ \t]+', '', text)
        
        sentences = []
        paragraphs = text.split('\n')
        
        for para in paragraphs:
            if not para.strip():
                continue
            
            # 使用 HanLP.segment 进行分词
            terms = HanLP.segment(para)
            
            current = ""
            for term in terms:
                word = str(term.word)
                current += word
                
                # 句子结束标记
                if word in ['。', '！', '？', ';', '；']:
                    if current.strip():
                        sentences.append(current.strip())
                        current = ""
            
            if current.strip():
                sentences.append(current.strip())
        
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
            
            # 识别对话
            is_dialogue = '"' in sentence or '"' in sentence or '「' in sentence
            
            if not current_chunk:
                current_chunk = sentence
            elif len(current_chunk) + len(sentence) <= self.max_length:
                # 对话通常独立
                if is_dialogue and len(current_chunk) >= self.min_length:
                    result.append(current_chunk)
                    current_chunk = sentence
                else:
                    current_chunk += sentence
            else:
                # 保存当前块
                if len(current_chunk) >= self.min_length:
                    result.append(current_chunk)
                    current_chunk = sentence
                else:
                    # 当前块太短，继续合并
                    if len(current_chunk) + len(sentence) <= self.max_length + 15:
                        current_chunk += sentence
                    else:
                        result.append(current_chunk)
                        current_chunk = sentence
        
        # 处理最后一块
        if current_chunk:
            if len(current_chunk) < self.min_length and result:
                last = result.pop()
                if len(last) + len(current_chunk) <= self.max_length + 15:
                    result.append(last + current_chunk)
                else:
                    result.append(last)
                    result.append(current_chunk)
            else:
                result.append(current_chunk)
        
        return result
    
    def split_for_tts(self, text, use_simple=False):
        """
        完整的分割流程
        use_simple: True 使用 HanLP.segment(), False 使用 NLPTokenizer
        """
        # 使用 HanLP 分句
        if use_simple:
            sentences = self.split_sentences_simple(text)
        else:
            sentences = self.split_sentences_with_hanlp(text)
        
        # print(f"HanLP 分句结果: {len(sentences)} 个原始句子")
        
        # 合并成适当长度
        chunks = self.merge_sentences(sentences)
        
        # 后处理：分割过长句子
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
        split_chars = ['，', '、', '；', '：']
        
        current = ""
        for char in text:
            current += char
            if char in split_chars and len(current) >= self.min_length:
                if len(current) <= self.max_length:
                    result.append(current)
                    current = ""
        
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
    走了约莫两个时辰，前方出现了一座古朴的山门。门前站着一位白衣少女，正在练剑。剑光如银蛇飞舞，招式精妙绝伦。
    "姑娘好剑法！"张三忍不住赞叹。
    少女收剑回鞘，转过身来，露出清秀的面容："多谢夸奖。你是来拜师的？"
    "正是。"张三拱手道，"在下张三，久闻青云派大名，特来求学。不知姑娘能否引荐？"
    少女微微一笑："我叫林婉儿，是青云派的外门弟子。想要入门，需要先通过考验。你可准备好了？"
    张三眼神坚定："无论什么考验，我都会全力以赴！"
    """
    
    print("=== 方法1: 使用 NLPTokenizer (推荐) ===\n")
    
    splitter = HanLPNovelTextSplitter(min_length=40, max_length=60)
    chunks = splitter.split_for_tts(sample_text, use_simple=False)
    
    for i, chunk in enumerate(chunks, 1):
        print(f"[句子 {i}] (长度: {len(chunk)}字)")
        print(chunk)
        print()
    
    print(f"总共分割成 {len(chunks)} 个TTS句子\n")
    
    print("="*50)
    print("\n=== 方法2: 使用 HanLP.segment() (简单) ===\n")
    
    chunks2 = splitter.split_for_tts(sample_text, use_simple=True)
    
    for i, chunk in enumerate(chunks2, 1):
        print(f"[句子 {i}] (长度: {len(chunk)}字)")
        print(chunk)
        print()
    
    print(f"总共分割成 {len(chunks2)} 个TTS句子")
    