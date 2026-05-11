param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

uv run pyinstaller packaging/pyinstaller/llm-knowledge-base.spec --noconfirm

if (-not $SkipInstaller) {
    $iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    $localIscc = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"
    if ($null -eq $iscc -and (Test-Path $localIscc)) {
        $isccPath = $localIscc
    } elseif ($null -ne $iscc) {
        $isccPath = $iscc.Source
    } else {
        $isccPath = $null
    }

    if ($null -eq $isccPath) {
        Write-Warning "Inno Setup ISCC.exe not found. Install Inno Setup to build the installer."
    } else {
        & $isccPath packaging/inno/llm-knowledge-base.iss
    }
}

uv run python scripts/smoke-packaged.py --exe dist/LLMKnowledgeBase/LLMKnowledgeBase.exe
