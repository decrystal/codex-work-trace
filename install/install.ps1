param(
  [ValidateSet("local", "remote")]
  [string] $Mode = "local",
  [string] $Endpoint = "",
  [string] $Version = "latest",
  [string] $Repo = "decrystal/codex-work-trace",
  [string] $InstallDir = "$HOME\.csgs\bin",
  [switch] $SkipPlugin
)

$ErrorActionPreference = "Stop"

if ($Mode -eq "remote" -and [string]::IsNullOrWhiteSpace($Endpoint)) {
  throw "--endpoint is required for remote mode"
}

$rid = [System.Runtime.InteropServices.RuntimeInformation]
if ($rid::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) {
  $os = "windows"
} elseif ($rid::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::OSX)) {
  $os = "darwin"
} elseif ($rid::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Linux)) {
  $os = "linux"
} else {
  throw "Unsupported OS"
}

$archRaw = $rid::OSArchitecture.ToString().ToLowerInvariant()
switch ($archRaw) {
  "x64" { $arch = "amd64" }
  "arm64" { $arch = "arm64" }
  default { throw "Unsupported architecture: $archRaw" }
}

$asset = "csgs-$os-$arch"
if ($os -eq "windows") {
  $asset = "$asset.exe"
}

$downloadBase = $env:CSGS_DOWNLOAD_BASE
if ([string]::IsNullOrWhiteSpace($downloadBase)) {
  $downloadBase = "https://github.com/$Repo/releases"
}

if ($Version -eq "latest") {
  $url = "$downloadBase/latest/download/$asset"
} else {
  $url = "$downloadBase/download/$Version/$asset"
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
$binaryName = if ($os -eq "windows") { "csgs.exe" } else { "csgs" }
$csgsBin = Join-Path $InstallDir $binaryName
Invoke-WebRequest -Uri $url -OutFile $csgsBin

if (-not $SkipPlugin) {
  $codexBin = $env:CODEX_BIN
  if ([string]::IsNullOrWhiteSpace($codexBin)) {
    $cmd = Get-Command codex -ErrorAction SilentlyContinue
    if ($cmd) {
      $codexBin = $cmd.Source
    }
  }

  if (-not [string]::IsNullOrWhiteSpace($codexBin)) {
    try {
      & $codexBin plugin --help | Out-Null
      $marketplaceSource = $env:CSGS_MARKETPLACE_SOURCE
      if ([string]::IsNullOrWhiteSpace($marketplaceSource)) {
        $marketplaceSource = "https://github.com/$Repo.git"
      }
      & $codexBin plugin marketplace add $marketplaceSource | Out-Null
      & $codexBin plugin add "csgs-$Mode@csgs" | Out-Null
    } catch {
      Write-Warning "Codex plugin install failed or plugin CLI is unavailable; continuing with csgs install."
    }
  } else {
    Write-Warning "Codex CLI not found; skipping plugin install."
  }
}

if ($Mode -eq "local") {
  & $csgsBin install --mode local --runtime binary --bin $csgsBin
} else {
  & $csgsBin install --mode remote --endpoint $Endpoint --runtime binary --bin $csgsBin
}

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ((";$userPath;" -notlike "*;$InstallDir;*")) {
  [Environment]::SetEnvironmentVariable("Path", "$InstallDir;$userPath", "User")
  Write-Host "Added $InstallDir to the user PATH. Open a new terminal for it to take effect."
}

Write-Host "CSGS installed at $csgsBin"
