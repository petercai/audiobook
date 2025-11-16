#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
txt_to_epub_final.py

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
TXT_FOLDER = r".\txt"
END_OF_BOOK = "（完）"

CALIBRE_PATH = r"C:\Program Files\Calibre2\ebook-convert.exe"  # 或 "ebook-convert" (已加入 PATH)
ENCODING = "GB18030"   # 源 TXT 编码
COVER_CANDIDATES = ["cover.jpg", "cover.jpeg", "cover.png", "cover.webp"]
# 匹配章节标题（更宽松）：第123章 / 第 一百 二十 三 章 等
RE_CHAPTER = re.compile(r"^第[\u4e00-\u9fa5\d\s零一二三四五六七八九十百千万亿]+章.*$")

# ========== 帮助函数 ==========
def find_cover():
    for name in COVER_CANDIDATES:
        if os.path.exists(name):
            return name
    return None

def sanitize_text_for_html(s: str) -> str:
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
    for ln in lines[:20]:  # 仅检查前 20 行
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

# ========== 主转换逻辑 ==========
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
    html_blocks = []

    # 读取并解析
    with open(txt_path, "r", encoding=ENCODING, errors="ignore") as f:
        for raw in f:
            line = raw.rstrip("\n\r")
            stripped = line.strip()

            # 截断条件
            if line == END_OF_BOOK:
                stopped = True
                break

            # skip pure empty lines but preserve separation (we'll ignore multiple)
            if stripped == "":
                # we keep an explicit newline marker for sensible paragraphing
                if in_title:
                    lines_title_page.append("")
                else:
                    html_blocks.append({"type": "blank"})
                continue

            # 是否章节标题
            if RE_CHAPTER.match(stripped):
                # 标题行
                in_title = False
                chapters.append({"title": stripped, "paras": []})
            else:
                if in_title:
                    lines_title_page.append(stripped)
                else:
                    if not chapters:
                        # 如果出现正文但还没识别到章节（罕见），把到 title 改为正文第一个章节前内容
                        lines_title_page.append(stripped)
                    else:
                        chapters[-1]["paras"].append(stripped)

    # 如果没有章节（整个文档无“第...章”），把整个文本放到 title page 并当做单章处理
    if not chapters:
        # Treat whole file as single chapter under title page
        # title page is lines_title_page (all content)
        # create a dummy chapter "正文"
        if lines_title_page:
            chapters.append({"title": "正文", "paras": lines_title_page})
            lines_title_page = []

    # 生成 HTML
    with open(html_path, "w", encoding="utf-8") as out:
        out.write("<!doctype html>\n<html>\n<head>\n<meta charset='utf-8'/>\n")
        out.write("<title>%s</title>\n" % sanitize_text_for_html(Path(txt_path).stem))
        out.write("</head>\n<body>\n")

        # cover page as first page (visible) if cover exists -- also used as cover when passing --cover
        if cover:
            out.write('<div id="cover-page" style="text-align:center;margin-top:2em;">\n')
            out.write(f'<img src="{sanitize_text_for_html(cover)}" alt="cover" style="max-width:100%;height:auto;"/>\n')
            out.write("</div>\n")

        # title page: first-chapter之前的所有内容
        if lines_title_page:
            out.write('<section id="title-page">\n')
            out.write('<h1>作品信息</h1>\n')
            for ln in lines_title_page:
                if ln == "":
                    out.write("<p></p>\n")
                else:
                    out.write(f"<p>{sanitize_text_for_html(ln)}</p>\n")
            out.write("</section>\n")

        # chapters with auto ids
        for idx, ch in enumerate(chapters, start=1):
            ch_id = f"chapter-{idx:03d}"
            out.write(f'<h2 id="{ch_id}">{sanitize_text_for_html(ch["title"])}</h2>\n')
            for para in ch["paras"]:
                if para.strip() == "":
                    out.write("<p></p>\n")
                else:
                    out.write(f"<p>{sanitize_text_for_html(para)}</p>\n")

        out.write("</body>\n</html>\n")

    print(f"[HTML generated] {html_path} (chapters: {len(chapters)}, cover: {bool(cover)}, truncated: {stopped})")
    return lines_title_page, chapters, cover

def build_and_run_ebook_convert(html_file, epub_file, title=None, author=None, cover=None):
    """
    调用 ebook-convert 生成 epub，并传入 metadata、封面、chapter/toc 设置
    """
    cmd = [CALIBRE_PATH, html_file, epub_file,
           "--chapter", "//h2",
           "--level1-toc", "//h2",
           "--pretty-print",
           "--no-default-epub-cover"]

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
    # 简单策略：优先匹配 标题/书名 与 作者 字段；否则 title 使用文件名
    title, author = extract_title_author_from_lines(lines_title_page)
    if not title:
        title = default_title
    return title, author

# ========== 主程序 ==========
def main():
    # check calibre path exists
    if not shutil_which(CALIBRE_PATH):
        print(f"Error: ebook-convert not found at: {CALIBRE_PATH}")
        print("如果你已将 ebook-convert 加入 PATH，请把 CALIBRE_PATH 设为 'ebook-convert' 或完整路径。")
        return

    # 扫描所有 txt
    for filename in os.listdir(TXT_FOLDER):
        if not filename.lower().endswith(".txt"):
            continue
        txt = os.path.join(TXT_FOLDER, filename)
        html = os.path.join(TXT_FOLDER, os.path.splitext(filename)[0] + ".html")
        epub = os.path.join(TXT_FOLDER, os.path.splitext(filename)[0] + ".epub")

        lines_title_page, chapters, cover = txt_to_structured_html(txt, html)

        # metadata
        default_title = os.path.splitext(os.path.basename(txt))[0]
        title_meta, author_meta = auto_metadata_from_titlepage(lines_title_page, default_title)

        # If no author extracted, keep blank (ebook-convert will accept)
        cover_file = cover if cover else None

        build_and_run_ebook_convert(html, epub, title=title_meta, author=author_meta, cover=cover_file)

    print("全部完成。")

# ========== 小工具 ==========
def shutil_which(path):
    """
    如果给出的是可执行名（如 'ebook-convert'），尝试 PATH 查找；
    如果给出完整路径，则判断文件是否存在。
    """
    p = Path(path)
    if p.is_file():
        return str(p)
    # try PATH search
    from shutil import which
    return which(path)

# ========== 执行 ==========
if __name__ == "__main__":
    main()
