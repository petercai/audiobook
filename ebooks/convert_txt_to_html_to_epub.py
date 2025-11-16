#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
txt_to_epub_with_nav.py
功能：
- 把 GB18030 编码的 TXT 转成结构化 HTML（可调试）
- title page（第1章之前的内容）提取并写入 <h1>
- 封面检测（cover.jpg / cover.png / ...），生成封面页并作为 epub 封面
- 遇到单独一行 "（完）" 后截断余下内容
- 将每章写为 <h2 id="chapter-001"> 并自动编号
- 从 title page 尝试提取 标题 与 作者，并作为 metadata 传给 ebook-convert
- 调用 Calibre 的 ebook-convert，使用 --chapter 和 --level1-toc 基于 //h2 生成 TOC

注意：
- 需先安装 Calibre，并设置 CALIBRE_PATH 为 ebook-convert.exe 的路径（Windows）
- TXT 推荐为 GB18030 编码（可改 ENCODING）

改进点：
- 在生成的 HTML 中显式插入 <nav epub:type="toc"> 列表（基于 <h2 id="chapter-###">）
- 这样 Calibre 会把 nav.xhtml/ncx 正确生成，EPUB 阅读器显示目录更可靠
- 仍支持封面、title page、（完）截断、自动编号章节、自动 metadata
"""

import os
import re
import subprocess
import html
from pathlib import Path

# ================================
# 配置
# ================================
# TXT 小说所在文件夹（当前目录）
TXT_FOLDER = r".\ebooks\txt"
END_OF_BOOK = "（完）"

CALIBRE_PATH = r"C:\Program Files\Calibre2\ebook-convert.exe"  # 或 "ebook-convert"（已在 PATH）
ENCODING = "GB18030"
COVER_CANDIDATES = ["cover.jpg", "cover.jpeg", "cover.png", "cover.webp"]
# 匹配章节标题（更宽松）：第123章 / 第 一百 二十 三 章 等
RE_CHAPTER = re.compile(r"^第[\u4e00-\u9fa5\d\s零一二三四五六七八九十百千万亿]+章.*$")

# ========== 帮助函数 ==========
def find_cover():
    for name in COVER_CANDIDATES:
        if os.path.exists(name):
            return name
    return None

def esc(s):
    return html.escape(s)

def extract_title_author_from_lines(lines):
    """
    从 title_page 行列表中尝试提取 title / author：
    支持常见格式：
      标题：xxx
      书名：xxx
      作者：xxx
      Author: xxx
    如果无法提取，会用文件名作为 title，author 留空。
    """
    title = None
    author = None
    for ln in lines[:30]:
        s = ln.strip()
        if not s:
            continue
        # 常见中文字段
        m = re.match(r"^(?:书名|标题|名[称]?)[:：\s]\s*(.+)$", s)
        if m and not title:
            title = m.group(1).strip()
            continue
        m = re.match(r"^(?:作者|著者|作[者]?)[:：\s]\s*(.+)$", s)
        if m and not author:
            author = m.group(1).strip()
            continue
        # 英文
        m = re.match(r"^Title[:\s]\s*(.+)$", s, flags=re.I)
        if m and not title:
            title = m.group(1).strip()
            continue
        m = re.match(r"^Author[:\s]\s*(.+)$", s, flags=re.I)
        if m and not author:
            author = m.group(1).strip()
            continue
    return title, author

# ========== 核心：TXT -> HTML（含 nav） ==========
def txt_to_structured_html(txt_path, html_path):
    """
    把 TXT 读入并生成单个 HTML：
    - 封面页（如存在）
    - title page（第1章之前的所有文本）
    - chapters：每个章写为 <h2 id="chapter-###"> 标题
    - 段落 <p> 用于正文
    """
    cover = find_cover()
    lines_title_page = []
    in_title = True
    stopped = False
    chapters = []

    # 读取原文
    with open(txt_path, "r", encoding=ENCODING, errors="ignore") as f:
        for raw in f:
            line = raw.rstrip("\r\n")
            stripped = line.strip()

            # 截断条件
            if line == END_OF_BOOK:
                stopped = True
                break

            # 保留空行为段落分隔（在 title page/paras 里用空串处理）
            if stripped == "":
                if in_title:
                    lines_title_page.append("")
                else:
                    # 表示段落间隔
                    if chapters:
                        chapters[-1]["paras"].append("")
                    else:
                        lines_title_page.append("")
                continue

            if RE_CHAPTER.match(stripped):
                in_title = False
                chapters.append({"title": stripped, "paras": []})
            else:
                if in_title:
                    lines_title_page.append(stripped)
                else:
                    if not chapters:
                        # 若正文出现但尚未命中章名，则作为 title page 内容（备用）
                        lines_title_page.append(stripped)
                    else:
                        chapters[-1]["paras"].append(stripped)

    # 若从未识别出章节，把全文当成一章（避免空 toc）
    if not chapters:
        chapters.append({"title": "正文", "paras": lines_title_page.copy()})
        lines_title_page = []

    # 生成 HTML：包含 cover, title-page, nav, chapters（每章 id 固定）
    with open(html_path, "w", encoding="utf-8") as out:
        out.write("<!doctype html>\n<html lang='zh-CN'>\n<head>\n<meta charset='utf-8'/>\n")
        out.write(f"<title>{esc(Path(txt_path).stem)}</title>\n")
        # small css to make toc page visible
        out.write("<style>body{font-family:serif;line-height:1.7;padding:1em;} nav#toc{margin-bottom:1.5em;} nav#toc ol{list-style:decimal;padding-left:1.2em;} #cover-page img{max-width:100%;height:auto;}</style>\n")
        out.write("</head>\n<body>\n")

        # cover page (visible) if exists
        if cover:
            out.write('<div id="cover-page" role="doc-cover" style="text-align:center;margin:1em 0;">\n')
            out.write(f'<img src="{esc(cover)}" alt="cover"/>\n')
            out.write("</div>\n")

        # title page
        if lines_title_page:
            out.write('<section id="title-page" epub:type="titlepage">\n')
            out.write('<h1>作品信息</h1>\n')
            for ln in lines_title_page:
                if ln == "":
                    out.write("<p></p>\n")
                else:
                    out.write(f"<p>{esc(ln)}</p>\n")
            out.write("</section>\n")

        # 生成 nav（TOC）——基于我们已识别的 chapters 列表
        out.write('<nav epub:type="toc" id="toc" role="doc-toc">\n')
        out.write('<h2>目录</h2>\n')
        out.write('<ol>\n')
        for idx, ch in enumerate(chapters, start=1):
            ch_id = f"chapter-{idx:03d}"
            out.write(f'  <li><a href="#{ch_id}">{esc(ch["title"])}</a></li>\n')
        out.write('</ol>\n')
        out.write('</nav>\n')

        # 正文章节（h2 带 id）
        for idx, ch in enumerate(chapters, start=1):
            ch_id = f"chapter-{idx:03d}"
            out.write(f'<h2 id="{ch_id}">{esc(ch["title"])}</h2>\n')
            for para in ch["paras"]:
                if para.strip() == "":
                    out.write("<p></p>\n")
                else:
                    out.write(f"<p>{esc(para)}</p>\n")

        out.write("</body>\n</html>\n")

    print(f"[HTML generated] {html_path} (chapters: {len(chapters)}, cover: {bool(cover)}, truncated: {stopped})")
    return lines_title_page, chapters, cover

# ========== 调用 ebook-convert ==========
def build_and_run_ebook_convert(html_file, epub_file, title=None, author=None, cover=None):
    cmd = [CALIBRE_PATH, html_file, epub_file,
           "--pretty-print",
           "--duplicate-links-in-toc",
           "--epub-version", "3",
           "--max-toc-links", "0",
           "--no-default-epub-cover"]
    # 我们不强制 --level1-toc，使用内嵌 nav 更可靠
    if title:
        cmd += ["--title", title]
    if author:
        cmd += ["--authors", author]
    if cover:
        cmd += ["--cover", cover]

    print("[run] " + " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"[EPUB generated] {epub_file}")

def auto_metadata_from_titlepage(lines_title_page, default_title):
    title, author = extract_title_author_from_lines(lines_title_page)
    if not title:
        title = default_title
    return title, author

# ========== 小工具 ==========
def shutil_which(path):
    p = Path(path)
    if p.is_file():
        return str(p)
    from shutil import which
    return which(path)

# ========== 主程序 ==========
def main():
    # 校验 ebook-convert
    if not shutil_which(CALIBRE_PATH):
        print(f"ebook-convert not found at: {CALIBRE_PATH}")
        print("请把 CALIBRE_PATH 设置为正确路径，或设置为 'ebook-convert'（加入 PATH）")
        return

    # 扫描所有 txt
    for filename in os.listdir(TXT_FOLDER):
        if not filename.lower().endswith(".txt"):
            continue
        txt = os.path.join(TXT_FOLDER, filename)
        html = os.path.join(TXT_FOLDER, os.path.splitext(filename)[0] + ".html")
        epub = os.path.join(TXT_FOLDER, os.path.splitext(filename)[0] + ".epub")

        lines_title_page, chapters, cover = txt_to_structured_html(txt, html)
        default_title = os.path.splitext(os.path.basename(txt))[0]
        title_meta, author_meta = auto_metadata_from_titlepage(lines_title_page, default_title)
        cover_file = cover if cover else None

        build_and_run_ebook_convert(html, epub, title=title_meta, author=author_meta, cover=cover_file)

    print("全部完成。")

if __name__ == "__main__":
    main()
