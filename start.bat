@echo off
echo.
echo  ============================================
echo   PromptGuard -- One-Click Setup
echo  ============================================
echo.

REM ── Backend setup ──────────────────────────────────────────────
echo [1/4] Installing Python dependencies...
cd /d "%~dp0backend"
pip install -r requirements.txt
if errorlevel 1 (echo ERROR: pip install failed && pause && exit /b 1)

echo.
echo [2/4] Training ML model...
python -m models.train
if errorlevel 1 (echo WARNING: Training failed -- will use rule-only mode)

echo.
echo [3/4] Installing frontend dependencies...
cd /d "%~dp0frontend"
call npm install
if errorlevel 1 (echo ERROR: npm install failed && pause && exit /b 1)

echo.
echo [4/4] Starting servers...
echo.
echo  Backend:   http://localhost:8000
echo  Frontend:  http://localhost:5173
echo  API Docs:  http://localhost:8000/docs
echo.

REM Start backend in new terminal
start "PromptGuard Backend" cmd /k "cd /d "%~dp0backend" && uvicorn main:app --reload --port 8000"

REM Give backend 3 seconds to start
timeout /t 3 /nobreak >nul

REM Start frontend in new terminal
start "PromptGuard Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo  Both servers launched!
echo  Open http://localhost:5173 in your browser.
echo.
pause
