param(
    [string]$Python = "",
    [string]$VenvPath = "",
    [switch]$SkipOcr
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
if (-not $VenvPath) {
    $VenvPath = Join-Path $env:LOCALAPPDATA "ResearchOS\python-envs\zotero-ocr"
}
$venvFullPath = $VenvPath
if (-not [System.IO.Path]::IsPathRooted($venvFullPath)) {
    throw "VenvPath must be an absolute machine-local path. Do not create Python environments inside the sync workspace."
}
$workspaceRoot = [System.IO.Path]::GetFullPath($projectRoot)
$venvResolvedParent = [System.IO.Path]::GetFullPath((Split-Path -Parent $venvFullPath))
if ($venvResolvedParent.StartsWith($workspaceRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to create a Python environment inside the sync workspace: $venvFullPath"
}
$requirements = Join-Path $projectRoot "tools\requirements\base.txt"
$ocrRequirements = Join-Path $projectRoot "tools\requirements\ocr.txt"

if (-not $Python) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $Python = $pythonCommand.Source
    }
}

if (-not $Python) {
    throw "Python was not found on PATH. Pass -Python with an absolute python.exe path."
}

& $Python -m venv $venvFullPath
$venvPython = Join-Path $venvFullPath "Scripts\python.exe"

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r $requirements

if (-not $SkipOcr) {
    & $venvPython -m pip install -r $ocrRequirements
}

Write-Host "OK: local Python environment is ready: $venvPython"
if (-not $SkipOcr) {
    Write-Host "NOTE: OCR also requires machine-local Tesseract. Use tools\runtime\ensure_ocr_needed.py for OCR dependency checks and setup."
}
