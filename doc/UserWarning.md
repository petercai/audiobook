You can globally suppress **torchaudio’s `deprecated()` warnings** the same way you suppress ordinary Python warnings, because `torchaudio.deprecation.deprecated()` ultimately emits a standard `UserWarning` or `FutureWarning`.

Here are the **three reliable global methods**:

---

# ✅ **Method 1 — Suppress torchaudio deprecation warnings in Python code**

```python
import warnings

# Suppress only torchaudio's deprecated warnings
warnings.filterwarnings(
    "ignore",
    category=UserWarning,
    module="torchaudio"
)
```

Place this **before** importing torchaudio modules.

If torchaudio uses `FutureWarning` instead, you can cover both:

```python
import warnings

warnings.filterwarnings("ignore", category=FutureWarning, module="torchaudio")
warnings.filterwarnings("ignore", category=UserWarning, module="torchaudio")
```

---

# ✅ **Method 2 — Suppress ALL warnings (not recommended)**

```python
import warnings
warnings.filterwarnings("ignore")
```

This hides everything — OK for scripts, not ideal for debugging.

---

# ✅ **Method 3 — Environment variable (global, no code change)**

Python supports a warnings filter via an environment variable:

### **Windows CMD / PowerShell**

```
set PYTHONWARNINGS=ignore::UserWarning:torchaudio
```

### **Linux / macOS**

```
export PYTHONWARNINGS="ignore::UserWarning:torchaudio"
```

You can add it to:

* PowerShell profile
* `.bashrc` / `.zshrc`
* VSCode launch.json `"env"` section
* PyCharm Run/Debug configuration

---

# 🔍 **Which warning category does `torchaudio.deprecated()` emit?**

Most `deprecated()` usages in torchaudio emit:

* `UserWarning` (common)
* or `FutureWarning` (less common)

If you want to cover all torchaudio warnings regardless of category:

```python
warnings.filterwarnings("ignore", module="torchaudio")
```

---

# ⭐ Recommended (safe + targeted)

```python
import warnings
warnings.filterwarnings("ignore", module="torchaudio")
```

This hides only warnings originating from the `torchaudio` package, without touching the rest of your program.

---

If you want, I can also show how to:

* suppress warnings only for a specific function / block
* redirect warnings to a logger
* suppress warnings when using `TorchCodec` or the new Streaming API

Just tell me!
