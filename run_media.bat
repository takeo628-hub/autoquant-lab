@echo off
cd /d C:\Users\yukur\auto_media
C:\Users\yukur\investment_advisor\venv\Scripts\python.exe -X utf8 generator.py --daily --push >> media.log 2>&1
