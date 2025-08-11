param(
    [string]$Remote = "https://github.com/serbinov/ThermoGrid_Server.git",
    [string]$UserName = "serbinov",
    [string]$UserEmail = "serbinovoleg@gmail.com",
    [string]$Branch = "main",
    [string]$Message = "Update ThermoGrid_Server"
)

$ErrorActionPreference = 'Stop'

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[ERROR] $msg" -ForegroundColor Red }

try {
    # Ensure we run from the repo root (script directory)
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    Set-Location $scriptDir

    Write-Info "Using remote: $Remote"
    Write-Info "Branch: $Branch"

    # Check git
    git --version | Out-Null
} catch {
    Write-Err "Git is not installed or not in PATH. Install Git and retry."
    exit 1
}

# Configure identity
try {
    git config user.name $UserName | Out-Null
    git config user.email $UserEmail | Out-Null
    Write-Info "Configured git user: $UserName <$UserEmail>"
} catch {
    Write-Warn "Failed to set git user config: $($_.Exception.Message)"
}

# Initialize repo if needed
$gitDirExists = Test-Path (Join-Path (Get-Location) ".git")
if (-not $gitDirExists) {
    Write-Info "Initializing new git repository"
    git init | Out-Null
}

# Ensure desired branch
Write-Info "Checking out branch $Branch"
 git checkout -B $Branch | Out-Null

# Set or add remote origin
$remotes = git remote 2>$null
if ($LASTEXITCODE -ne 0 -or -not ($remotes -match "^origin$")) {
    Write-Info "Adding remote origin -> $Remote"
    git remote add origin $Remote 2>$null | Out-Null
} else {
    Write-Info "Updating remote origin -> $Remote"
    git remote set-url origin $Remote | Out-Null
}

# Fetch remote (if exists)
Write-Info "Fetching origin"
 git fetch origin 2>$null | Out-Null

# Merge remote/main allowing unrelated histories (README/LICENSE on remote)
Write-Info "Merging origin/$Branch (allow unrelated histories, prefer local on conflicts)"
# Git иногда пишет служебные сообщения в stderr, что PowerShell воспринимает как ошибку.
# Временно ослабим обработку ошибок и объединим stderr со stdout.
$__prevEAP = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
git pull --allow-unrelated-histories -X ours origin $Branch 2>&1 | Out-Null
$ErrorActionPreference = $__prevEAP

# Stage changes
Write-Info "Staging changes"
 git add -A | Out-Null

# Commit only if there are changes
$status = git status --porcelain
if ([string]::IsNullOrWhiteSpace($status)) {
    Write-Info "Nothing to commit. Working tree clean."
} else {
    $ts = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    $msg = "$Message ($ts)"
    Write-Info "Committing: $msg"
    git commit -m $msg | Out-Null
}

# Push
Write-Info "Pushing to origin/$Branch"
 git push -u origin $Branch
if ($LASTEXITCODE -ne 0) {
    Write-Err "Push failed. If prompted for credentials, use a GitHub Personal Access Token."
    exit $LASTEXITCODE
}

Write-Host "Done. Repository is up to date on $Remote ($Branch)." -ForegroundColor Green
