@echo off
REM This script downloads the facebook/w2v-bert-2.0 model from Hugging Face.

echo Checking for huggingface-cli...
hf version >nul 2>&1
if %errorlevel% neq 0 (
    echo huggingface-cli is not found.
    echo Please install it first. The project recommends using uv:
    echo.
    echo   uv tool install "huggingface-hub[cli,hf_xet]"
    echo.
    echo After installation, ensure the tool's bin directory is in your system's PATH.
    goto :eof
)

set "MODEL_DIR=models\facebook\w2v-bert-2.0"

echo Creating model directory: %MODEL_DIR%
mkdir %MODEL_DIR%

echo ---
echo Downloading facebook/w2v-bert-2.0 model...
hf download facebook/w2v-bert-2.0 --local-dir=%MODEL_DIR%

echo ---
echo Model facebook/w2v-bert-2.0 has been downloaded to the '%MODEL_DIR%' directory.
@echo off


REM This script downloads the facebook/w2v-bert-2.0 model from Hugging Face.

hf download facebook/w2v-bert-2.0 --local-dir=models\tts\facebook\w2v-bert-2.0

@REM amphion/MaskGCT
hf download amphion/MaskGCT --local-dir=models\tts\amphion\MaskGCT
hf download funasr/campplus --local-dir=models\tts\funasr\campplus
hf download nvidia/bigvgan_v2_22khz_80band_256x --local-dir=models\tts\nvidia\bigvgan_v2_22khz_80band_256x