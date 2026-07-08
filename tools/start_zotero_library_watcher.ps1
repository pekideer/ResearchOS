param(
    [string]$Python = "",
    [string]$Db = "",
    [int]$Interval = 300,
    [string]$FulltextCacheRoot = "",
    [switch]$Ocr,
    [string]$OcrLanguage = "eng+chi_sim",
    [int]$OcrDpi = 220,
    [int]$PdfTimeout = 300,
    [int]$StaleAfter = 3600,
    [int]$LockStaleAfter = 1800,
    [switch]$ForceLock,
    [int]$MaxItems = 0,
    [int]$MaxProcessItems = 0,
    [switch]$NoPdfText
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $Python) {
    $Python = Join-Path $env:LOCALAPPDATA "ResearchOS\python-envs\zotero-ocr\Scripts\python.exe"
}
if (-not $Db) {
    $Db = Join-Path $projectRoot "corpus\zotero\M-001-zotero-library\zotero_library.sqlite"
}
$pythonPath = $Python
if (-not [System.IO.Path]::IsPathRooted($pythonPath)) {
    throw "Python must be an absolute machine-local path."
}
if (-not (Test-Path $pythonPath)) {
    throw "Python executable not found: $pythonPath. Run tools\build_local_python_env.ps1 first or pass -Python."
}

$logDir = Join-Path $env:LOCALAPPDATA "ResearchOS\logs\zotero-library-watcher"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$timestamp = Get-Date -Format "yyyyMMddTHHmmss"
$stdout = Join-Path $logDir "$timestamp-watcher.out.log"
$stderr = Join-Path $logDir "$timestamp-watcher.err.log"
$pidPath = Join-Path $logDir "watcher.pid"

$args = @(
    "tools\zotero_library_index.py",
    "--db", $Db,
    "watch",
    "--interval", [string]$Interval,
    "--pdf-timeout", [string]$PdfTimeout,
    "--stale-after", [string]$StaleAfter,
    "--lock-stale-after", [string]$LockStaleAfter
)

if ($FulltextCacheRoot) {
    $args += @("--fulltext-cache-root", $FulltextCacheRoot)
}
if ($Ocr) {
    $args += @("--ocr", "--ocr-language", $OcrLanguage, "--ocr-dpi", [string]$OcrDpi)
}
if ($NoPdfText) {
    $args += "--no-pdf-text"
}
if ($ForceLock) {
    $args += "--force-lock"
}
if ($MaxItems -gt 0) {
    $args += @("--max-items", [string]$MaxItems)
}
if ($MaxProcessItems -gt 0) {
    $args += @("--max-process-items", [string]$MaxProcessItems)
}

function Quote-ProcessArgument {
    param([string]$Value)
    if ($Value -match '[\s"]') {
        return '"' + ($Value -replace '"', '\"') + '"'
    }
    return $Value
}

$argumentLine = ($args | ForEach-Object { Quote-ProcessArgument $_ }) -join " "
$process = Start-Process -FilePath $pythonPath -ArgumentList $argumentLine -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
Set-Content -Path $pidPath -Value $process.Id -Encoding UTF8

Write-Host "OK: Zotero library watcher started."
Write-Host "PID: $($process.Id)"
Write-Host "stdout: $stdout"
Write-Host "stderr: $stderr"
