import os
import re
import subprocess


# ================================
# 配置
# ================================
# TXT 小说所在文件夹（当前目录）
TXT_FOLDER = r".\txt"

ENCODING = "GB18030"
CALIBRE = r"C:\Program Files\Calibre2\ebook-convert.exe"

# 匹配章节，例如：第100章 天地开辟
RE_CHAPTER = re.compile(r"^第[\u4e00-\u9fa5\d]+章.*$")
END_OF_BOOK = "（完）"

# 允许的封面文件名
COVER_CANDIDATES = ["cover.jpg", "cover.jpeg", "cover.png", "cover.webp"]


def find_cover_file():
    """检测当前目录是否有封面文件"""
    for f in COVER_CANDIDATES:
        if os.path.exists(f):
            return f
    return None


def generate_cover_html(cover_file):
    """生成 cover.html，用 <img> 嵌入封面"""
    cover_html = "cover.html"
    with open(cover_html, "w", encoding="utf-8") as f:
        f.write(
            "<html><head><meta charset='utf-8'></head>"
            "<body style='margin:0;padding:0;text-align:center;'>"
            f"<img src='{cover_file}' alt='cover' style='max-width:100%;height:auto;'>"
            "</body></html>"
        )
    return cover_html


def txt_to_html(txt_file, html_file):
    """TXT 转 HTML，含 title page、章节、截断（完）"""

    html = []
    html.append("<html><head><meta charset='utf-8'></head><body>\n")

    title_page = []
    in_title_page = True

    with open(txt_file, "r", encoding=ENCODING, errors="ignore") as f:
        for raw in f:
            line = raw.strip()

            if line == END_OF_BOOK:
                break

            if not line:
                continue

            # 章节开头
            if RE_CHAPTER.match(line):

                # 输出 title page
                if in_title_page:
                    html.append("<h1>作品信息</h1>\n")
                    for t in title_page:
                        html.append(f"<p>{t}</p>\n")
                    in_title_page = False

                html.append(f"<h2>{line}</h2>\n")
            else:
                if in_title_page:
                    title_page.append(line)
                else:
                    html.append(f"<p>{line}</p>\n")

    html.append("</body></html>")

    with open(html_file, "w", encoding="utf-8") as f:
        f.writelines(html)

    print(f"[HTML] 生成 {html_file}")


def html_to_epub(html_file, epub_file, cover_file=None, cover_html=None):
    """调用 Calibre 转 EPUB"""

    cmd = [
        CALIBRE, html_file, epub_file,
        "--chapter", "//h2",
        "--level1-toc", "//h2",
        "--toc-title", "目录",
        "--pretty-print"
    ]

    # 如果有封面
    if cover_file:
        print(f"[COVER] 使用封面：{cover_file}")
        cmd += ["--cover", cover_file]

        # 把 cover.html 加入到转换资源里（Calibre 会自动打包）
        cmd += ["--extra-css", ""]  # 占位参数让我们能插入文件

    subprocess.run(cmd, check=True)
    print(f"[EPUB] 已输出 {epub_file}")


def main():
    # 检查封面
    cover_file = find_cover_file()
    cover_html = None

    if cover_file:
        cover_html = generate_cover_html(cover_file)

    # 扫描所有 txt
    for filename in os.listdir(TXT_FOLDER):
        if filename.lower().endswith(".txt"):
            txt = os.path.join(TXT_FOLDER, filename)
            html = os.path.join(TXT_FOLDER, os.path.splitext(filename)[0] + ".html")
            epub = os.path.join(TXT_FOLDER, os.path.splitext(filename)[0] + ".epub")

            txt_to_html(txt, html)
            html_to_epub(html, epub, cover_file=cover_file, cover_html=cover_html)

    print("\n全部完成!")


if __name__ == "__main__":
    main()
