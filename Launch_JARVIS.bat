@echo off
echo ============================================
echo   JARVIS Desktop App - Starting...
echo ============================================
echo.

cd /d "%~dp0jarvis-ui"

echo [1/2] Starting Electron app (backend + frontend)...
call npm run electron:dev

echo.
echo JARVIS has been shut down.
pause
