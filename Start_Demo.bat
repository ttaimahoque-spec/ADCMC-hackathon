@echo off
cd /d "%~dp0"
echo Open http://127.0.0.1:8000 after the ready message, then choose Open dashboard.
py run.py --demo-before
pause
