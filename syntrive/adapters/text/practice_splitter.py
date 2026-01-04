import re
from dataclasses import dataclass
from typing import List, Literal, Iterable

Kind = Literal["title", "narration", "dialog"]

@dataclass
class Segment:
    text: str
    kind: Kind

# ---- 基础清洗与工具 ----

TITLE_RE = re.compile(r"^\s*(第[一二三四五六七八九十百千万0-9]+[章节回卷部].{0,20}|楔子|序章|序|后记|番外.{0,10})\s*$")

END_PUNC_RE = re.compile(r"[。！？…]+$")   # 允许 …… 或 ……
HARD_SPLIT_RE = re.compile(r"([。！？…]+)(?!”)\s*")  # 句末强切（尽量不把 ” 后面的粘走）
WEAK_SPLIT_RE = re.compile(r"([；：，])\s*")

QUOTE_RE = re.compile(r"“([^”]+)”")  # 简化版：不处理跨段引号（结构解析里会讲怎么增强）

def normalize_text(s: str) -> str:
    s = s.replace("\u3000", " ")          # 全角空格
    s = re.sub(r"[ \t]+", " ", s)
    s = s.replace("……", "…")              # 统一省略号（可选）
    s = s.replace("——", "—")              # 统一破折号（可选）
    return s.strip()

def ensure_end_punc(s: str, kind: Kind) -> str:
    s = s.strip()
    if not s:
        return s
    if END_PUNC_RE.search(s):
        return s
    # 对话常用“。”也行；如果你想更“口语”，可根据是否包含疑问词来补 ？/！
    return s + ("。" if kind != "title" else "")

# ---- 核心：对话感知切分 ----

def split_by_hard_punc(s: str) -> List[str]:
    # 保留分隔符
    parts = []
    start = 0
    for m in HARD_SPLIT_RE.finditer(s):
        end = m.end()
        chunk = s[start:end].strip()
        if chunk:
            parts.append(chunk)
        start = end
    tail = s[start:].strip()
    if tail:
        parts.append(tail)
    return parts

def split_to_maxlen(s: str, max_len: int) -> List[str]:
    """把一个句子进一步切到 max_len 以内：优先弱标点，其次硬切。"""
    s = s.strip()
    if len(s) <= max_len:
        return [s]

    # 先按弱标点分
    tokens = []
    buf = ""
    i = 0
    while i < len(s):
        buf += s[i]
        if s[i] in "，；：":
            tokens.append(buf.strip())
            buf = ""
        i += 1
    if buf.strip():
        tokens.append(buf.strip())

    # 重新拼成不超过 max_len 的块
    out, cur = [], ""
    for t in tokens:
        if not cur:
            cur = t
        elif len(cur) + len(t) <= max_len:
            cur += t
        else:
            out.append(cur.strip())
            cur = t
    if cur.strip():
        out.append(cur.strip())

    # 如果还有超过 max_len 的，做硬切回退
    final = []
    for x in out:
        if len(x) <= max_len:
            final.append(x)
        else:
            # 极端长无标点：直接切片
            for j in range(0, len(x), max_len):
                final.append(x[j:j+max_len].strip())
    return [z for z in final if z]

def dialog_aware_segment(paragraph: str,
                         max_len: int = 160,
                         dialog_max_len: int = 90) -> List[Segment]:
    """
    输入一个“段落”（已按空行切过），输出 narration/dialog/title 的 Segment 列表。
    """
    p = normalize_text(paragraph)
    if not p:
        return []

    if TITLE_RE.match(p):
        return [Segment(text=p, kind="title")]

    segs: List[Segment] = []

    # 1) 把段落按引号对话拆成：旁白片段 + 对话片段 + 旁白片段...
    last = 0
    for m in QUOTE_RE.finditer(p):
        # 旁白
        nar = p[last:m.start()].strip()
        if nar:
            segs.append(Segment(nar, "narration"))
        # 对话
        dia = m.group(0).strip()  # 包含引号
        segs.append(Segment(dia, "dialog"))
        last = m.end()

    tail = p[last:].strip()
    if tail:
        segs.append(Segment(tail, "narration"))

    # 2) 对每个片段做强标点切分 + 长度控制
    out: List[Segment] = []
    for s in segs:
        if s.kind == "title":
            out.append(s)
            continue

        # 对话：尽量不切碎一个 turn（先按句末强标点切，超长再弱切）
        chunks = split_by_hard_punc(s.text)
        maxl = dialog_max_len if s.kind == "dialog" else max_len

        for c in chunks:
            # 超长再二次切
            for piece in split_to_maxlen(c, maxl):
                piece = ensure_end_punc(piece, s.kind)
                out.append(Segment(piece, s.kind))

    return out

def segment_novel(text: str,
                  max_len: int = 70,
                  dialog_max_len: int = 50) -> List[Segment]:
    # 按空行切段落
    paras = [x for x in re.split(r"\n\s*\n+", text) if x.strip()]
    all_segs: List[Segment] = []
    for para in paras:
        all_segs.extend(dialog_aware_segment(para, max_len=max_len, dialog_max_len=dialog_max_len))
    return all_segs
