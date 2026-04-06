@echo off
echo Installing Requirements
python -m pip install -r requirements.txt
echo Installing Chromium
python -m playwright install chromium
echo Setup Completed!
pause