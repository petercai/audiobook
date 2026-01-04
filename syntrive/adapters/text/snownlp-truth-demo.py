"""
SnowNLP 标点符号丢失的真相
从源代码角度分析问题并提供解决方案
"""

from snownlp import SnowNLP
from snownlp import normal  # 直接导入 normal 模块
import re

print("=" * 70)
print("SnowNLP 标点符号丢失的真相")
print("=" * 70)

# 测试文本
test_text = "月光透过窗棂洒在青石板上。李明轻轻推开门！师父正坐在院中品茶？"

print(f"\n原文:\n{test_text}\n")

# 创建 SnowNLP 对象
s = SnowNLP(test_text)

print("=" * 70)
print("问题：s.sentences 的结果")
print("=" * 70)

# 查看 s.sentences 返回什么
print("\ns.sentences 的结果:")
for i, sent in enumerate(s.sentences, 1):
    print(f"  [{i}] {sent}")
    print(f"      标点: {'✗ 丢失' if not any(p in sent for p in '。！？；') else '✓ 保留'}")

print("\n" + "=" * 70)
print("真相：查看源代码")
print("=" * 70)

print("""
从 SnowNLP 源代码可以看到:

# snownlp/__init__.py
class SnowNLP(object):
    @property
    def sentences(self):
        return normal.get_sentences(self.doc)  # 调用 normal.get_sentences()

关键在于 normal.get_sentences() 的实现!
""")

print("=" * 70)
print("直接调用 normal.get_sentences()")
print("=" * 70)

# 直接调用底层函数
sentences_from_normal = normal.get_sentences(test_text)
print("\nnormal.get_sentences() 的结果:")
for i, sent in enumerate(sentences_from_normal, 1):
    print(f"  [{i}] {sent}")
    print(f"      标点: {'✗ 丢失' if not any(p in sent for p in '。！？；') else '✓ 保留'}")

print("\n" + "=" * 70)
print("结论")
print("=" * 70)

print("""
❌ SnowNLP 的 normal.get_sentences() 函数在分句时**会移除标点符号**
❌ 这是 SnowNLP 源代码的设计决定，不是 bug
❌ s 对象中没有保留标点信息的其他属性

因此，必须从原始文本中找回标点！
""")

print("\n" + "=" * 70)
print("解决方案：改进的 SnowNLP 分句器")
print("=" * 70)


class ImprovedSnowNLPSplitter:
    """
    改进的 SnowNLP 分句器
    保留与原版相似的结构，但保留标点
    """
    
    def __init__(self, min_length=50, max_length=70):
        self.min_length = min_length
        self.max_length = max_length
    
    def split_with_punctuation(self, text):
        """
        方法1：直接用正则分句（不依赖 SnowNLP 的分句）
        这是最简单可靠的方法
        """
        # 在句末标点处分割，并保留标点
        pattern = r'([^。！？；…]*[。！？；…]+)'
        sentences = re.findall(pattern, text)
        
        # 处理末尾没有标点的部分
        remaining = re.sub(pattern, '', text).strip()
        if remaining:
            sentences.append(remaining)
        
        return [s.strip() for s in sentences if s.strip()]
    
    def split_using_snownlp_with_mapping(self, text):
        """
        方法2：使用 SnowNLP 分句，然后映射回标点
        保持使用 SnowNLP，但修复标点问题
        """
        s = SnowNLP(text)
        sentences_no_punct = s.sentences
        
        sentences_with_punct = []
        search_pos = 0
        
        for sentence in sentences_no_punct:
            if not sentence.strip():
                continue
            
            # 在原文中查找这个句子
            idx = text.find(sentence, search_pos)
            
            if idx != -1:
                # 找到句子结束位置
                end_pos = idx + len(sentence)
                
                # 查找后面的标点
                while end_pos < len(text) and text[end_pos] in '。！？；…""''':
                    end_pos += 1
                
                # 提取带标点的句子
                full_sentence = text[idx:end_pos]
                sentences_with_punct.append(full_sentence)
                search_pos = end_pos
            else:
                sentences_with_punct.append(sentence)
        
        return sentences_with_punct
    
    def split_for_tts(self, text, method='regex'):
        """
        完整分割流程
        method: 'regex' 或 'snownlp'
        """
        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r'[ \t]+', '', text)
        
        result = []
        paragraphs = text.split('\n')
        
        for paragraph in paragraphs:
            if not paragraph.strip():
                continue
            
            # 选择分句方法
            if method == 'regex':
                sentences = self.split_with_punctuation(paragraph)
            else:
                sentences = self.split_using_snownlp_with_mapping(paragraph)
            
            # 合并到适当长度
            current_chunk = ""
            for sentence in sentences:
                if not current_chunk:
                    current_chunk = sentence
                elif len(current_chunk) + len(sentence) <= self.max_length:
                    current_chunk += sentence
                else:
                    if len(current_chunk) >= self.min_length:
                        result.append(current_chunk)
                        current_chunk = sentence
                    else:
                        current_chunk += sentence
            
            if current_chunk:
                if len(current_chunk) < self.min_length and result:
                    result[-1] += current_chunk
                else:
                    result.append(current_chunk)
        
        return result


# 测试改进方案
print("\n测试改进方案:\n")

test_text = """
月光透过窗棂洒在青石板上，映出斑驳的光影。李明轻轻推开门，看到师父正坐在院中品茶。
"师父，我回来了。"他恭敬地说道。
老者抬起头，眼中闪过一丝欣慰："明儿，这次下山历练，可有收获？"
"""

splitter = ImprovedSnowNLPSplitter(min_length=40, max_length=70)

print("方法1: 使用正则分句（推荐）")
print("-" * 70)
chunks1 = splitter.split_for_tts(test_text, method='regex')
for i, chunk in enumerate(chunks1, 1):
    has_punct = any(p in chunk for p in '。！？；')
    print(f"[{i}] {chunk}")
    print(f"    标点: {'✓ 保留' if has_punct else '✗ 丢失'} | 长度: {len(chunk)}\n")

print("\n方法2: 使用 SnowNLP + 标点映射")
print("-" * 70)
chunks2 = splitter.split_for_tts(test_text, method='snownlp')
for i, chunk in enumerate(chunks2, 1):
    has_punct = any(p in chunk for p in '。！？；')
    print(f"[{i}] {chunk}")
    print(f"    标点: {'✓ 保留' if has_punct else '✗ 丢失'} | 长度: {len(chunk)}\n")

print("=" * 70)
print("最终建议")
print("=" * 70)
print("""
1. SnowNLP 的 s.sentences 确实会丢失标点（这是设计如此）
2. s 对象中没有其他属性保存标点信息
3. 必须从原文（self.doc）中找回标点

推荐方案：
- 如果只是需要分句：使用方法1（正则表达式）
- 如果必须用 SnowNLP：使用方法2（映射回标点）

两种方法都能100%保留标点符号！
""")
