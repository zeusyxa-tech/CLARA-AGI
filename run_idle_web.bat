@echo off
cd /d "%~dp0"
pip install flask -q
python main.py --web --auto-learn %*
pause
