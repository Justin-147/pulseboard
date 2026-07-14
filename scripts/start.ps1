param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root ".venv"
$python = Join-Path $venv "Scripts\python.exe"
$pythonw = Join-Path $venv "Scripts\pythonw.exe"
$url = "http://127.0.0.1:17865"

function Test-PulseBoard {
    try {
        $result = Invoke-RestMethod -Uri "$url/api/health" -TimeoutSec 1
        return $result.status -eq "ok"
    } catch {
        return $false
    }
}

if (-not (Test-Path $python)) {
    Write-Host "First run: preparing PulseBoard..."
    python -m venv $venv
}

$savedErrorPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $python -c "import psutil" 2>$null
$dependencyStatus = $LASTEXITCODE
$ErrorActionPreference = $savedErrorPreference
if ($dependencyStatus -ne 0) {
    Write-Host "Installing PulseBoard dependency..."
    & $python -m pip install --disable-pip-version-check -r (Join-Path $root "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed. Check the internet connection and try again." }
}

if (-not (Test-PulseBoard)) {
    $process = Start-Process -FilePath $pythonw -ArgumentList @("-m", "pulseboard.server", "--port", "17865") -WorkingDirectory $root -PassThru
    $ready = $false
    foreach ($attempt in 1..30) {
        Start-Sleep -Milliseconds 200
        if (Test-PulseBoard) { $ready = $true; break }
        if ($process.HasExited) { break }
    }
    if (-not $ready) { throw "PulseBoard failed to start. Check whether port 17865 is already in use." }
}

if (-not $NoBrowser) {
    Start-Process $url
}
