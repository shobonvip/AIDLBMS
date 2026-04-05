@echo off
echo Installing Requirements
pip install -r requirements.txt
echo Installing Chromium
playwright install chromium
echo Setup Completed!
pause