# Requires Windows PowerShell 5+ and an existing PROJECT_ROOT.
# Creates two virtualenvs:
#   <PROJECT_ROOT>\fxjefe     Python 3.11.9  (pipeline, golden server, MetaTrader5)
#   <PROJECT_ROOT>\fxjefe38   Python 3.8.10  (TA-Lib wheel + TensorFlow 2.10.1)
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
    if ($env:FXJEFE_PROJECT_ROOT) { return $env:FXJEFE_PROJECT_ROOT }
    return (Join-Path $env:USERPROFILE "Documents\FXJEFE_Project")
}

function Ensure-Python {
    param(
        [string]$LauncherArg,
        [string]$ExactVersion,
        [string]$InstallerUrl,
        [string]$InstallDirName
    )
    $check = "import struct,sys; raise SystemExit(0 if sys.version.split()[0]=='$ExactVersion' and struct.calcsize('P')*8==64 else 2)"
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py $LauncherArg -c $check
        if ($LASTEXITCODE -eq 0) { return @("py", $LauncherArg) }
        if ($LASTEXITCODE -eq 2) {
            Fail "py $LauncherArg is installed but it is not 64-bit CPython $ExactVersion."
        }
    }
    $installer = Join-Path $env:TEMP ("python-" + $ExactVersion + "-amd64.exe")
    Write-Host "Downloading $InstallerUrl"
    Invoke-WebRequest -Uri $InstallerUrl -OutFile $installer
    $installArgs = @("/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_launcher=1", "Include_test=0", "Shortcuts=0")
    $proc = Start-Process -FilePath $installer -ArgumentList $installArgs -Wait -PassThru
    if ($proc.ExitCode -ne 0) { Fail "Python $ExactVersion installer exited $($proc.ExitCode)" }
    $pythonExe = Join-Path $env:LOCALAPPDATA ("Programs\Python\" + $InstallDirName + "\python.exe")
    if (-not (Test-Path -LiteralPath $pythonExe)) {
        Fail "Python $ExactVersion installer finished but python.exe was not found at $pythonExe."
    }
    & $pythonExe -c $check
    if ($LASTEXITCODE -ne 0) { Fail "Installed interpreter at $pythonExe is not 64-bit Python $ExactVersion." }
    return @($pythonExe)
}

function New-ProjectVenv {
    param([string[]]$PythonCmd, [string]$VenvPath, [string]$Requirements)
    Write-Host "Creating $VenvPath"
    if ($PythonCmd.Length -ge 2) {
        & $PythonCmd[0] $PythonCmd[1] -m venv $VenvPath
    } else {
        & $PythonCmd[0] -m venv $VenvPath
    }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $venvPython = Join-Path $VenvPath "Scripts\python.exe"
    & $venvPython -m pip install --upgrade "pip==24.0" "setuptools==69.5.1" "wheel==0.43.0"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $venvPython -m pip install -r $Requirements
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    return $venvPython
}

$source = "default"
$Root = Resolve-ProjectRoot
if ($ProjectDir) { $source = "-ProjectDir" }
elseif ($env:FXJEFE_PROJECT_DIR) { $source = "FXJEFE_PROJECT_DIR" }
elseif ($env:FXJEFE_PROJECT_ROOT) { $source = "FXJEFE_PROJECT_ROOT" }
Write-Host "PROJECT_ROOT=$Root (source=$source)"
if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
    Fail "PROJECT_ROOT does not exist: $Root. Clone this repo to $env:USERPROFILE\Documents\FXJEFE_Project or set FXJEFE_PROJECT_DIR."
}

$Here = $PSScriptRoot
$Req311 = Join-Path $Here "requirements.txt"
$Req38 = Join-Path $Here "requirements-fxjefe38.txt"
if (-not (Test-Path $Req311)) { $Req311 = Join-Path $Root "requirements.txt" }
if (-not (Test-Path $Req38)) { $Req38 = Join-Path $Root "requirements-fxjefe38.txt" }

$Py311 = Ensure-Python -LauncherArg "-3.11" -ExactVersion "3.11.9" -InstallerUrl "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" -InstallDirName "Python311"
$Py38 = Ensure-Python -LauncherArg "-3.8" -ExactVersion "3.8.10" -InstallerUrl "https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe" -InstallDirName "Python38"

New-ProjectVenv -PythonCmd $Py311 -VenvPath (Join-Path $Root "fxjefe") -Requirements $Req311 | Out-Null
$Py38Venv = New-ProjectVenv -PythonCmd $Py38 -VenvPath (Join-Path $Root "fxjefe38") -Requirements $Req38
$TalibWheel = "https://github.com/cgohlke/talib-build/releases/download/v0.4.28/TA_Lib-0.4.28-cp38-cp38-win_amd64.whl"
Write-Host "Installing TA-Lib from $TalibWheel"
& $Py38Venv -m pip install $TalibWheel
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Setup complete."
Write-Host "  fxjefe    -> $(Join-Path $Root 'fxjefe\Scripts\python.exe')"
Write-Host "  fxjefe38  -> $(Join-Path $Root 'fxjefe38\Scripts\python.exe')"
Write-Host "Run: $(Join-Path $Root 'run_pipeline.bat')"
exit 0
