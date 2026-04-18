[CmdletBinding()]
param(
    [switch]$Apply,
    [switch]$IncludeBuildArtifacts,
    [switch]$IncludeDependencies,
    [switch]$IncludeVirtualEnv
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$workspaceRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$workspaceRootWithSlash = $workspaceRoot.TrimEnd("\") + "\"

function Test-InWorkspace {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = [System.IO.Path]::GetFullPath($Path)
    return $resolved -eq $workspaceRoot -or $resolved.StartsWith(
        $workspaceRootWithSlash,
        [System.StringComparison]::OrdinalIgnoreCase
    )
}

function Get-ItemSizeBytes {
    param([Parameter(Mandatory = $true)][System.IO.FileSystemInfo]$Item)

    if ($Item.PSIsContainer) {
        $measurement = Get-ChildItem -LiteralPath $Item.FullName -Force -Recurse -File `
            -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum
        if ($null -eq $measurement -or $null -eq $measurement.Sum) {
            return 0
        }

        return [int64]$measurement.Sum
    }

    return $Item.Length
}

function Add-CleanupCandidates {
    param(
        [Parameter(Mandatory = $true)][string[]]$Names,
        [Parameter(Mandatory = $true)][string]$Category,
        [System.Collections.Generic.List[object]]$Targets
    )

    $children = Get-ChildItem -LiteralPath $workspaceRoot -Force -ErrorAction SilentlyContinue
    foreach ($name in $Names) {
        $matches = $children | Where-Object { $_.Name -like $name }
        foreach ($match in $matches) {
            if (-not (Test-InWorkspace -Path $match.FullName)) {
                throw "Refusing to touch path outside workspace: $($match.FullName)"
            }

            $Targets.Add(
                [pscustomobject]@{
                    Category = $Category
                    FullPath = $match.FullName
                    Exists = $true
                    Bytes = Get-ItemSizeBytes -Item $match
                }
            )
        }
    }
}

function Add-LiteralTarget {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][string]$Category,
        [System.Collections.Generic.List[object]]$Targets
    )

    $fullPath = [System.IO.Path]::GetFullPath((Join-Path $workspaceRoot $RelativePath))
    if (-not (Test-InWorkspace -Path $fullPath)) {
        throw "Refusing to touch path outside workspace: $fullPath"
    }

    if (-not (Test-Path -LiteralPath $fullPath)) {
        return
    }

    $item = Get-Item -LiteralPath $fullPath -Force
    $Targets.Add(
        [pscustomobject]@{
            Category = $Category
            FullPath = $fullPath
            Exists = $true
            Bytes = Get-ItemSizeBytes -Item $item
        }
    )
}

$targets = [System.Collections.Generic.List[object]]::new()

Add-CleanupCandidates -Names @(
    ".mypy_cache",
    ".pytest_cache",
    ".pytest_tmp",
    ".pytest_tmp*",
    ".ruff_cache",
    ".playwright-mcp",
    ".manual_verification",
    ".tmp",
    ".tmp_pytest",
    "pytest_run_tmp",
    "tmp",
    "tmp*",
    "temp_pytest*",
    "plan*_smoke_*",
    "Usersaquap.codexmemoriespytesttmp"
) -Category "cache-temp" -Targets $targets

Add-LiteralTarget -RelativePath ".coverage" -Category "coverage" -Targets $targets
Add-LiteralTarget -RelativePath "htmlcov" -Category "coverage" -Targets $targets

if ($IncludeBuildArtifacts) {
    Add-LiteralTarget -RelativePath "build" -Category "build" -Targets $targets
    Add-LiteralTarget -RelativePath "dist" -Category "build" -Targets $targets
    Add-LiteralTarget -RelativePath "electron/dist" -Category "build" -Targets $targets
    Add-LiteralTarget -RelativePath "electron/.vite" -Category "build" -Targets $targets
    Add-LiteralTarget -RelativePath "electron/tsconfig.main.tsbuildinfo" -Category "build" -Targets $targets
}

if ($IncludeDependencies) {
    Add-LiteralTarget -RelativePath "node_modules" -Category "dependency" -Targets $targets
    Add-LiteralTarget -RelativePath "electron/node_modules" -Category "dependency" -Targets $targets
}

if ($IncludeVirtualEnv) {
    Add-LiteralTarget -RelativePath ".venv" -Category "virtualenv" -Targets $targets
}

$uniqueTargets = $targets |
    Sort-Object -Property FullPath -Unique |
    Sort-Object -Property Category, FullPath

if (-not $uniqueTargets) {
    Write-Host "No cleanup targets found under $workspaceRoot"
    exit 0
}

$report = $uniqueTargets | ForEach-Object {
    [pscustomobject]@{
        Category = $_.Category
        SizeMB = [math]::Round(($_.Bytes / 1MB), 2)
        Path = $_.FullPath.Replace($workspaceRootWithSlash, "")
    }
}

$mode = if ($Apply) { "APPLY" } else { "DRY-RUN" }
Write-Host "Workspace cleanup mode: $mode"
$report | Format-Table -AutoSize

$totalBytes = ($uniqueTargets | Measure-Object -Property Bytes -Sum).Sum
Write-Host ("Total candidate size: {0} MB" -f [math]::Round(($totalBytes / 1MB), 2))

if (-not $Apply) {
    Write-Host "Nothing was deleted. Re-run with -Apply to remove the targets above."
    exit 0
}

foreach ($target in $uniqueTargets) {
    if (-not (Test-Path -LiteralPath $target.FullPath)) {
        continue
    }

    Write-Host "Removing $($target.FullPath)"
    Remove-Item -LiteralPath $target.FullPath -Recurse -Force
}

Write-Host "Cleanup complete."
