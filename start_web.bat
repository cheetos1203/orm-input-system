@echo off
setlocal

if not exist ".venv\Scripts\python.exe" (
  echo [OMR] Creating virtual environment...
  py -m venv .venv
)

echo [OMR] Activating environment...
call .venv\Scripts\activate

echo [OMR] Installing requirements...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo [OMR] Starting web service...
python run_web.py

endlocal

