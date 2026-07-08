param(
    [string]$Root = "",
    [string]$SecretDir = "",
    [string]$Endpoint = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

function Read-WithDefault {
    param(
        [string]$Prompt,
        [string]$Default
    )
    $value = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $Default
    }
    return $value.Trim()
}

function Convert-SecureStringToPlainText {
    param([System.Security.SecureString]$SecureValue)
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

function Escape-YamlScalar {
    param([string]$Value)
    if ($null -eq $Value) {
        return '""'
    }
    $escaped = $Value.Replace("\", "\\").Replace('"', '\"')
    return '"' + $escaped + '"'
}

if ([string]::IsNullOrWhiteSpace($Root)) {
    $Root = Resolve-Path (Join-Path $PSScriptRoot "..")
}
else {
    $Root = Resolve-Path $Root
}

if ([string]::IsNullOrWhiteSpace($SecretDir)) {
    $SecretDir = Join-Path $env:USERPROFILE ".researchos\secrets"
}

$providerDir = Join-Path $Root ".researchos\providers"
$providerPath = Join-Path $providerDir "easyscholar.yml"
$secretPath = Join-Path $SecretDir "easyscholar.env"

if ((Test-Path $providerPath) -and -not $Force) {
    Write-Host "Provider config already exists: $providerPath"
    Write-Host "Use -Force to overwrite."
    exit 1
}

if ((Test-Path $secretPath) -and -not $Force) {
    Write-Host "Secret file already exists: $secretPath"
    Write-Host "Use -Force to overwrite."
    exit 1
}

Write-Host "Configure EasyScholar API for ResearchOS."
Write-Host "You only need to provide the API endpoint and API key."
Write-Host "Other settings use ResearchOS defaults and can be edited later if the API requires a different contract."
Write-Host "Provider config will be written under the synced ResearchOS workspace."
Write-Host "The real API key will be written only to the local user secret directory."
Write-Host ""

if ([string]::IsNullOrWhiteSpace($Endpoint)) {
    $endpoint = Read-WithDefault "EasyScholar API endpoint" "https://example.invalid/easyscholar/query"
}
else {
    $endpoint = $Endpoint.Trim()
}

$method = "GET"
$authHeader = "Authorization"
$authPrefix = "Bearer"
$queryPriority = "venue,publication_title,journal,publication,journal_abbrev"
$timeoutSeconds = "20"
$rateLimit = "30"

$secureKey = Read-Host "EasyScholar API key" -AsSecureString
$apiKey = Convert-SecureStringToPlainText $secureKey
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    throw "EasyScholar API key is empty; aborting."
}

New-Item -ItemType Directory -Force -Path $providerDir | Out-Null
New-Item -ItemType Directory -Force -Path $SecretDir | Out-Null

$fields = $queryPriority.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ }
if ($fields.Count -eq 0) {
    throw "Query field priority is empty; aborting."
}

$yamlLines = @(
    "# EasyScholar provider config for ResearchOS.",
    "# This file may live in the synced workspace but must not contain the real API key.",
    "provider: easyscholar",
    "endpoint: $(Escape-YamlScalar $endpoint)",
    "method: $(Escape-YamlScalar $method)",
    "auth_header: $(Escape-YamlScalar $authHeader)",
    "auth_prefix: $(Escape-YamlScalar $authPrefix)",
    "query_field_priority:"
)

foreach ($field in $fields) {
    $yamlLines += "  - $(Escape-YamlScalar $field)"
}

$yamlLines += @(
    "timeout_seconds: $timeoutSeconds",
    "rate_limit_per_minute: $rateLimit",
    "cache_policy: project-internal-cache",
    "secret_env_file: $(Escape-YamlScalar $secretPath)"
)

$envLines = @(
    "# EasyScholar API key for ResearchOS.",
    "# Do not copy this file into OneDrive, Markdown, logs, screenshots, prompts, Git, or kit exports.",
    "EASYSCHOLAR_API_KEY=$apiKey"
)

Set-Content -LiteralPath $providerPath -Encoding UTF8 -Value $yamlLines
Set-Content -LiteralPath $secretPath -Encoding UTF8 -Value $envLines

Write-Host ""
Write-Host "EasyScholar provider config written:"
Write-Host $providerPath
Write-Host "EasyScholar API key saved locally:"
Write-Host $secretPath
Write-Host "API key value was not printed."
