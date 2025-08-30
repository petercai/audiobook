
ffmpeg -i yunyi.mp3 -ar 24000 -ac 1 yunyi_24000.wav

### 🔹 Parts explained

* **`-i input.mp3`**
  The input file. Here it’s an MP3.

* **`-ar 16000`**
  Audio sample rate = **16,000 Hz (16 kHz)**.

  * Common for **speech recognition** (like Whisper, Google STT, Vosk).
  * Standard music files often use 44.1 kHz or 48 kHz.
  * Lowering to 16 kHz reduces file size and processing cost, but still keeps enough clarity for speech.

* **`-ac 1`**
  Audio channels = **1 (mono)**.

  * Stereo has 2 channels (left + right).
  * Mono combines them → smaller file, required by many STT models.

* **`output.wav`**
  The output file in **WAV format**.

  * WAV is uncompressed PCM audio, preferred for analysis, editing, and speech recognition.
