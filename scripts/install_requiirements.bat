@echo off

:: Set UTF-8 encoding
chcp 65001

:: Check for requirements.txt
IF NOT EXIST "requirements.txt" (
    echo requirements.txt not found!
    exit /b 1
)

:: Check for virtual environment
IF NOT EXIST "..\.venv" (
    echo Virtual environment not found, creating it...
    python -m venv ..\.venv
)

:: Activate virtual environment
call ..\.venv\Scripts\activate.bat

:: Install dependencies
pip install -r requirements.txt

:: Pause to keep window open
echo Virtual environment is active. Use 'deactivate' command to exit.
pause