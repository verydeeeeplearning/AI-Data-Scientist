param(
  [switch]$SkipCompile
)

$ErrorActionPreference = "Stop"

Add-Type -Namespace Win32 -Name ErrorMode -MemberDefinition @"
[System.Runtime.InteropServices.DllImport("kernel32.dll")]
public static extern uint SetErrorMode(uint uMode);
"@
[Win32.ErrorMode]::SetErrorMode(0x0002) | Out-Null

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ElectronDir = Join-Path $RepoRoot "electron"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$ArtifactsRoot = Join-Path $RepoRoot ".manual_verification\electron-e2e\direct-cdp-$Timestamp"
$BackendLog = Join-Path $ArtifactsRoot "backend.stdout.log"
$BackendErr = Join-Path $ArtifactsRoot "backend.stderr.log"
$ElectronLog = Join-Path $ArtifactsRoot "electron.stdout.log"
$ElectronErr = Join-Path $ArtifactsRoot "electron.stderr.log"
$SurveyLog = Join-Path $ArtifactsRoot "visual-survey-cdp.log"
$WorkspaceDir = Join-Path $ArtifactsRoot "workspace"
$ConfigPath = Join-Path $ArtifactsRoot "config.yaml"

New-Item -ItemType Directory -Force -Path $ArtifactsRoot | Out-Null
New-Item -ItemType Directory -Force -Path $WorkspaceDir | Out-Null

function Get-FreeTcpPort {
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
  $listener.Start()
  try {
    return $listener.LocalEndpoint.Port
  } finally {
    $listener.Stop()
  }
}

function Wait-HttpOk {
  param(
    [Parameter(Mandatory = $true)][string]$Uri,
    [int]$TimeoutSeconds = 60
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      Invoke-RestMethod -Uri $Uri -TimeoutSec 1 | Out-Null
      return
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
  throw "Timed out waiting for $Uri"
}

function Wait-CdpPage {
  param(
    [Parameter(Mandatory = $true)][int]$Port,
    [int]$TimeoutSeconds = 60
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $targets = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/json/list" -TimeoutSec 1
      $pageTargets = @($targets | Where-Object { $_.type -eq "page" })
      if ($pageTargets.Count -gt 0) {
        return
      }
    } catch {
      Start-Sleep -Milliseconds 500
    }
  }
  throw "Timed out waiting for Electron CDP page on port $Port"
}

if (-not $SkipCompile) {
  Push-Location $ElectronDir
  try {
    & .\node_modules\.bin\tsc.cmd -p tsconfig.main.json
    & .\node_modules\.bin\tsc.cmd -p tsconfig.test.json
  } finally {
    Pop-Location
  }
}

$BackendPort = Get-FreeTcpPort
$CdpPort = Get-FreeTcpPort
$WsToken = "e2e-direct-cdp-$Timestamp"
$BackendExe = Join-Path $RepoRoot "dist\ds-agent-backend\ds-agent-api.exe"
$ElectronExe = Join-Path $ElectronDir "node_modules\electron\dist\electron.exe"
$ElectronMain = Join-Path $ElectronDir "dist\main\index.js"
$UserData = Join-Path ([System.IO.Path]::GetTempPath()) "ds-agent-e2e-userData-$Timestamp"

if (-not (Test-Path $BackendExe)) {
  throw "Backend binary not found: $BackendExe"
}
if (-not (Test-Path $ElectronExe)) {
  throw "Electron binary not found: $ElectronExe"
}
if (-not (Test-Path $ElectronMain)) {
  throw "Electron main bundle not found: $ElectronMain"
}

New-Item -ItemType Directory -Force -Path $UserData | Out-Null

$config = @{
  provider = @{
    default_model = "anthropic/claude-sonnet-4-6"
  }
  agent = @{
    workspace_dir = $WorkspaceDir
  }
} | ConvertTo-Json -Depth 8
Set-Content -Path $ConfigPath -Value $config -Encoding UTF8

Write-Host "Artifacts: $ArtifactsRoot"
Write-Host "Workspace: $WorkspaceDir"
Write-Host "Backend port: $BackendPort"
Write-Host "CDP port: $CdpPort"

$env:DS_AGENT_WS_TOKEN = $WsToken
$env:DS_AGENT_CONFIG_PATH = $ConfigPath
$env:DS_AGENT_SENTRY_DSN = ""
$env:DS_AGENT_ERROR_REPORTING_ENABLED = "0"
$env:DS_AGENT_TELEMETRY_ENABLED = "0"

$backendProcess = Start-Process `
  -FilePath $BackendExe `
  -ArgumentList @("--port", "$BackendPort") `
  -WorkingDirectory $RepoRoot `
  -RedirectStandardOutput $BackendLog `
  -RedirectStandardError $BackendErr `
  -PassThru

$electronProcess = $null
try {
  Wait-HttpOk -Uri "http://127.0.0.1:$BackendPort/health" -TimeoutSeconds 60

  $env:DS_AGENT_E2E_EXISTING_BACKEND_PORT = "$BackendPort"
  $env:DS_AGENT_E2E_EXISTING_BACKEND_TOKEN = $WsToken
  $env:DS_AGENT_E2E_USE_BUILT_RENDERER = "1"
  $env:DS_AGENT_E2E_SKIP_ONBOARDING = "1"
  $env:DS_AGENT_E2E_USER_DATA_DIR = $UserData
  $env:DS_AGENT_E2E_DISABLE_AUTO_UPDATER = "1"
  $env:DS_AGENT_E2E_DISABLE_PROTOCOL_REGISTRATION = "1"
  $env:DS_AGENT_E2E_DISABLE_CHROMIUM_SANDBOX = "1"

  $electronProcess = Start-Process `
    -FilePath $ElectronExe `
    -ArgumentList @(
      "--no-sandbox",
      "--disable-gpu-sandbox",
      "--single-process",
      "--in-process-gpu",
      "--disable-features=NetworkServiceSandbox,NetworkServiceCodeIntegrity,RendererAppContainer,GpuAppContainer,PrintCompositorLPAC,WinSboxNetworkServiceSandboxIsLPAC,WinSboxDisableExtensionPoint",
      "--disable-crash-reporter",
      "--disable-breakpad",
      "--disable-in-process-stack-traces",
      "--disable-gpu-shader-disk-cache",
      "--disk-cache-size=0",
      "--media-cache-size=0",
      "--remote-debugging-port=$CdpPort",
      $ElectronMain
    ) `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput $ElectronLog `
    -RedirectStandardError $ElectronErr `
    -PassThru

  Wait-CdpPage -Port $CdpPort -TimeoutSeconds 60

  $env:DS_AGENT_E2E_CDP_PORT = "$CdpPort"
  $env:DS_AGENT_E2E_ARTIFACTS_DIR = Join-Path $ArtifactsRoot "visual-surface-survey"
  Write-Host "Running CDP visual survey..."
  Write-Host "Survey artifacts: $env:DS_AGENT_E2E_ARTIFACTS_DIR"
  Push-Location $ElectronDir
  try {
    & node tests\.compiled\smoke\visual-surface-survey-cdp.spec.js *>&1 |
      Tee-Object -FilePath $SurveyLog
    Write-Host "Survey exit code: $LASTEXITCODE"
    if ($LASTEXITCODE -ne 0) {
      throw "visual-surface-survey-cdp failed with exit code $LASTEXITCODE. Log: $SurveyLog"
    }
  } finally {
    Pop-Location
  }

  Write-Host "Direct CDP Electron E2E completed."
  Write-Host "Artifacts: $ArtifactsRoot"
} finally {
  if ($electronProcess -and -not $electronProcess.HasExited) {
    Stop-Process -Id $electronProcess.Id -Force
  }
  if ($backendProcess -and -not $backendProcess.HasExited) {
    Stop-Process -Id $backendProcess.Id -Force
  }
}
