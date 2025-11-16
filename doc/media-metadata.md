Good question. It’s a bit tricky to find a *perfect* free/open-source player that checks **all** your boxes (m4b/mp4 + “detailed media info” for video/audio/subtitles), but here are some of the best options + tools + trade-offs, plus my recommendation.

---

## ✅ Strong Open-Source / Free Players & Tools to View Info

Here are a few free or open-source players (or tools) that are very capable and can give you detailed media info. Depending on exactly what you mean by “viewer,” you may combine a media player + a metadata tool.

### **1. mpv**

* mpv is a powerful, free, open-source media player. ([mpv][1])
* It supports a very wide variety of file formats, including MP4. ([GitHub][2])
* **Viewing track information:** Pressing `i` (on many builds) brings up an OSD info panel that shows things like resolution, framerate, audio track, subtitle track, etc. (Though note: some users say newer builds may not show bitrate anymore. ([Reddit][3]))
* Pros: Very lightweight, very flexible, and scriptable.
* Cons: Minimal GUI — not super “friendly” if you want a rich media-info dialog like a more full-featured GUI player.

---

### **2. SMPlayer**

* SMPlayer is a GUI frontend for mpv and MPlayer. ([Wikipedia][4])
* It supports MP4 (and many other formats) “out of the box” via built-in codecs. ([SMPlayer][5])
* **Media info panel:** SMPlayer has a “Information and properties” dialog (View → Information) that shows file metadata including codecs, title, chapters, tracks, etc. ([Virtual Curiosities][6])
* It also supports subtitle tracks and switching audio tracks. ([UserBase][7])
* Pros: More “user friendly” than mpv for seeing track info, switching tracks, etc.
* Cons: Not super modern UI, but very practical.

---

### **3. Kodi**

* Kodi is a full-fledged media center, open-source, very powerful. ([Opensource.com][8])
* It supports embedded video tags in MP4 files. ([Kodi Wiki][9])
* While playing a file, you can press `i` (or use the “Information” icon) to see media info: video codec, audio tracks, subtitle streams, chapters, etc. ([Kodi Wiki][10])
* Pros: Very rich information, good for managing libraries, supports many subtitle formats. ([Kodi Wiki][11])
* Cons: Heavier than a simple player; more setup, more UI.

---

### **4. MediaInfo**

* Although not a “player,” **MediaInfo** is exactly designed to show detailed media file technical metadata. ([Wikipedia][12])
* It’s open-source, cross-platform (including Android). ([Wikipedia][12])
* MediaInfo shows: general info (title, duration, chapters), video codec, bitrate, frame rate; audio tracks (codec, channels, language); subtitle tracks. ([Wikipedia][12])
* Pros: Very detailed; perfect for inspecting files even if you use another player to play them.
* Cons: It’s not a “player” — just an info tool.

---

### **5. ExifTool**

* **ExifTool** is a metadata tool that works on many file types. ([Wikipedia][13])
* It can read (and write) metadata in MP4/M4B files (tags, chapters, cover art, etc.) using command line.
* Pros: Extremely powerful and flexible, very detailed metadata access.
* Cons: Command-line, not a media player.

---

## 💡 My Recommendation

If I were in your shoes and needed both **playback + media info**, I’d probably use a combo:

* **SMPlayer** (or **mpv**) for playback — because they’re lightweight and open-source.
* **MediaInfo** for inspecting file structure, codecs, tracks, chapters, subtitle streams, etc.

If you prefer a **single app** that *does both playback + good info view*:

* Go with **Kodi** — it's more heavyweight, but its “Information” screen during playback is very feature-rich.

---

If you tell me **which platform** you're on (Windows? Linux? Android?) I can pick the very best open-source players for **that system**. Do you want me to do that?

[1]: https://mpv.io/?utm_source=chatgpt.com "mpv.io"
[2]: https://github.com/mpv-player/mpv?utm_source=chatgpt.com "GitHub - mpv-player/mpv: 🎥 Command line media player"
[3]: https://www.reddit.com/r/mpv/comments/1h3m0i6?utm_source=chatgpt.com "Video bitrate not shown anymore in new version of mpv"
[4]: https://en.wikipedia.org/wiki/SMPlayer?utm_source=chatgpt.com "SMPlayer"
[5]: https://www.smplayer.info/en/info2?utm_source=chatgpt.com "SMPlayer - Free Media Player for Windows and Linux - Official site"
[6]: https://www.virtualcuriosities.com/articles/5059/my-review-of-smplayer?utm_source=chatgpt.com "My Review of SMPlayer - Virtual Curiosities"
[7]: https://userbase.kde.org/SMPlayer/en?utm_source=chatgpt.com "SMPlayer - KDE UserBase Wiki"
[8]: https://opensource.com/sites/default/files/articles/kodi_media_guide.pdf?utm_source=chatgpt.com ". . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . Manage Your Media With Kodi"
[9]: https://kodi.wiki/view/Video_file_tagging?utm_source=chatgpt.com "Video file tagging - Official Kodi Wiki"
[10]: https://kodi.wiki/view/Video_playback?utm_source=chatgpt.com "Video playback - Official Kodi Wiki"
[11]: https://kodi.wiki/view/Subtitles?utm_source=chatgpt.com "Subtitles - Official Kodi Wiki"
[12]: https://en.wikipedia.org/wiki/MediaInfo?utm_source=chatgpt.com "MediaInfo"
[13]: https://en.wikipedia.org/wiki/ExifTool?utm_source=chatgpt.com "ExifTool"
