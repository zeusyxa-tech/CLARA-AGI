@echo off
REM Chạy CLARA với chế độ tự học khi rảnh — để mở treo cả ngày
cd /d "%~dp0"
echo.
echo ==============================================
echo   CLARA-AGI  -  CHE DO TU HOC KHI TREO MAY
echo ==============================================
echo.
python main.py --auto-learn %*
pause
