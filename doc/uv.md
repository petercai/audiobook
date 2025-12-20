# matcha-tts

**you want `matcha-tts` listed in `pyproject.toml`, but you *do NOT* want uv to install any of its dependencies** (because it brings GPU‑only packages like `onnxruntime-gpu`, which break on macOS arm64).

This *is* possible with `uv`, but **not through `uv add`**, because:

> **`uv add` always resolves dependencies.  
> There is no `--no-deps` mode for it.**

However — we can do it cleanly using `uv add --no-sync` + controlling when resolution happens.

***

# ✅ The cleanest method (works 100% with uv)

## **Step 1 — Add matcha-tts *only* to pyproject.toml (no install yet)**

```bash
uv add matcha-tts --no-sync
```

This updates `pyproject.toml` but **does not install anything**  
→ No dependencies are resolved yet.

***

## **Step 2 — Lock WITHOUT updating dependencies**

```bash
uv lock --no-update-dependencies
```

This prevents uv from pulling in dependencies of `matcha-tts` during the lock.

***

## **Step 3 — Sync (will install only what’s resolvable without deps)**

```bash
uv sync
```

If you haven't added any other packages that require dependency resolution, `uv` will **not install matcha-tts’s transitive deps**.

***

# 🔥 Even simpler: manually edit `pyproject.toml`

You can also **just add it manually** and avoid uv resolution entirely:

### Add to `pyproject.toml`

```toml
[project]
dependencies = [
    "matcha-tts",
]
```

Then run:

```bash
uv sync --no-install  # only validates structure, does not install deps
```

Or just leave it until you're ready to deal with deps.

***

# 🧠 If you want to **install matcha-tts itself but no deps**

`uv add` cannot do this.  
But **uv pip can**, because it supports pip flags:

```bash
uv pip install --no-deps matcha-tts
```

This will install the package, but none of its dependencies.

***

# 🛑 Why `uv add` cannot skip deps

Per uv design:

*   `uv add` edits `pyproject.toml` **and** resolves all dependencies.
*   There is **no `--no-deps`** flag.
*   Only `uv pip install --no-deps` behaves like pip.

So the correct pattern is:

*   **Use `uv add --no-sync`** to edit `pyproject.toml` without installing.
*   **Never run `uv sync` unless you're okay with failed deps** (or have constraints/platform markers).

***

# ⭐ Bonus: If matcha-tts depends on GPU-only deps (likely)

To avoid failing builds on macOS arm64, add override markers:

### Add to `pyproject.toml`

```toml
[tool.uv.overrides]
"onnxruntime-gpu" = { markers = "false" }
```

Or replace with CPU version:

```toml
[tool.uv.overrides]
"onnxruntime-gpu" = { version = "0", markers = "sys_platform == 'darwin' and platform_machine == 'arm64'" }
"onnxruntime" = { version = ">=1.18,<1.24", markers = "sys_platform == 'darwin' and platform_machine == 'arm64'" }
```

***

# ✔️ TL;DR — The simplest answer

### **To add matcha-tts to pyproject.toml without installing any deps:**

```bash
uv add matcha-tts --no-sync
uv lock --no-update-dependencies
```

# cosyvoice

Here’s the **correct, uv‑compatible way** to add **cosyvoice** to your `pyproject.toml` **while excluding its dependency on `onnxruntime-gpu`**, which breaks on macOS ARM64.

This works 100% with **uv**, and avoids the dependency resolution errors you’ve been running into.

***

# ✅ Goal

*   Add `cosyvoice` to `pyproject.toml`
*   **Prevent uv from installing `onnxruntime-gpu`**
*   Allow macOS ARM64 to use CPU `onnxruntime` instead (optional but recommended)

***

# ✅ The exact `pyproject.toml` entries you need

## **1. Add cosyvoice normally**

Inside `[project]`:

```toml
[project]
dependencies = [
    "cosyvoice",
    "onnxruntime>=1.18,<1.24 ; sys_platform == 'darwin' and platform_machine == 'arm64'"
]
```

## **2. Override to block `onnxruntime-gpu`**

Add this section:

```toml
[tool.uv.overrides]
onnxruntime-gpu = { markers = "false" }
```

This tells uv:

> **Pretend `onnxruntime-gpu` is never valid on any platform.**

So uv will not try to install it — even if cosyvoice declares it.

***

# 💡 Optional: Only block on macOS ARM64

If you want Linux/Windows CI to still use GPU:

```toml
[tool.uv.overrides]
onnxruntime-gpu = { version = "0", markers = "sys_platform == 'darwin' and platform_machine == 'arm64'" }
```

This results in:

*   macOS ARM64 → `onnxruntime-gpu` skipped
*   Linux x86\_64 / Windows → GPU runtime allowed

***

# ✅ Apply changes with uv

```bash
uv lock --no-update-dependencies
uv sync
```

These ensure your overrides are respected.

***

# 🔥 Alternative: Add cosyvoice without resolving its deps

```bash
uv add cosyvoice --no-sync
uv lock --no-update-dependencies
uv sync
```

Then apply the overrides above.

***

# 🧪 Want me to generate a complete working `pyproject.toml` for your project

(including overrides for CosyVoice, Matcha‑TTS, pytorch, audio deps, etc.)?  
Just paste your current file and I’ll patch it cleanly.
