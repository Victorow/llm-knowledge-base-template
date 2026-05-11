[CmdletBinding()]
param(
    [string]$ProjectRoot,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $PSCommandPath
if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
} else {
    $ProjectRoot = (Resolve-Path $ProjectRoot).Path
}

$LogFile = Join-Path $ScriptDir "compile.log"
$CompileScript = Join-Path $ScriptDir "compile.py"
$Timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

Add-Content -Path $LogFile -Value ""
Add-Content -Path $LogFile -Value "===== compile-daily.ps1 @ $Timestamp ====="

$UvArgs = @("run", "--directory", $ProjectRoot, "python", $CompileScript)
if ($DryRun) {
    $UvArgs += "--dry-run"
}

Push-Location $ProjectRoot
try {
    & uv @UvArgs *>&1 | Tee-Object -FilePath $LogFile -Append
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}
