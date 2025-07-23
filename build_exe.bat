@echo off
REM Build GUI application into a single portable EXE using PyInstaller
REM ---------------------------------------------------------------
REM Prerequisites:
REM   1) Activate the virtual environment where dependencies are installed
REM   2) pip install pyinstaller
REM ---------------------------------------------------------------

pyinstaller --noconfirm --onefile --windowed ^
    --add-data "font;font" ^
    --add-data "insert_image;insert_image" ^
    --add-data "reciept_format;reciept_format" ^
    --hidden-import=gpt_receipt_ocr_250721 ^
    --hidden-import=gemini_receipt_ocr_250722 ^
    --icon "insert_image/icon.png" ^
    gui_250722.py

echo.
echo Build complete. You can find the executable in the dist folder. 