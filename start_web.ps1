$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv/Scripts/python.exe")) {
    Write-Host "[OMR] Creating virtual environment..."
    py -m venv .venv
}

Write-Host "[OMR] Activating environment..."
. .\.venv\Scripts\Activate.ps1

Write-Host "[OMR] Installing requirements..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Write-Host "[OMR] Starting web service..."
python run_web.py

