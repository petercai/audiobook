\
## **正确使用 HanLP 的两种方法**

### **方法1: NLPTokenizer.segment()** ✅
```python
seg_result = self.tokenizer.segment(para)  # 真正调用了！
for term in seg_result:
    word = str(term.word)
    # 根据标点符号重组句子
```

### **方法2: HanLP.segment()** ✅
```python
terms = HanLP.segment(para)  # 真正调用了！
for term in terms:
    word = str(term.word)
```

## **关键区别**

| 方法 | 优势 | 适用场景 |
|------|------|----------|
| NLPTokenizer | 更智能的分词，考虑语义 | 复杂文本、对话多 |
| HanLP.segment() | 更简单，速度快 | 一般小说、描述多 |
