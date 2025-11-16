好的，我来给你写一个 **完整可行的方法**，用 **Calibre 的命令行工具 `ebook-convert`** 来把中文 TXT 小说转换成 EPUB，同时正确识别章节（“第100章”这种格式）。

---

# 1️⃣ **准备工作**

1. 安装 Calibre（Windows / Linux / macOS 都行）
2. 找到命令行工具：

* Windows 默认路径：

```
C:\Program Files\Calibre2\ebook-convert.exe
```

* Linux / macOS：

```
ebook-convert
```

3. 确保 TXT 文件编码为 **UTF-8**，避免中文乱码。

---

# 2️⃣ **章节识别设置**

我们使用 **XPath 章节匹配**，例如：

```xpath
//p[starts-with(normalize-space(.), '第') and contains(., '章')]
```

这是最通用的中文小说章节匹配方法。

---

# 3️⃣ **命令行示例**

假设：

* 输入文件：`novel.txt`
* 输出文件：`novel.epub`
* Calibre XPath 配置如下：

```bash
ebook-convert novel.txt novel.epub \
    --chapter "//p[starts-with(normalize-space(.), '第') and contains(., '章')]" \
    --input-encoding utf-8 \
    --output-profile default \
    --no-default-epub-cover
```

### 参数解释：

| 参数                         | 说明                 |
| -------------------------- | ------------------ |
| `--chapter`                | 指定 XPath 或正则匹配章节标题 |
| `--input-encoding utf-8`   | 保证中文正确             |
| `--output-profile default` | 输出 EPUB 默认配置       |
| `--no-default-epub-cover`  | 如果没有封面可以跳过         |

---

# 4️⃣ **可选增强版**

如果小说可能有 **回/节/章**，用增强 XPath：

```bash
ebook-convert novel.txt novel.epub \
    --chapter "//p[starts-with(normalize-space(.), '第') and (contains(., '章') or contains(., '回') or contains(., '节'))]" \
    --input-encoding utf-8
```

---

# 5️⃣ **其他实用命令行参数**

* `--level1-toc` 指定 TOC 第一层章节，例如：

```bash
--level1-toc "//p[starts-with(normalize-space(.), '第') and contains(., '章')]"
```

* `--no-inline-toc` 避免在正文开头生成重复 TOC
* `--pretty-print` 美化 HTML

完整示例：

```bash
ebook-convert novel.txt novel.epub \
    --chapter "//p[starts-with(normalize-space(.), '第') and contains(., '章')]" \
    --level1-toc "//p[starts-with(normalize-space(.), '第') and contains(., '章')]" \
    --input-encoding utf-8 \
    --no-default-epub-cover \
    --no-inline-toc \
    --pretty-print
```

---

# 6️⃣ **流程总结**

1. 确保 TXT 文件格式规范（每章首行是 `第xxx章 标题`）
2. 使用 `ebook-convert` 命令行工具，指定 **章节 XPath**
3. 输出 EPUB，Calibre 会自动生成：

* 正确的章节目录
* 分章节 XHTML 文件
* TOC / EPUB 标准导航

---

如果你愿意，我可以帮你写一个 **Windows 一键批量脚本**，支持：

* 自动遍历多个 TXT 小说
* 自动识别“第xxx章”
* 输出 EPUB，包含目录
* 保证中文不乱码

你希望我帮你写这个脚本吗？

明白了，我给你写一个 **Windows 一键批量转换中文 TXT 小说到 EPUB 的脚本**，支持：

* 自动识别章节（“第100章”格式）
* 保证中文 UTF-8 正确显示
* 自动生成 EPUB 目录

---

# 1️⃣ **批量转换脚本（Windows Batch）**

把下面内容保存为 `convert_txt_to_epub.bat`，放在你的小说 TXT 文件夹里：

```bat
@echo off
REM 设置 Calibre ebook-convert 路径
set CALIBRE_PATH="C:\Program Files\Calibre2\ebook-convert.exe"

REM XPath 正则匹配章节
set CHAPTER_XPATH=//p[starts-with(normalize-space(.), '第') and contains(., '章')]

REM 遍历当前目录下所有 TXT 文件
for %%f in (*.txt) do (
    echo 正在转换 %%f ...
    %CALIBRE_PATH% "%%f" "%%~nf.epub" ^
        --chapter "%CHAPTER_XPATH%" ^
        --level1-toc "%CHAPTER_XPATH%" ^
        --input-encoding utf-8 ^
        --no-default-epub-cover ^
        --no-inline-toc ^
        --pretty-print
    echo 完成 %%f
)
pause
```

### ✅ 使用方法

1. 把脚本和 TXT 小说放在同一个文件夹
2. 双击运行
3. 所有 TXT 会生成对应的 EPUB 文件
4. 每章会按“第xxx章”自动分章节，并生成 EPUB TOC

---

# 2️⃣ **注意事项**

* **TXT 文件必须 UTF-8 编码**
* **章节标题格式**必须是 `第xxx章`，否则 XPath 不会匹配
* 如果小说有 **回/节**，修改 `CHAPTER_XPATH` 为：

```bat
set CHAPTER_XPATH=//p[starts-with(normalize-space(.), '第') and (contains(., '章') or contains(., '回') or contains(., '节'))]
```

* 如果有封面，可在命令里加：

```bat
--cover "cover.jpg"
```

---

我也可以帮你写一个 **Python 版本脚本**，它更智能：

* 自动处理 TXT 编码
* 自动清理多余空行
* 支持章节标题的多种写法
* 支持批量转换

你想让我写 Python 版吗？


好的，我来帮你写一个 **Python 版本的批量 TXT → EPUB 转换脚本**，专门针对中文小说，支持：

* 自动识别章节（“第100章”、“第100回”、“第100节”）
* 保证中文 UTF-8 编码
* 自动生成 EPUB 目录
* 可选封面

下面是完整脚本示例：

---

```python
import os
import subprocess

# =======================
# 配置部分
# =======================
# Calibre ebook-convert 可执行文件路径
CALIBRE_PATH = r"C:\Program Files\Calibre2\ebook-convert.exe"

# 当前目录下 TXT 小说文件夹（可改成绝对路径）
TXT_FOLDER = r"."

# 可选封面文件（放在 TXT 文件夹下），如果不需要设置为 None
COVER_FILE = None  # 示例: "cover.jpg"

# XPath 章节匹配（中文小说第xxx章/回/节）
CHAPTER_XPATH = "//p[starts-with(normalize-space(.), '第') and (contains(., '章') or contains(., '回') or contains(., '节'))]"

# =======================
# 主程序
# =======================
def convert_txt_to_epub(txt_path, epub_path):
    cmd = [
        CALIBRE_PATH,
        txt_path,
        epub_path,
        "--chapter", CHAPTER_XPATH,
        "--level1-toc", CHAPTER_XPATH,
        "--input-encoding", "utf-8",
        "--no-default-epub-cover",
        "--no-inline-toc",
        "--pretty-print"
    ]
    if COVER_FILE:
        cmd.extend(["--cover", COVER_FILE])

    # 调用命令
    subprocess.run(cmd, check=True)
    print(f"已生成: {epub_path}")

def main():
    # 遍历 TXT 文件
    for filename in os.listdir(TXT_FOLDER):
        if filename.lower().endswith(".txt"):
            txt_path = os.path.join(TXT_FOLDER, filename)
            epub_path = os.path.join(TXT_FOLDER, os.path.splitext(filename)[0] + ".epub")
            try:
                convert_txt_to_epub(txt_path, epub_path)
            except subprocess.CalledProcessError as e:
                print(f"转换失败: {filename}")
                print(e)

if __name__ == "__main__":
    main()
```

---

# ✅ **使用方法**

1. 确保安装 **Calibre** 并找到 `ebook-convert.exe` 路径，修改 `CALIBRE_PATH`
2. 把所有 TXT 小说放在同一文件夹
3. 可选：在同目录放置封面 `cover.jpg`，修改 `COVER_FILE = "cover.jpg"`
4. 保存脚本为 `convert_txt_to_epub.py`
5. 打开命令行，运行：

```bash
python convert_txt_to_epub.py
```

6. 脚本会自动把每个 TXT 转换成 EPUB，章节识别“第xxx章/回/节”，生成 TOC

---

# ⚡ **特点**

* 自动识别章节标题
* 保证中文 UTF-8 正确显示
* 支持批量处理
* 可选封面
* 输出 EPUB 文件结构清晰，可直接在 iBooks / Moon+ / KOReader / Kindle 查看

---

如果你需要，我还可以帮你加一个 **功能：自动清理 TXT 空行、去掉页眉页脚或广告**，让 EPUB 更整洁。

你希望我加吗？
