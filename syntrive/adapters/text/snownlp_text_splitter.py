"""
使用 SnowNLP 将小说章节分割成适合 TTS 的句子
安装: pip install snownlp
"""

from snownlp import SnowNLP
import re

def split_novel_for_tts(text, min_length=50, max_length=70):
    """
    将小说文本分割成适合TTS的句子
    
    参数:
        text: 输入的小说文本
        min_length: 最小句子长度
        max_length: 最大句子长度
    
    返回:
        分割后的句子列表
    """
    # 预处理：移除多余空白，保留段落结构
    text = re.sub(r'\n+', '\n', text)
    # text = re.sub(r'[ \t]+', '', text)
    
    result = []
    
    # 按段落处理
    paragraphs = text.split('\n')
    
    for paragraph in paragraphs:
        if not paragraph.strip():
            continue
            
        # 使用 SnowNLP 进行句子分割
        s = SnowNLP(paragraph)
        sentences = s.sentences
        
        current_chunk = ""
        
        for sentence in sentences:
            # 清理句子
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # 如果当前块为空，直接添加句子
            if not current_chunk:
                current_chunk = sentence
            # 如果添加后不超过最大长度，合并
            elif len(current_chunk) + len(sentence) <= max_length:
                current_chunk += sentence
            else:
                # 当前块已达到合适长度，保存并开始新块
                if len(current_chunk) >= min_length:
                    result.append(current_chunk)
                    current_chunk = sentence
                else:
                    # 当前块太短，继续合并
                    current_chunk += sentence
        
        # 处理剩余内容
        if current_chunk:
            # 如果最后一块太短，尝试与前一块合并
            if len(current_chunk) < min_length and result:
                last = result.pop()
                if len(last) + len(current_chunk) <= max_length:
                    result.append(last + current_chunk)
                else:
                    result.append(last)
                    result.append(current_chunk)
            else:
                result.append(current_chunk)
    
    return result


def smart_split_long_sentence(sentence, max_length=70):
    """
    智能分割过长的句子，在合适的标点处断句
    """
    if len(sentence) <= max_length:
        return [sentence]
    
    result = []
    # 优先在这些标点处断句
    split_marks = ['，', '。', '！', '？', '；', '：', '"', '"']
    
    current = ""
    for char in sentence:
        current += char
        if char in split_marks and len(current) >= 50:
            result.append(current)
            current = ""
    
    if current:
        result.append(current)
    
    return result


# 示例使用
if __name__ == "__main__":
    # 示例小说文本
    sample_text = """
    月光透过窗棂洒在青石板上，映出斑驳的光影。李明轻轻推开门，看到师父正坐在院中品茶。
    "师父，我回来了。"他恭敬地说道。
    老者抬起头，眼中闪过一丝欣慰："明儿，这次下山历练，可有收获？"
    "弟子受益良多。"李明顿了顿，"这世间百态，果然不是书中所能尽述的。在江南水乡，我见到了许多善良的百姓，也遇到了一些江湖中的险恶之人。"
    师父点点头，放下茶杯："记住，习武之人，当以济世为怀。武功再高，若无德行，终究只是匹夫之勇。"
    夜风吹过，院中的竹叶沙沙作响，仿佛在低声附和着这番教诲。
    """
    
    print("=== 使用 SnowNLP 分割结果 ===\n")
    
    chunks = split_novel_for_tts(sample_text, min_length=50, max_length=70)
    
    for i, chunk in enumerate(chunks, 1):
        print(f"[句子 {i}] (长度: {len(chunk)})")
        print(chunk)
        print()
    
    print(f"总共分割成 {len(chunks)} 个句子")
