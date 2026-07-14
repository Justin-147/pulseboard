$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$executables = @(
    (Join-Path $root "PulseBoard.exe"),
    (Join-Path $root "dist\PulseBoard.exe")
)
$executable = $executables | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$venv = Join-Path $root ".venv"
$python = Join-Path $venv "Scripts\python.exe"
$pythonw = Join-Path $venv "Scripts\pythonw.exe"

if ($executable) {
    Start-Process -FilePath $executable -WorkingDirectory $root
    exit 0
}

if (-not (Test-Path $python)) {
    Write-Host "First run: preparing PulseBoard..."
    python -m venv $venv
}

$savedErrorPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $python -c "import psutil, tkinter" 2>$null
$dependencyStatus = $LASTEXITCODE
$ErrorActionPreference = $savedErrorPreference
if ($dependencyStatus -ne 0) {
    Write-Host "Installing PulseBoard dependency..."
    & $python -m pip install --disable-pip-version-check -r (Join-Path $root "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed. Check the internet connection and try again." }
}

$ErrorActionPreference = "Continue"
& $python -c "import tkinter" 2>$null
$tkStatus = $LASTEXITCODE
$ErrorActionPreference = $savedErrorPreference
if ($tkStatus -ne 0) {
    throw "Tkinter is missing. Install Python from python.org with the optional Tcl/Tk component enabled."
}

$process = Start-Process -FilePath $pythonw -ArgumentList @("-m", "pulseboard.desktop") -WorkingDirectory $root -PassThru
Start-Sleep -Milliseconds 900
if ($process.HasExited -and $process.ExitCode -ne 0) {
    throw "PulseBoard failed to start. Run .venv\Scripts\python.exe -m pulseboard.desktop to see details."
}
