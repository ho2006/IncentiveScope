#requires -Version 7.4
<#
Frozen-input CPU rehearsal. Run from a fresh clone; no existing raw-data or
virtual-environment copy is required. pip may reuse its download cache.
#>
param([string]$Output = 'reports/live/reproduction')
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root
$OutputPath = [IO.Path]::GetFullPath($Output, $Root)
$LiveRoot = [IO.Path]::GetFullPath('reports/live', $Root)
if (-not $OutputPath.StartsWith($LiveRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Rehearsal output must stay inside ignored reports/live, preserving the reference artifacts.'
}
New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null
$Started = [DateTime]::UtcNow
$Steps = [Collections.Generic.List[object]]::new()
function Step([string]$Name, [scriptblock]$Action) {
    $Timer = [Diagnostics.Stopwatch]::StartNew()
    try {
        & $Action
        $Steps.Add(@{ name = $Name; passed = $true; seconds = [Math]::Round($Timer.Elapsed.TotalSeconds, 3) })
    } catch {
        $Steps.Add(@{ name = $Name; passed = $false; seconds = [Math]::Round($Timer.Elapsed.TotalSeconds, 3); error = $_.Exception.Message })
        throw
    }
}
$Python = Join-Path $Root '.venv-rehearsal/Scripts/python.exe'
$env:MPLCONFIGDIR = Join-Path $OutputPath 'matplotlib'
$env:IPYTHONDIR = Join-Path $OutputPath 'ipython'
# Notebook defaults inspect saved results. Full raw/model regeneration below is explicit.
Remove-Item Env:INCENTIVESCOPE_RERUN_RAW, Env:INCENTIVESCOPE_RERUN_ML -ErrorAction SilentlyContinue
try {
    Step 'python-environment' {
        if (-not (Test-Path -LiteralPath $Python)) { py -3.14 -m venv .venv-rehearsal }
        & $Python -m pip install -r requirements-ml-cpu.txt --extra-index-url https://download.pytorch.org/whl/cpu
        & $Python -m pip wheel . --no-deps --no-build-isolation --wheel-dir "$OutputPath/wheels"
        $Wheel = Get-ChildItem -LiteralPath "$OutputPath/wheels" -Filter 'incentivescope-*.whl' | Sort-Object LastWriteTime | Select-Object -Last 1
        & $Python -m pip install --no-deps --force-reinstall $Wheel.FullName
        & $Python -m pip check
        & $Python -c 'import incentivescope; print("Installed package:", incentivescope.__file__); assert "site-packages" in incentivescope.__file__'
    }
    Step 'frozen-release-download' {
        New-Item -ItemType Directory -Force -Path 'data/raw/gmx-stip' | Out-Null
        $Release = 'https://github.com/ho2006/IncentiveScope/releases/download/v0.2.0'
        foreach ($Asset in @('trades.csv.gz', 'manifest.json', 'SHA256SUMS.txt')) {
            Invoke-WebRequest "$Release/$Asset" -OutFile "data/raw/gmx-stip/$Asset"
        }
        & $Python -c 'import gzip,shutil; from pathlib import Path; p=Path("data/raw/gmx-stip"); f=gzip.open(p/"trades.csv.gz","rb"); o=(p/"trades.csv").open("wb"); shutil.copyfileobj(f,o); o.close(); f.close()'
        $Hash = (Get-FileHash 'data/raw/gmx-stip/trades.csv' -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($Hash -ne '76e4992debf0bf2e60328221c94c840aa97c2c7545550085bcd3e83d09fe61a3') { throw 'Frozen input checksum mismatch' }
    }
    Step 'checks' { & $Python checks.py }
    Step 'core-rebuild' { & $Python scripts/build_case.py --output "$OutputPath/core" }
    Step 'cpu-ml-retrain' {
        & $Python -m incentivescope ml --config configs/gmx-stip-ml.json --input data/raw/gmx-stip/trades.csv --manifest data/raw/gmx-stip/manifest.json --output "$OutputPath/ml" --device cpu
    }
    Step 'saved-notebook-inspection' {
        foreach ($Notebook in @('gmx-stip', 'retention-ml')) {
            Copy-Item -LiteralPath "notebooks/$Notebook.ipynb" -Destination "$OutputPath/$Notebook.ipynb"
            & $Python scripts/execute_notebook.py "$OutputPath/$Notebook.ipynb"
        }
    }
    Step 'analytical-comparison' {
        & $Python scripts/verify_reproduction.py --reference-root . --candidate-root $OutputPath --input data/raw/gmx-stip/trades.csv --output "$OutputPath/comparison.json" --core-float-tolerance 1e-12
    }
    $Passed = $true
} catch {
    $Passed = $false
    $Failure = $_.Exception.Message
} finally {
    $Session = @{ schema_version = 1; passed = $Passed; started_at = $Started.ToString('o'); finished_at = [DateTime]::UtcNow.ToString('o'); tested_commit = (git rev-parse HEAD); powershell = $PSVersionTable.PSVersion.ToString(); steps = $Steps; scope = 'Independent clone, new Python environment, release download, installed wheel, CPU retraining, saved notebook execution, analytical comparison; pip cache may be reused.' }
    if (-not $Passed) { $Session.failure = $Failure }
    $Session | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath "$OutputPath/session.json" -Encoding utf8
}
if (-not $Passed) { throw "Rehearsal failed: $Failure" }
Write-Host "Rehearsal passed: $OutputPath/session.json and comparison.json"
