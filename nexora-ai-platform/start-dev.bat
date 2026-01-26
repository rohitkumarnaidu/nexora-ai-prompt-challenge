@echo off
echo Starting Nexora AI Platform Development Environment
echo.

echo Installing frontend dependencies...
cd frontend
call npm install
if %errorlevel% neq 0 (
    echo Failed to install frontend dependencies
    pause
    exit /b 1
)

echo.
echo Starting development servers...
echo Frontend will be available at: http://localhost:3000
echo Backend API will be available at: http://localhost:8001
echo API Documentation will be available at: http://localhost:8001/docs
echo.

:: Start backend server in background with virtual environment
start "Nexora Backend" cmd /k "cd .. && venv\Scripts\activate.bat && python src/dev_server.py"

:: Wait a moment for backend to start
timeout /t 3 /nobreak > nul

:: Start frontend server
start "Nexora Frontend" cmd /k "npm run dev"

echo.
echo Both servers are starting...
echo Press any key to open the application in your browser
pause > nul

:: Open browser
start http://localhost:3000

echo.
echo Development environment is running!
echo Close this window or press Ctrl+C to stop the servers
pause