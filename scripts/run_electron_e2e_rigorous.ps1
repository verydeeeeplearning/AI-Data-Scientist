param(
  [switch]$SkipBackendBuild,
  [switch]$SkipElectronBuild,
  [switch]$Quick,
  [switch]$IncludeA11y,
  [switch]$IncludeOnboarding
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ElectronDir = Join-Path $RepoRoot "electron"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$ArtifactsRoot = Join-Path $RepoRoot ".manual_verification\electron-e2e\$Timestamp"

New-Item -ItemType Directory -Force -Path $ArtifactsRoot | Out-Null

function Invoke-Step {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][scriptblock]$Command
  )

  $logPath = Join-Path $ArtifactsRoot ("{0}.log" -f ($Name -replace '[^A-Za-z0-9_.-]', '_'))
  Write-Host "==> $Name"
  try {
    & $Command *>&1 | Tee-Object -FilePath $logPath
  } catch {
    Write-Host "FAILED: $Name"
    Write-Host "Log: $logPath"
    throw
  }
}

Write-Host "Artifacts: $ArtifactsRoot"

if (-not $SkipBackendBuild) {
  Invoke-Step "backend-build" {
    Set-Location $RepoRoot
    python scripts/build_backend.py
  }
}

if ($SkipElectronBuild) {
  Invoke-Step "electron-test-compile" {
    Set-Location $ElectronDir
    node_modules\.bin\tsc.cmd -p tsconfig.test.json
  }
} else {
  Invoke-Step "electron-build-and-test-compile" {
    Set-Location $ElectronDir
    npm.cmd run test:e2e:prepare
  }
}

$env:DS_AGENT_E2E_ARTIFACTS_DIR = Join-Path $ArtifactsRoot "visual-surface-survey"
$env:DS_AGENT_E2E_DISABLE_AUTO_UPDATER = "1"
$env:DS_AGENT_E2E_DISABLE_PROTOCOL_REGISTRATION = "1"

$specs = @(
  "tests/.compiled/smoke/diagnostic-window.spec.js",
  "tests/.compiled/smoke/happy-path.spec.js",
  "tests/.compiled/smoke/visual-surface-survey.spec.js",
  "tests/.compiled/smoke/task-contract-lifecycle.spec.js",
  "tests/.compiled/smoke/task-contract-governance.spec.js",
  "tests/.compiled/smoke/workflow-integration.spec.js",
  "tests/.compiled/smoke/autonomy-control-plane.spec.js",
  "tests/.compiled/smoke/decision-os-review.spec.js"
)

if ($IncludeOnboarding) {
  $specs = @("tests/.compiled/smoke/onboarding-contract-first.spec.js") + $specs
}

if ($Quick) {
  $specs = @(
    "tests/.compiled/smoke/diagnostic-window.spec.js",
    "tests/.compiled/smoke/happy-path.spec.js",
    "tests/.compiled/smoke/visual-surface-survey.spec.js"
  )
}

foreach ($spec in $specs) {
  Invoke-Step $spec {
    Set-Location $ElectronDir
    node $spec
  }
}

if ($IncludeA11y) {
  Invoke-Step "a11y-suite" {
    Set-Location $ElectronDir
    npm.cmd run test:e2e:a11y
  }
}

Write-Host "Electron E2E rigorous gate completed."
Write-Host "Artifacts: $ArtifactsRoot"
