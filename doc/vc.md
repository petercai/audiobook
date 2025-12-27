# VC++ Compiler Error Troubleshooting

## Error
When running:
```bat
uv pip install --no-deps -e ../CosyVoice/third_party/Matcha-TTS
```
The following error occurs:
```text
error: Microsoft Visual C++ 14.0 or greater is required. Get it with "Microsoft C++ Build Tools": https://visualstudio.microsoft.com/visual-cpp-build-tools/
```

## Root Cause
1.  **Compiling from Source:** You are installing `matcha-tts` in editable mode (`-e`), which forces a local build of the package.
2.  **C Extension:** The package contains a C-extension (`matcha.utils.monotonic_align.core`) that must be compiled into a `.pyd` file.
3.  **Missing Environment:** Even if "Microsoft C++ Build Tools" are installed, the compiler (`cl.exe`) is not added to the global system `PATH` by default. The build system (`setuptools`) cannot find it in a standard command prompt.

## Solution

You do not need to modify the code. You must run the installation command in the correct environment where the compiler is accessible.

### Option 1: Use the Developer Command Prompt (Recommended)
1.  Click the Windows Start button.
2.  Search for **"x64 Native Tools Command Prompt for VS 2022"** (or your installed version).
3.  Open it.
4.  Navigate to your project folder:
    ```cmd
    cd c:\workspace\github\audiobook\ebook2audiobook
    ```
5.  Run the installation command again:
    ```cmd
    uv pip install --no-deps -e ../CosyVoice/third_party/Matcha-TTS
    ```

### Option 2: Verify Installation Workloads
If Option 1 fails, ensure the compiler libraries are actually installed:
1.  Open **Visual Studio Installer**.
2.  Click **Modify**.
3.  Ensure **"Desktop development with C++"** is checked.
4.  Ensure **"MSVC v143 - VS 2022 C++ x64/x86 build tools"** is checked.