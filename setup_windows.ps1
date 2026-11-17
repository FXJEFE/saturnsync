# Requires Windows PowerShell 5+ and an existing PROJECT_ROOT.
# Installs Python 3.8.10 x64 per-user when `py -3.8` is missing, then creates
# <PROJECT_ROOT>\.venv and installs requirements.txt into it.
param(
    [string]$ProjectDir = ""
)

$ErrorActionPreference = "Stop"

function Fail {
    param([string]$Message)
    Write-Host $Message
    exit 1
}

function Resolve-ProjectRoot {
    if ($ProjectDir) { return $ProjectDir }
    if ($env:FXJEFE_PROJECT_DIR) { return $env:FXJEFE_PROJECT_DIR }
    return (Join-Path $env:USERPROFILE "Documents\FXJEFE_Project")
}

$source = "default"
$Root = Resolve-ProjectRoot
if ($ProjectDir) { $source = "-ProjectDir" }
elseif ($env:FXJEFE_PROJECT_DIR) { $source = "FXJEFE_PROJECT_DIR" }
Write-Host "PROJECT_ROOT=$Root (source=$source)"
if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
    Fail "PROJECT_ROOT does not exist: $Root. Clone this repo to $env:USERPROFILE\Documents\FXJEFE_Project or set FXJEFE_PROJECT_DIR."
}

$Requirements = Join-Path $PSScriptRoot "requirements.txt"
if (-not (Test-Path -LiteralPath $Requirements)) {
    $Requirements = Join-Path $Root "requirements.txt"
}
if (-not (Test-Path -LiteralPath $Requirements)) {
    Fail "requirements.txt was not found next to setup_windows.ps1 or in PROJECT_ROOT."
}

$versionCheck = "import struct,sys; raise SystemExit(0 if sys.version.split()[0]=='3.8.10' and struct.calcsize('P')*8==64 else 2)"
$PythonExe = $null
$UseLauncher = $false
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.8 -c $versionCheck
    if ($LASTEXITCODE -eq 0) {
        $UseLauncher = $true
    } elseif ($LASTEXITCODE -eq 2) {
        Fail "py -3.8 is installed but it is not 64-bit CPython 3.8.10. Remove that 3.8 from the py launcher or install the official 3.8.10 x64 build."
    }
}

if (-not $UseLauncher) {
    $Installer = Join-Path $env:TEMP "python-3.8.10-amd64.exe"
    $Url = "https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe"
    Write-Host "Downloading $Url"
    Invoke-WebRequest -Uri $Url -OutFile $Installer
    Write-Host "Installing Python 3.8.10 for the current user"
    $installArgs = @("/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_launcher=1", "Include_test=0", "Shortcuts=0")
    $proc = Start-Process -FilePath $Installer -ArgumentList $installArgs -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        Fail "Python installer exited $($proc.ExitCode)"
    }
    $PythonExe = Join-Path $env:LOCALAPPDATA "Programs\Python\Python38\python.exe"
    if (-not (Test-Path -LiteralPath $PythonExe)) {
        Fail "Python 3.8.10 installer finished but python.exe was not found at $PythonExe."
    }
    & $PythonExe -c $versionCheck
    if ($LASTEXITCODE -ne 0) {
        Fail "Installed interpreter at $PythonExe is not 64-bit Python 3.8.10."
    }
}

$Venv = Join-Path $Root ".venv"
Write-Host "Creating virtualenv $Venv"
if ($UseLauncher) {
    & py -3.8 -m venv $Venv
} else {
    & $PythonExe -m venv $Venv
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$VenvPython = Join-Path $Venv "Scripts\python.exe"
& $VenvPython -m pip install --upgrade "pip==24.0" "setuptools==69.5.1" "wheel==0.43.0"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $VenvPython -m pip install -r $Requirements
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Setup complete. Run: $Root\run_pipeline.bat"
exit 0
