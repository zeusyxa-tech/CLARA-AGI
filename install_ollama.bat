@echo off
REM Windows: cài Ollama và pull model tự động
echo 🧬 CLARA-AGI - Cai dat Ollama (Windows)
echo ==============================================
where ollama >nul 2>nul
if %ERRORLEVEL%==0 (
    echo ✅ Ollama da co:
    ollama --version
) else (
    echo 📥 Mo trang tai Ollama...
    start https://ollama.com/download/windows
    echo.
    echo ⚠️  Hay cai dat Ollama bang file vua tai xong, sau do dong va mo lai
    echo    cmd chay lai file nay de pull model.
    pause
    exit /b
)

echo.
set /p MODEL="Model nao? [0.5b | 1.5b | 3b] (mac dinh 1.5b): "
if "%MODEL%"=="" set MODEL=1.5b
if "%MODEL%"=="0.5b" set M=qwen2.5:0.5b
if "%MODEL%"=="1.5b" set M=qwen2.5:1.5b
if "%MODEL%"=="3b"   set M=qwen2.5:3b
echo.
echo 📥 Dang pull %M%...
ollama pull %M%
echo.
echo ✅ Xong! Chay CLARA:  run.bat
pause
