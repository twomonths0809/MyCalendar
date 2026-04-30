$ErrorActionPreference = "Stop"

$RepoOwner = "twomonths0809"
$RepoName = "MyCalendar"
$Version = "v1.0.0"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExePath = Join-Path $ProjectDir "dist\MyCalendar.exe"
$SourceZipPath = Join-Path $ProjectDir "dist\MyCalendar-source-v1.0.0.zip"
$ReleaseNotesPath = Join-Path $ProjectDir "RELEASE_NOTES.md"
$GitExe = "E:\Git\cmd\git.exe"
$GhExe = "E:\Gh\gh.exe"

Set-Location $ProjectDir
$env:PATH = "E:\Git\cmd;E:\Gh;$env:PATH"

function Require-Command($Name, $InstallHint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name was not found. $InstallHint"
    }
}

if (-not (Test-Path $GitExe)) {
    $GitExe = "git"
    Require-Command "git" "Install Git for Windows, then open a new terminal."
}

if (-not (Test-Path $GhExe)) {
    $GhExe = "gh"
    Require-Command "gh" "Install GitHub CLI, then run: gh auth login"
}

if (-not (Test-Path $ExePath)) {
    throw "Missing $ExePath. Run build_exe.bat first."
}

if (-not (Test-Path $ReleaseNotesPath)) {
    throw "Missing $ReleaseNotesPath."
}

$authStatus = & $GhExe auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "GitHub CLI is not logged in. Run: gh auth login"
}

if (-not (Test-Path ".git")) {
    & $GitExe init
    & $GitExe branch -M main
}

& $GitExe add .gitignore README.md RELEASE_NOTES.md main.py requirements.txt install_dependencies.bat run_calendar.bat build_exe.bat publish_to_github.ps1 data/.gitkeep

$hasStagedChanges = & $GitExe diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    & $GitExe commit -m "Initial release"
}

$repoFullName = "$RepoOwner/$RepoName"
$ErrorActionPreference = "Continue"
$repoExists = & $GhExe repo view $repoFullName 2>&1
$repoViewExitCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($repoViewExitCode -ne 0) {
    & $GhExe repo create $repoFullName --public --description "A lightweight personal calendar app for Windows built with Python and PySide6."
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create GitHub repository."
    }
} else {
    Write-Host "Repository already exists: $repoFullName"
}

$remote = & $GitExe remote
if ($remote -notcontains "origin") {
    & $GitExe remote add origin "https://github.com/$repoFullName.git"
} else {
    & $GitExe remote set-url origin "https://github.com/$repoFullName.git"
}

& $GitExe push -u origin main
if ($LASTEXITCODE -ne 0) {
    throw "Failed to push source code to GitHub."
}

$ErrorActionPreference = "Continue"
$releaseExists = & $GhExe release view $Version --repo $repoFullName 2>&1
$releaseViewExitCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($releaseViewExitCode -eq 0) {
    & $GhExe release upload $Version $ExePath --repo $repoFullName --clobber
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upload exe to existing release."
    }
    if (Test-Path $SourceZipPath) {
        & $GhExe release upload $Version $SourceZipPath --repo $repoFullName --clobber
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to upload source zip to existing release."
        }
    }
} else {
    $assets = @($ExePath)
    if (Test-Path $SourceZipPath) {
        $assets += $SourceZipPath
    }
    & $GhExe release create $Version @assets --repo $repoFullName --title "MyCalendar v1.0.0" --notes-file $ReleaseNotesPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create GitHub release."
    }
}

Write-Host ""
Write-Host "Published successfully:"
Write-Host "https://github.com/$repoFullName"
Write-Host "https://github.com/$repoFullName/releases/tag/$Version"
