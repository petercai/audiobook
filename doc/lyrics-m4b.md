Here’s the **correct and practical way** to embed a transcript into an **M4B audiobook** as *lyrics* (LRC-like synchronized text) so that **music players** (Poweramp, GoneMAD, etc.) can display it.

⚠️ **Important:**
MP4/M4B **does not support native LRC** inside the container.
Instead, you must embed the transcript as **timed text (tx3g / mov_text)** subtitle tracks.

Music players that support "lyrics" usually treat **embedded timed text** as lyrics.

So the process is:

> **Transcript → SRT/VTT → embed into M4B as mov_text → readable as lyrics**

---

# ✅ OPTION 1 — *Best Method*: Embed as `mov_text` (tx3g subtitle)

Convert your transcript to **SRT** (or VTT).

Example `subs.srt`:

```
1
00:00:01,000 --> 00:00:05,000
第一章 青牛镇

2
00:00:06,000 --> 00:00:12,000
这是一个小城……
```

Then embed into M4B:

### **FFmpeg command**

```bash
ffmpeg -i book.m4b -i subs.srt -map 0 -map 1 -c copy -c:s mov_text output.m4b
```

What this does:

* Keeps audio untouched (`-c copy`)
* Converts SRT → tx3g (`-c:s mov_text`)
* Embeds subtitle track into the M4B container

Result:
✔ Most Android players (Poweramp, GoneMAD, VLC, etc.) show it as **embedded lyrics or captions**
✔ Totally standard & reliable
✔ No re-encoding of audio

---

# ✅ OPTION 2 — Convert true LRC → SRT → embed

If you already have an `.lrc` file:

Example LRC:

```
[00:01.00] 第一章 青牛镇
[00:06.00] 这是一个小城……
```

Convert LRC → SRT (I can give you a Python script if needed), then embed using the command above.

---

# ❌ Why you cannot embed raw .LRC inside M4B

The MP4 container supports:

* `©lyr` atom (lyrics tag) — **but only unsynced text**
* `mov_text` (tx3g) subtitles — **synced timed text**

Music players rarely support reading synced text from `©lyr`.

So if you need **synchronized lyrics**, use **mov_text subtitles**.

---

# 💡 OPTION 3 — Embed as unsynced lyrics (`©lyr` atom)

If your player supports viewing plain lyrics only (no sync), use:

```bash
ffmpeg -i book.m4b -metadata lyrics="your entire transcript here" -c copy output.m4b
```

But:

* ⚠️ No timestamps
* ⚠️ Not displayed as timed lyrics
* ✔ Works in some players (Poweramp, iTunes, etc.)

---

# 🔥 BEST RECOMMENDATION (for Android music players)

If your goal is:

### **“Show transcript synced while playing the M4B on a music player”**

Then do **this**:

1. Convert transcript → SRT
2. Embed as `mov_text` tx3g using ffmpeg
3. Use a player that supports timed captions:

   * Poweramp (shows embedded lyrics)
   * GoneMAD Music Player (supports embedded lyrics)
   * VLC
   * mpv
   * Smart Audiobook Player (partial)

This gives you **true synchronized on-screen text**, closest to LRC.

---

# If you want, I can generate:

### ✔ a Python script: `.lrc` → `.srt`

### ✔ a script: `.txt transcript` → timestamped SRT

### ✔ an ffmpeg one-liner specific to your M4B

### ✔ help figuring out which Android player shows embedded lyrics best

Just tell me which one you need.
