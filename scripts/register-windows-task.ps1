[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$TaskName = "LLMKnowledgeBaseDailyCompile",
    [string]$At = "17:00",
    [string]$ProjectRoot
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $PSCommandPath
if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $ScriptDir "..")).Path
} else {
    $ProjectRoot = (Resolve-Path $ProjectRoot).Path
}

$Wrapper = Join-Path $ProjectRoot "scripts\compile-daily.ps1"
if (-not (Test-Path $Wrapper)) {
    throw "compile-daily.ps1 not found at $Wrapper"
}

try {
    $TriggerTime = [datetime]::ParseExact(
        $At,
        "HH:mm",
        [System.Globalization.CultureInfo]::InvariantCulture
    )
} catch {
    throw "Invalid -At value '$At'. Use 24-hour HH:mm format, for example 17:00."
}

$ActionArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$Wrapper`" -ProjectRoot `"$ProjectRoot`""
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $ActionArgs
$Trigger = New-ScheduledTaskTrigger -Daily -At $TriggerTime
$Description = "Compile changed LLM knowledge base daily logs into wiki articles."

if ($PSCmdlet.ShouldProcess($TaskName, "Register daily knowledge base compile task")) {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Description $Description `
        -Force | Out-Null

    Write-Host "Registered scheduled task '$TaskName' for $At."
}
