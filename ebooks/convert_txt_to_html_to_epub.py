import os
import re
import subprocess

# ================================
# 配置
# ================================

ENCODING = "GB18030"
CALIBRE = r"C:\Program Files\Calibre2\ebook-convert.exe"
CHAPTER_REGEX = re.compile(r"^第[\u4e00-\u9fa5\d]+章.*$")
# TXT 小说所在文件夹（当前目录）
TXT_FOLDER = r".\txt\test"

def txt_to_html(txt_file, html_file):
    """把 TXT 转成结构化 HTML，章节变 h2。"""

    html_lines = [
        "<html>\n<head>\n<meta charset='utf-8'>\n</head>\n<body>\n"
    ]

    with open(txt_file, "r", encoding=ENCODING, errors="ignore") as f:
        for line in f:
            s = line.strip()

            if not s:
                continue

            # 匹配 第XX章
            if CHAPTER_REGEX.match(s):
                html_lines.append(f"<h2>{s}</h2>\n")
            else:
                html_lines.append(f"<p>{s}</p>\n")

    html_lines.append("</body>\n</html>")

    with open(html_file, "w", encoding="utf-8") as f:
        f.writelines(html_lines)

    print(f"[HTML GENERATED] {html_file}")


def html_to_epub(html_file, epub_file):
    """用 Calibre 把 HTML 转 EPUB"""

    cmd = [
        CALIBRE, html_file, epub_file,
        "--chapter", "//h2",
        "--level1-toc", "//h2",
        "--no-default-epub-cover",
        "--pretty-print"
    ]

    subprocess.run(cmd, check=True)
    print(f"[EPUB GENERATED] {epub_file}")


def main():
    # for file in os.listdir("."):
    #     if file.endswith(".txt"):
    #         txt = file
    #         html = file + ".html"
    #         epub = file.replace(".txt", ".epub")
    #
    #         txt_to_html(txt, html)
    #         html_to_epub(html, epub)
    for filename in os.listdir(TXT_FOLDER):
        if filename.lower().endswith(".txt"):
            txt = os.path.join(TXT_FOLDER, filename)
            html = os.path.join(TXT_FOLDER, os.path.splitext(filename)[0] + ".html")
            epub = os.path.join(TXT_FOLDER, os.path.splitext(filename)[0] + ".epub")

            txt_to_html(txt, html)
            html_to_epub(html, epub)

    print("\n全部处理完成！")


if __name__ == "__main__":
    main()
