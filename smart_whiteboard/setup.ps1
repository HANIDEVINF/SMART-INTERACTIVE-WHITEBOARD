# LuminaBoard - one-shot setup for Windows PowerShell.
# Usage (from the smart_whiteboard folder):   .\setup.ps1
# If PowerShell blocks the script:            Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "== 1/4  Looking for Python 3.14 ==" -ForegroundColor Cyan
$python = $null
try {
    $v = & py -3.14 --version 2>$null
    if ($LASTEXITCODE -eq 0) { $python = @("py", "-3.14"); Write-Host "Found: $v" }
} catch { }
if (-not $python) {
    $v = & python --version 2>&1
    Write-Host "Python 3.14 launcher entry not found. 'python' reports: $v" -ForegroundColor Yellow
    Write-Host "Install Python 3.14 from https://www.python.org/downloads/ (tick 'Add to PATH' and 'py launcher')." -ForegroundColor Yellow
    Write-Host "Continuing with 'python' - LuminaBoard works on Python 3.10+ as well." -ForegroundColor Yellow
    $python = @("python")
}

Write-Host "== 2/4  Creating virtual environment (.venv) ==" -ForegroundColor Cyan
if (-not (Test-Path ".venv")) { & $python[0] $python[1..($python.Length)] -m venv .venv }
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

Write-Host "== 3/4  Installing dependencies ==" -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements-dev.txt

Write-Host "== 4/4  Verifying ==" -ForegroundColor Cyan
& $venvPython -c "import sys, cv2, numpy, PIL, PySide6; print('Python', sys.version.split()[0], '| OpenCV', cv2.__version__, '| NumPy', numpy.__version__, '| Pillow', PIL.__version__, '| PySide6', PySide6.__version__)"
& $venvPython -m pytest tests -q
& $venvPython main.py --smoke

Write-Host ""
Write-Host "Setup complete. Start the application with:" -ForegroundColor Green
Write-Host "    .\.venv\Scripts\python.exe main.py" -ForegroundColor Green
