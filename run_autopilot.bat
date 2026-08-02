@echo off
:: Chạy CLARA-AGI ở chế độ tự học + tự nâng cấp tự động
:: Windows
cd /d "%~dp0"
echo 🧬 Khoi dong CLARA-AGI o che do autopilot...
echo    Tu hoc + tu nghien cuu web da bat.
echo    Nhan Ctrl+C de dung.
python3 main.py --auto-learn --self-improve %*
pause
