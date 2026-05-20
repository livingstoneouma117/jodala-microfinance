param(
    [int]$Port = 5000
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Root ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$Requirements = Join-Path $Root "requirements.txt"
$CachedPackages = Join-Path $Root "venv\Lib\site-packages"

function Run-Step {
    param(
        [string]$FilePath,
        [string[]]$Arguments
    )

    & $FilePath @Arguments 2>&1 | ForEach-Object { Write-Host $_ }
    return $LASTEXITCODE
}

function Copy-CachedPackages {
    if (-not (Test-Path -LiteralPath $CachedPackages)) {
        return $false
    }

    $target = Join-Path $Venv "Lib\site-packages"
    $packages = @(
        "blinker", "blinker-*.dist-info",
        "click", "click-*.dist-info",
        "colorama", "colorama-*.dist-info",
        "dateutil", "python_dateutil-*.dist-info",
        "flask", "flask-*.dist-info",
        "itsdangerous", "itsdangerous-*.dist-info",
        "jinja2", "jinja2-*.dist-info",
        "jwt", "pyjwt-*.dist-info",
        "markupsafe", "markupsafe-*.dist-info",
        "six.py", "six-*.dist-info",
        "werkzeug", "werkzeug-*.dist-info"
    )

    foreach ($package in $packages) {
        Get-ChildItem -Path $CachedPackages -Filter $package -ErrorAction SilentlyContinue |
            Copy-Item -Destination $target -Recurse -Force
    }

    return $true
}

function Find-Python {
    $candidates = @()

    foreach ($name in @("py.exe", "python.exe", "python3.exe")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd -and $cmd.Source -notlike "*\WindowsApps\*") {
            $candidates += $cmd.Source
        }
    }

    $commonPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "C:\Python314\python.exe",
        "C:\Python313\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe"
    )

    $installRoots = @(
        "$env:LOCALAPPDATA\Programs\Python",
        "C:\Program Files\Python"
    )

    foreach ($root in $installRoots) {
        if (Test-Path -LiteralPath $root) {
            $candidates += Get-ChildItem -LiteralPath $root -Recurse -Filter python.exe -ErrorAction SilentlyContinue |
                Select-Object -ExpandProperty FullName
        }
    }

    foreach ($path in $commonPaths) {
        if (Test-Path -LiteralPath $path) {
            $candidates += $path
        }
    }

    foreach ($path in $candidates | Select-Object -Unique) {
        try {
            $version = & $path --version 2>&1
            if ($LASTEXITCODE -eq 0 -and $version -match "Python 3") {
                return $path
            }
        } catch {
            continue
        }
    }

    return $null
}

$python = Find-Python
if (-not $python) {
    Write-Host "Python 3 was not found."
    Write-Host "Install Python 3.10 or newer from https://www.python.org/downloads/windows/"
    Write-Host "Then run this script again from: $Root"
    exit 1
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "Creating local Python environment..."
    & $python -m venv $Venv
}

$dependencyCheck = Run-Step $VenvPython @("-c", "import flask, jwt, dateutil")
if ($dependencyCheck -ne 0) {
    Write-Host "Installing dependencies..."
    $pipUpgrade = Run-Step $VenvPython @("-m", "pip", "install", "--upgrade", "pip")
    $pipInstall = Run-Step $VenvPython @("-m", "pip", "install", "-r", $Requirements)

    if ($pipInstall -ne 0) {
        Write-Host "Online install was blocked. Trying cached local packages..."
        if (-not (Copy-CachedPackages)) {
            Write-Host "Could not find cached packages in the old venv folder."
            exit $pipInstall
        }
    }

    $dependencyCheck = Run-Step $VenvPython @("-c", "import flask, jwt, dateutil")
    if ($dependencyCheck -ne 0) {
        Write-Host "Dependencies are still missing."
        exit $dependencyCheck
    }
}

Write-Host "Starting SACCOFinance LMS on http://localhost:$Port"
Set-Location -LiteralPath $Root
$env:FLASK_ENV = "development"
$env:PORT = "$Port"
$env:PYTHONUTF8 = "1"
& $VenvPython app.py
