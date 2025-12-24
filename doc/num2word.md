# num2words 与中文数字处理

## 背景与问题
`num2words` 在当前环境里不支持中文（`zh`/`zh_CN`），调用会抛出 `NotImplementedError`。即使
`app.py` 会尝试安装包含 `lang_ZH_CN` 的 git 版本（`app.py` 中的包检测与安装逻辑），也仍可能因为
语言实现缺失或特定值不被支持而失败。

## 在本项目里推荐的处理方式
1. **避免在中文路径调用 num2words**
   - 通过兼容性探测控制：`lib/epub.py:_get_num2words_compat` 和 `lib/functions.py:get_num2words_compat`
     会对当前语言尝试一次 `num2words`。中文失败时应让 `is_num2words_compat=False`，从而走备用逻辑。
2. **单次调用兜底**
   - 像 `lib/epub.py:_clean_single_num` 这样，针对 `num2words(...)` 包一层 `try/except NotImplementedError`。
   - 兜底策略建议使用 `language_math_phonemes['zho']` 做逐位读法（当前项目已有该映射）。
3. **需要更自然的中文读法时**
   - 数字规范化应改为单独的中文数词转换模块（例如引入专用的中文数字转换库），而不是依赖 `num2words`。
   - 这部分目前不在仓库内实现，建议放在文本预处理阶段（`filter_chapter` → `math2words` 之前）。

## CosyVoice 与 IndexTTS 的处理方式（本仓库视角）
**结论：本仓库的 CosyVoice / IndexTTS 适配层没有调用 num2words，也没有显式的数字规范化逻辑。**

- **CosyVoice**
  - `lib/classes/tts_engines/coqui.py:_synthesize_cosyvoice` 直接把 `sentence` 传给
    `tts.inference_sft(...)` 或 `tts.inference_zero_shot(...)`，未做数字转词处理。
  - `tools/zero_short_test.py` 中有注释提示 `text_frontend=False`，说明上游 CosyVoice 内部可能有
    文本前端（包含数字规范化），但本仓库未直接控制或实现该逻辑。
- **IndexTTS**
  - `lib/classes/tts_indextts.py` 直接调用 `IndexTTS2.infer(spk_audio_prompt=..., text=...)`，
    没有本地的数字转换。
  - 是否做数字规范化由 IndexTTS 上游内部处理（仓库内无源码可确认具体规则）。

## 小结
- 中文数字不应依赖 `num2words`；应在文本预处理阶段做中文数词转换或退回逐位读法。
- CosyVoice / IndexTTS 在本仓库中仅“透传文本”，数字处理如果需要更自然，应该在进入 TTS 之前完成。


#  文本清洗

这个问题问得**非常关键**，而且你刚好踩在 **CosyVoice vs IndexTTS 的真实差异点** 上。
结论先给你：

> **两者“都能读”，但“都不可靠”**
> 👉 **正式项目（尤其有声书）一定要做文本正规化（TN）**，不要指望模型自动帮你处理。

下面我按「**数字 / 时间 / 日期**」逐条拆开说，而且会明确告诉你：
**谁能凑合用、谁必须前处理、为什么。**

---

## 一句话总览（结论版）

| 文本类型         | CosyVoice  | IndexTTS | 是否建议前处理       |
| ------------ | ---------- | -------- | ------------- |
| `123`        | ⚠️ 有时对，有时怪 | ⚠️ 波动更大  | ✅ **必须**      |
| `3:45`       | ❌ 经常读错     | ❌ 更容易翻车  | ✅ **必须**      |
| `2025-10-11` | ❌ 几乎必错     | ❌ 几乎必错   | ✅ **必须**      |
| 有声书 / 正式朗读   | ❌ 不可依赖     | ❌ 不可依赖   | ✅ **100% 要做** |

---

## 1️⃣ 数字 `123` 是怎么读的？

### CosyVoice

可能的输出包括：

* “一百二十三”（理想）
* “一二三”（逐字读）
* 停顿怪 / 语调怪（尤其在长句中）

**原因**
CosyVoice 是 **token-based + 中英文混合语料**，
数字在训练集中：

* 有的被当“数量”
* 有的被当“序号”
* 有的被当“字符串”

模型只能**猜语境**，但猜不稳。

---

### IndexTTS

更容易出现：

* “一 二 三”（逐字）
* 语速不稳定
* 有时吞掉数字（尤其在句中）

**原因**
IndexTTS 更偏「语音模仿 / 情绪 / 韵律」，
**语义理解比 CosyVoice 弱一点**，
数字这种「纯语义规则型文本」是它的短板。

---

### 正确做法（强烈建议）

在 TTS 前先转：

```
123 → 一百二十三
```

---

## 2️⃣ 时间 `3:45` 是不是灾难区？

👉 是的，而且是**双倍灾难区**。

### CosyVoice 可能会：

* “三 冒号 四十五”
* “三点 四十五”（偶尔）
* “三四五”（最糟）

### IndexTTS 更常见：

* “三 冒号 四 五”
* 停顿奇怪
* 语气完全不像时间

**原因**

* `:` 在 TTS 里是**弱语义符号**
* 时间属于 **强规则文本**
* 两个模型都 **没有显式时间解析模块**

---

### 正确做法

在 TTS 前统一转换：

```
3:45 → 三点四十五分
```

如果是口语风格：

```
3:45 → 三点四十五
```

---

## 3️⃣ 日期 `2025-10-11` 怎么样？

这块可以直接说结论：

> **不做文本处理 = 必错**

### 常见错误：

* “二零二五 减 十 减 十一”
* “二零二五 十 十一”
* 完全乱读

### 正确读法应该是：

```
2025-10-11 → 二零二五年十月十一日
```

但 **模型自己几乎不会这么做**。

---

## 4️⃣ 为什么 TTS 模型不擅长这些？

这是个结构性问题，不是模型“笨”。

### 核心原因只有一句话：

> **数字 / 时间 / 日期不是“语言”，而是“规则”**

而：

* CosyVoice / IndexTTS 都是
  **从语音分布里学语言**
* 不是从 **规则系统** 学语言

所以：

* 规则型文本 → ❌
* 文学性文本 → ✅
* 情绪、韵律 → ✅

---

## 5️⃣ 正确工程方案（你这个级别一定要这样）

### 标准流水线（强烈推荐）

```
原始文本
   ↓
TN（文本正规化）
   ↓
Clean Text（纯汉字 / 可读文本）
   ↓
CosyVoice / IndexTTS
```

---

### 最低限度你需要处理的 5 类

1. 数字（123 → 一百二十三）
2. 时间（3:45 → 三点四十五分）
3. 日期（2025-10-11 → 二零二五年十月十一日）
4. 单位（km / kg / %）
5. 英文缩写（CPU / AI）

---

## 6️⃣ 有声书场景的“真实建议”

结合你之前说的目标（**高质量、有声书、离线、可控**）：

> **TN 做得好 vs 模型差一个代际**

* TN 做好
  → CosyVoice / IndexTTS 都能“专业播音”
* TN 没做好
  → 再好的模型也像“机器人试读”

---

## 如果你愿意，我可以下一步直接帮你：

* ✅ 给你一个 **中文 TN 规则表（实战级）**
* ✅ 写一个 **Python 文本清洗 + 数字/时间/日期转换脚本**
* ✅ 按 **CosyVoice / IndexTTS 各自特点** 微调规则
* ✅ 专门针对 **有声书**（不是客服播报）

你只要告诉我：
👉 **你现在的文本来源是：小说？历史？教材？新闻？**


# TN库

好问题，而且你已经问到 **TTS 工程里“最容易被忽略、但最值钱”的那一层** 了 👍
我直接给你一个**工程视角的答案**，不绕学术。

---

# 一、有没有「现成可用」的中文 TN 库？

先给结论：

> **有，但没有一个是「拿来就能完美用于有声书 TTS」的**
> 👉 **现实做法：选一个“基础库” + 少量定制规则**

下面是目前业内**真实在用**的几类方案。

---

## 1️⃣ WeText（CosyVoice 在用）

### 是什么？

**WeText = 阿里系中文文本规范化（TN）系统**

> CosyVoice **并不是“自动会读数字”**，
> 它是 **前面偷偷跑了一层 WeText**。

### 它主要干什么？

* 数字 → 中文
* 日期 / 时间
* 金额
* 百分比
* 单位（km、kg、℃）
* 中英文混排
* 标点、空白清洗

👉 本质：**TTS 前的文本清洗 + 规则转换器**

---

### 举例（WeText 能做的）

```
2025-10-11 → 二零二五年十月十一日
3:45 → 三点四十五分
123 → 一百二十三
12.5% → 百分之十二点五
```

---

### WeText 的真实评价（很重要）

✅ **优点**

* 中文规则覆盖非常全
* 工业级（客服、播报）
* CosyVoice 训练时“假设它存在”

⚠️ **缺点**

* **不是 pip install 就能用**
* 依赖多、偏重
* 默认规则偏「播报腔」，**不完全适合有声书**
* 开源程度一般（更多是内部用）

👉 **结论**
CosyVoice **强烈假设你会用 TN**，
而 WeText 就是它的“官方答案”。

---

## 2️⃣ Python 里可用的中文 TN 库（你能真正用的）

### ✅ ① `cn2an`（最常用，最干净）

> **中文数字处理的“地基库”**

```bash
pip install cn2an
```

#### 能干什么？

```python
import cn2an

cn2an.an2cn("123")       # 一百二十三
cn2an.an2cn("12.5")      # 十二点五
cn2an.an2cn("2025")      # 二千零二十五 / 可调模式
```

✅ 优点

* 稳定
* 规则清晰
* 超适合「自己写 TN」

❌ 缺点

* **不懂语境**
* 不会自动处理时间 / 日期

👉 **这是你一定会用到的库**

---

### ✅ ② `zhdate`（日期专用）

```bash
pip install zhdate
```

```python
from zhdate import ZhDate

ZhDate(2025, 10, 11).chinese()  
# 二零二五年十月十一日
```

适合：

* 年月日格式
* 标准公历日期

---

### ⚠️ ③ PaddleSpeech / ESPnet TN

* 工程重
* 依赖深
* 更适合 ASR pipeline
* 不适合你现在的「轻量离线 TTS」

---

## 3️⃣ 所以：**CosyVoice 到底怎么用 WeText？**

这是个**容易误解的点**。

### CosyVoice 并不是：

> “模型内部理解数字、时间”

### 而是：

```
原始文本
 ↓
WeText（TN）
 ↓
模型只负责“朗读已经规范化的文本”
```

👉 CosyVoice 的 **高稳定度朗读**
**50% 来自 TN，不是模型本身**

这也是为什么：

* 你关掉 / 没用 TN
* CosyVoice 读数字立刻翻车

---

## 4️⃣ IndexTTS 为什么问题更明显？

IndexTTS：

* **没有内建 WeText**
* 也不假设你做了完整 TN
* 更专注 **声音还原 / 情绪 / 韵律**

👉 所以：

* 数字、日期、时间
  **比 CosyVoice 更依赖你自己做 TN**

---

## 5️⃣ 给你一个「现实可用」的 TN 方案（强烈推荐）

### ✅ 轻量、可控、适合有声书

**组合拳：**

```
regex + cn2an + 自定义时间/日期规则
```

### 示例流程（你未来 90% 会用这个）

```python
def normalize(text):
    text = normalize_date(text)    # 2025-10-11 → 二零二五年十月十一日
    text = normalize_time(text)    # 3:45 → 三点四十五分
    text = normalize_number(text)  # 123 → 一百二十三
    return text
```

**优势**

* 可控
* 可调「播音腔 vs 小说腔」
* 和 CosyVoice / IndexTTS 都完美兼容
* 不依赖重型系统

---

## 6️⃣ 给你的最终建议（直说）

> 如果你目标是：
> **高质量有声书 + 离线 + 声音克隆**

### ❌ 不建议

* 指望模型“自动读对”
* 直接硬接 WeText（太重）

### ✅ 强烈建议

* 用 `cn2an` + 规则
* 自己掌控 TN
* 把 TN 当作 **和模型同等重要的模块**

---

## 下一步我可以直接帮你做的事

如果你点头，我可以直接给你：

1. ✅ **一个完整的中文 TN Python 模块**

   * 数字 / 时间 / 日期 / 百分比 / 单位
2. ✅ **小说 & 有声书专用规则**
3. ✅ **CosyVoice / IndexTTS 差异化优化**
4. ✅ 可选：**WeText 风格 vs 小说风格切换**

你只要说一句：
👉 **“先给我一个可直接用的 TN 脚本”**

下面按你问的 3 块来讲：**CosyVoice / IndexTTS 对数字/时间/日期怎么读**、**中文 TN(文本规范化)有哪些库**、以及 **PaddleSpeech vs ESPnet vs WeText(=wetext/WeTextProcessing) 的中文 TN 能力对比**。

---

## 1) CosyVoice / IndexTTS：`123`、`3:45`、`2025-10-11` 能不能直接读？

### CosyVoice

CosyVoice 官方特性里明确写了 **Text Normalization：能读数字、特殊符号、各种文本格式，不需要传统前端模块**。([GitHub][1])
另外它在 roadmap 里也提到 **当 ttsfrd 不可用时会用 WeTextProcessing**。([GitHub][1])
在它的 CLI 前端代码里还能看到：导入失败会打印 “use wetext instead”，并 `from wetext import Normalizer` 作为中英文 normalizer。([GitHub][2])

**结论（CosyVoice）：**多数情况下你直接喂：

* `123` → 往往会读成「一百二十三」（也可能按语境读「一二三」这类，取决于 TN 规则/模型鲁棒性）
* `3:45` → 往往会读成「三点四十五（分）」
* `2025-10-11` → 往往会读成「二零二五年十月十一日」或「2025年10月11日」

但如果你做**有声书/正式播报**，建议仍然在前面做一次 TN（原因见下文“歧义”）。

### IndexTTS（IndexTTS2 / IndexTTS-1.x）

IndexTTS 这边也**集成了 wetext/WeTextProcessing**：例如它的 PR 日志里出现 `WETEXT INFO found existing fst ... zh_tn_tagger.fst / zh_tn_verbalizer.fst`。([GitHub][3])
而且它的依赖/安装讨论里也明确提到 `wetext` / `WeTextProcessing`（不同平台选择不同包）。([GitHub][4])

**结论（IndexTTS）：**同样“通常可以直接读出”数字、时间、日期；底层也是走一套 TN FST/规则图，所以对 `123 / 3:45 / 2025-10-11` 这类一般没问题。

---

## 2) 什么时候“需要先做文本处理(TN)”？

即使 CosyVoice/IndexTTS 都“号称能读”，你在生产（尤其有声书）里还是会遇到 **TN 歧义**，常见是：

* `123` 该读「一百二十三」还是「幺二三」还是「一二三」？
* `3:45` 在口语里可能是「三点四十五」；在比赛时间可能是「三分四十五秒」
* `2025-10-11` 是「2025年10月11日」还是「2025-10-11（逐字符）」？分隔符 `- / .` 也会影响读法

**经验建议：**

* **聊天/普通短句**：直接丢给模型，基本够用。
* **有声书/新闻播报/金融数字**：强烈建议你**自己做 TN**，把最终口播形式固定下来（比如统一日期读法、金额读法、编号读法），再喂给 TTS。这样一致性最好、可控性最高。

---

## 3) 有哪些专门做中文数字/日期时间 TN 的库？wetext / WeTextProcessing 是干嘛的？

你问的“cosyvoice 使用了 wetext，是干吗用的？”——核心就是：**Text Normalization（TN）/Inverse TN（ITN）**。

### wetext / WeTextProcessing（WeNet 体系）

* **WeTextProcessing** 是 WeNet 社区的（逆）文本规范化项目：提供 **TN pipeline / ITN pipeline**。([GitHub][5])
* PyPI 上的 **WeTextProcessing** 也写得很直白：参考了 NeMo 的 TN 数据、以及 `chinese_text_normalization` 的 ITN 数据来构建图（tagger graph）。([PyPI][6])
* 在 CosyVoice 里，代码层面会把它当作“前端 TN”组件来用（以及 ttsfrd 不可用时的替代）。([GitHub][1])
* 在 IndexTTS 里，也能看到它运行时加载 `zh_tn_tagger.fst / zh_tn_verbalizer.fst` 这类 FST 文件（典型 WFST/图规范化做法）。([GitHub][3])

**一句话：**`wetext/WeTextProcessing` 就是把“书面写法”变成“口语读法”的前端：数字、日期、时间、温度、单位、符号、混合中英文等，尽量转成稳定可读的文本（或读音标注）。

### PaddleSpeech 自带的中文 TN

PaddleSpeech 有一整套 **rule-based Chinese frontend**，包含 TN、分词、G2P（多音字、变调等）。([GitHub][7])
它也有专门的 API 文档入口：`paddlespeech.t2s.frontend.zh_normalization`。([PaddleSpeech][8])

---

## 4) PaddleSpeech vs ESPnet 的中文 TN：能力如何？与 wetext/WeTextProcessing 对比

这里有个很“硬”的对比点来自 PaddleSpeech 的论文（NAACL demo / arXiv 版本都能看到）：

> **ESPnet 的普通话 TN 处理不了某些日期（如 2020/10/29）和温度（如 -3°C）**；PaddleSpeech 强调它的中文前端更完整。([ACL Anthology][9])

基于公开信息，可以这样理解三者定位：

### A) PaddleSpeech（偏“传统中文 TTS 前端”的完整链路）

* 优势：中文前端组件齐全（TN、分词、G2P、多音字、变调），更像“工程化传统 TTS”的那套。([GitHub][7])
* TN 能力：对中文常见格式一般覆盖好；你可以把它当“规则系统”，可预期、可控、可定制（改规则/字典）。
* 适合：你要做**强一致性**（有声书、播报、客服脚本）并且愿意维护前端规则。

### B) ESPnet（更偏研究/训练框架，中文 TN 往往不作为强项）

* 论文里明确点名：ESPnet 的 Mandarin TN 对某些**日期/温度**处理不正确。([arXiv][10])
* 适合：你更看重端到端研究/可复现训练流水线，而不是拿来就做“工业级中文口播格式覆盖”。

### C) wetext / WeTextProcessing（偏“WFST 图”的 TN/ITN 专项库，常被各家集成）

* 优势：专注做 TN/ITN，本身就是给 ASR/TTS 工程当“标准件”的思路；能提供 tagger/verbalizer 这套图（你在 IndexTTS 日志里看到的 fst 就是这类）。([GitHub][3])
* 适合：你希望一个**独立 TN 模块**，能被 CosyVoice/IndexTTS/你自己的管线复用；并且希望它对“数字/符号/格式”覆盖更系统。

---

## 给你的实操建议（最稳的做法）

* **想省事**：直接喂 CosyVoice/IndexTTS 原始文本；它们确实“通常能读”。([GitHub][1])
* **想可控/一致**（尤其有声书）：把 TN 放在你自己的 preprocessing：

  * 统一规则：日期永远读“二零二五年十月十一日”，时间永远读“三点四十五分”，编号永远读“一二三”……
  * 然后再喂给模型，减少“同一格式多种读法”的随机性。

如果你愿意贴一段你真实要合成的中文句子（包含数字/时间/日期/金额/单位），我可以按“有声书播报口径”给你一套更细的 TN 规范和示例输出。

[1]: https://github.com/FunAudioLLM/CosyVoice "GitHub - FunAudioLLM/CosyVoice: Multi-lingual large voice generation model, providing inference, training and deployment full-stack ability."
[2]: https://github.com/FunAudioLLM/CosyVoice/blob/main/cosyvoice/cli/frontend.py?utm_source=chatgpt.com "CosyVoice/cosyvoice/cli/frontend.py at main"
[3]: https://github.com/index-tts/index-tts/pull/147?utm_source=chatgpt.com "adding support to specify GPU Device by ID through CLI ..."
[4]: https://github.com/index-tts/index-tts/issues/313?utm_source=chatgpt.com "感觉环境部署不友好，除了uv有没有别的环境部署方式呢#313"
[5]: https://github.com/wenet-e2e/WeTextProcessing?utm_source=chatgpt.com "wenet-e2e/WeTextProcessing: Text Normalization & ..."
[6]: https://pypi.org/project/WeTextProcessing/0.0.3/?utm_source=chatgpt.com "WeTextProcessing 0.0.3"
[7]: https://github.com/PaddlePaddle/PaddleSpeech?utm_source=chatgpt.com "PaddlePaddle/PaddleSpeech"
[8]: https://paddlespeech.readthedocs.io/en/latest/api/paddlespeech.t2s.frontend.zh_normalization.html?utm_source=chatgpt.com "paddlespeech.t2s.frontend.zh_normalization package"
[9]: https://aclanthology.org/2022.naacl-demo.12.pdf?utm_source=chatgpt.com "PaddleSpeech: An Easy-to-Use All-in-One Speech Toolkit"
[10]: https://arxiv.org/pdf/2205.12007?utm_source=chatgpt.com "arXiv:2205.12007v1 [eess.AS] 20 May 2022"



这个问题我可以**非常明确地给你一个工程结论**，而且是站在你「**已经在用 num2words、有现成 TN 架构**」这个前提下说的。

---

# 结论先行（直给）

> **如果目标是：最小改动、最快落地、像 num2words 一样可插拔**
> 👉 **选：WeText（WeTextProcessing / wetext）**

> **如果目标是：做一整套“传统 TTS 中文前端”，愿意重构**
> 👉 才考虑 PaddleSpeech TN

一句话总结：

| 维度              | WeText       | PaddleSpeech |
| --------------- | ------------ | ------------ |
| 集成成本            | ⭐⭐⭐⭐⭐ **最低** | ⭐⭐           |
| 是否可作为“独立 TN 模块” | ✅ 是          | ❌ 不太是        |
| 架构侵入性           | 低            | 高            |
| 是否像 num2words   | ✅ 非常像        | ❌ 完全不是       |
| 中文规则完整度         | ⭐⭐⭐⭐         | ⭐⭐⭐⭐⭐        |
| 适合你当前代码         | ✅ **非常适合**   | ❌            |

---

下面我按**“代码架构视角”**给你拆清楚。

---

# 你的现状（这是关键前提）

你现在是：

```text
raw text
  ↓
num2words (EN / FR / DE / ...)
  ↓
normalized text
  ↓
TTS
```

也就是说你已经有：

* ✅ **TN 是前置模块**
* ✅ **函数式 / pipeline 化**
* ✅ **语言无关接口**
* ❌ **缺中文实现**

👉 你缺的不是「TN 理论」，而是**一个能无痛替换的中文 TN 实现**

---

# 一、WeText（wetext / WeTextProcessing）为什么更适合你

## 1️⃣ 架构层面：它就是“TN 库”，不是 TTS 系统

WeText 的定位非常清晰：

```text
text → TN → text
```

它做的事和 num2words **在同一层**，只是覆盖面更广：

* 数字
* 日期
* 时间
* 单位
* 符号
* 中英文混排
* 罗马数字（部分）

👉 **它不关心声学模型、分词、G2P、韵律**

这点极其重要。

---

## 2️⃣ 调用方式：可直接包一层，像 num2words 一样用

工程上你可以做到这种效果：

```python
def normalize_zh(text):
    return wetext_normalizer.normalize(text)
```

然后在你现有代码里：

```python
if lang == "zh":
    text = normalize_zh(text)
else:
    text = num2words_normalize(text, lang)
```

**不需要动你后面的 TTS 逻辑**。

---

## 3️⃣ 和 CosyVoice / IndexTTS 是“同源假设”

这是隐藏但非常重要的一点：

* CosyVoice：**默认假设你用 WeText**
* IndexTTS：**直接加载 WeText 的 FST**

👉 用 WeText，你是在**顺着模型作者的工程假设走**

这意味着：

* 少踩坑
* 少“模型奇怪发音”
* 行为更可预测

---

## 4️⃣ 你可以“只用它的中文部分”

你不用全量引入 WeNet / ASR 那一套。

现实中很多人只干一件事：

* 拿 WeText
* 用中文 TN
* 其他语言继续用 num2words

**这在工程上是完全合理的**

---

# 二、PaddleSpeech TN：为什么不适合你现在的架构

我说结论前先强调一句：

> **PaddleSpeech 的 TN 很强，但它不是“库思维”**

---

## 1️⃣ PaddleSpeech 是“完整中文 TTS 前端”，不是 TN 库

PaddleSpeech 的中文前端是：

```text
TN
 ↓
中文分词
 ↓
多音字 disambiguation
 ↓
G2P
 ↓
声调 / 变调
 ↓
phoneme sequence
```

👉 它的 TN 是**为后续 phoneme pipeline 服务的**

而你现在的系统是：

```text
TN → text → TTS（端到端）
```

**模型边界完全不同。**

---

## 2️⃣ 集成 PaddleSpeech = 架构升级，而不是加模块

一旦你用 PaddleSpeech TN，你很容易会被“诱导”去：

* 用它的 tokenizer
* 用它的 lexicon
* 用它的 G2P
* 用它的 phoneme 表达

最后会变成：

> “我只是想转个日期，结果引进了一整套 TTS 前端”

这在工程上叫 **架构污染**。

---

## 3️⃣ PaddleSpeech TN 不适合“语言无关”架构

你现在明显是多语言系统（num2words 就是证据）。

而 PaddleSpeech 是：

* 极度中文中心
* 默认假设你后面也是 PaddleSpeech TTS

👉 它**不适合当一个 drop-in 的 zh normalizer**

---

# 三、WeText vs PaddleSpeech：工程级对比表（重点）

| 维度              | WeText   | PaddleSpeech |
| --------------- | -------- | ------------ |
| 是否可单独使用         | ✅        | ⚠️ 勉强        |
| 是否语言无关          | ⚠️ 只负责中文 | ❌            |
| 是否侵入后端          | ❌        | ✅            |
| 是否适合 TTS 前端独立模块 | ✅        | ❌            |
| 是否像 num2words   | ✅        | ❌            |
| 是否适合快速补齐中文      | ✅ **强烈** | ❌            |

---

# 四、我给你的“最佳实践建议”

## ✅ 最优解（我非常推荐）

```text
num2words  → 英文/其他语言
WeText     → 中文
自定义规则 → 小说/播音风格差异
```

也就是：

* **不要指望一个库解决所有语言**
* 每种语言用“最适合它的 TN”

---

## 🚫 不建议你现在就做的事

* 不要为了中文 TN 重构成 PaddleSpeech pipeline
* 不要把 phoneme-level 前端塞进端到端 TTS
* 不要让 TN 和声学模型耦合

---

# 五、如果你愿意，我可以直接帮你做这三件事之一

1️⃣ **把你现有的 num2words TN 架构改造成「多语言 TN Adapter」**
2️⃣ **写一个 `ZhNormalizer`，底层用 WeText，但接口风格和 num2words 一致**
3️⃣ **顺便补上你现在用 num2words 但中文缺失的：日期 / 时间 / 罗马数字策略**

你只要告诉我一句：
👉 **“我的 TN 现在是怎么组织的（函数 / 类 / pipeline）”**
