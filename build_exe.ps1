param(
    [switch]$UseUPX
)

# Build a minimal one-file EXE into WIN_64 using PyInstaller and the headless entrypoint.
# Assumes a virtual environment with pyinstaller installed.

$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$OutDir = Join-Path $ProjectRoot 'WIN_64'
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

# Detect python
$py = "$env:VIRTUAL_ENV\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = (Get-Command python).Source }

# Ensure pyinstaller
try { & $py -m PyInstaller --version | Out-Null } catch { & $py -m pip install --upgrade pip; & $py -m pip install pyinstaller }

# Common PyInstaller args for minimal size
$icon = 'icons/app_icon.ico'
$addData = @(
    'index.html;.','static;static','icons;icons','README.md;.'
)
$datas = @()
foreach ($d in $addData) { $datas += @('--add-data', $d) }

$excludes = @(
    # Exclude GUI libs; we use headless entrypoint
    '--exclude-module','PySide6',
    '--exclude-module','PyQt5',
    '--exclude-module','tkinter',
    '--exclude-module','matplotlib',
    '--exclude-module','PIL',
    '--exclude-module','numpy',
    '--exclude-module','scipy',
    '--exclude-module','pydoc',
    '--exclude-module','asyncpg'
)

$hidden = @(
    # FastAPI/Starlette deps sometimes need to be hinted
    '--hidden-import','anyio',
    '--hidden-import','idna',
    '--hidden-import','sniffio'
)

$upxArgs = @()
if ($UseUPX) {
    # Try to use system UPX if available; otherwise skip
    $upx = (Get-Command upx -ErrorAction SilentlyContinue)
    if ($upx) { $upxArgs = @('--upx-dir', Split-Path -Parent $upx.Source) }
}

$cmd = @(
    '-m','PyInstaller',
    '--name','ThermoGridServer',
    '--onefile','--noconsole',
    '--clean',
    '--optimize','2',
    '--icon', $icon
) + $datas + $excludes + $hidden + $upxArgs + @('server_headless.py')

& $py $cmd

# Move artifact
$exe = Join-Path $ProjectRoot 'dist/ThermoGridServer.exe'
if (Test-Path $exe) { Move-Item -Force $exe $OutDir }

Write-Host "Built WIN_64/ThermoGridServer.exe"
