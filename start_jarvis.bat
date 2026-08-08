@echo off
echo =========================================
echo       JARVIS System Startup Script
echo =========================================

echo [1] Checking MongoDB Service...
net start MongoDB 2>nul
if %errorlevel% neq 0 (
    echo [INFO] MongoDB service is already running, or not installed as a Windows service.
    echo If MongoDB is installed manually, please ensure 'mongod' is running.
) else (
    echo [OK] MongoDB started.
)

echo.
echo [2] Checking ChromaDB...
echo [OK] ChromaDB is embedded. No separate server required.

echo.
echo [3] Starting JARVIS API Server...
python -m uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
