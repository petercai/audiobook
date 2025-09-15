@REM To configure **Poetry** to always create the virtual environment in the current folder as `.venv`,
poetry config virtualenvs.in-project true --local

@REM You can specify a full path to the Python interpreter:
poetry env use /full/path/to/python


@REM which tells Poetry to use the currently active Python environment
poetry config virtualenvs.prefer-active-python true --local


@REM If you want to revert to the default system Python behavior, you can run:
poetry env use system


@REM ### 1. **List All Poetry Virtual Environments**
poetry env list

@REM ### 2. **Show Full Path of the Active Virtual Environment**
poetry env info
@REM This will display details like:
@REM - Path to the virtual environment
@REM - Python version used
@REM - Whether the environment is currently activated

@REM ### 3. **Get Only the Virtual Environment Path**
poetry env info --path


python app.py --share


python app.py --headless --ebook ebooks/god-c1.txt --language zh-cn --voice zho/adult/male/yunyang_24000.wav --output_dir audiobook_output