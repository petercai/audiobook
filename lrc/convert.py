import re

def vtt_to_lrc(vtt_path, lrc_path):
    with open(vtt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    lrc_lines = []
    time_pattern = re.compile(r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})")

    for line in lines:
        match = time_pattern.search(line)
        if match:
            h, m, s, ms = match.groups()
            total_seconds = int(h) * 3600 + int(m) * 60 + int(s)
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            hundredths = int(ms) // 10
            timestamp = f"[{minutes:02d}:{seconds:02d}.{hundredths:02d}]"
            continue
        elif line.strip() and not line.startswith("WEBVTT"):
            lrc_lines.append(timestamp + " " + line.strip())

    with open(lrc_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lrc_lines))

# Example usage
vtt_to_lrc("chapter_1.vtt", "chapter_1.lrc")
